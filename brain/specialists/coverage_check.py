"""Coverage gate for specialist handoffs.

The gate checks that every required specialist returned a valid completed handoff
and that unresolved evidence gaps are visible before Lead Resolver analysis.
It does not resolve conflicts or outcomes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


try:
    from brain.specialists.registry import CORE_SPECIALISTS
except ModuleNotFoundError:  # Direct execution: python brain/specialists/coverage_check.py
    from registry import CORE_SPECIALISTS

# One shared policy for foreground, background, and coverage gates.
MANDATORY_SPECIALISTS = set(CORE_SPECIALISTS)
REQUIRED_RESULT_FIELDS = {
    "specialist",
    "status",
    "citations",
    "applicable_rules",
    "excluded_rules",
    "findings",
    "assumptions",
    "evidence_requests",
    "conflicts",
    "recommendation",
}
VALID_STATUSES = {"complete", "blocked", "needs_evidence"}


class CoverageCheck:
    """Recompute specialist coverage from the structured handoff."""

    def check(self, specialist_output: dict[str, Any]) -> dict[str, Any]:
        coverage = specialist_output.get("coverage", {})
        required = coverage.get("required", [])
        if not isinstance(required, list):
            required = []
        required = [name for name in required if isinstance(name, str)]
        required_set = set(required) | MANDATORY_SPECIALISTS

        raw_results = specialist_output.get("specialist_results", [])
        if not isinstance(raw_results, list):
            raw_results = []
        results_by_name: dict[str, dict[str, Any]] = {}
        malformed: list[dict[str, Any]] = []
        duplicate_results: list[str] = []
        for result in raw_results:
            if not isinstance(result, dict):
                malformed.append({"reason": "specialist result is not an object"})
                continue
            name = result.get("specialist")
            if not isinstance(name, str) or not name:
                malformed.append({"reason": "specialist result has no name"})
                continue
            if name in results_by_name:
                duplicate_results.append(name)
            results_by_name[name] = result
            missing_fields = sorted(REQUIRED_RESULT_FIELDS - set(result))
            if missing_fields:
                malformed.append({
                    "specialist": name,
                    "reason": "missing required handoff fields",
                    "fields": missing_fields,
                })
            if result.get("status") not in VALID_STATUSES:
                malformed.append({
                    "specialist": name,
                    "reason": "invalid specialist status",
                })
            for field in REQUIRED_RESULT_FIELDS - {"specialist", "status", "recommendation"}:
                if field in result and not isinstance(result[field], list):
                    malformed.append({
                        "specialist": name,
                        "reason": f"{field} must be a list",
                    })

        missing = sorted(required_set - set(results_by_name))
        # A needs_evidence handoff is still useful to Lead Resolver: another
        # specialist may contain the missing fact. Only an explicitly blocked
        # specialist prevents the Lead from reviewing the complete handoff set.
        incomplete = sorted(
            name
            for name in required_set & set(results_by_name)
            if results_by_name[name].get("status") == "blocked"
        )
        raw_evidence_gaps = self._evidence_gaps(specialist_output)
        gap_adjudication = specialist_output.get("gap_adjudication")
        if not isinstance(gap_adjudication, dict):
            gap_adjudication = {}
        gap_decision = gap_adjudication.get("decision")
        hard_gap_types = {
            "malformed_sections", "malformed_section", "invalid_section_reference",
            "invalid_line_range", "stale_index", "missing_index_source",
        }
        hard_gaps = [gap for gap in raw_evidence_gaps if gap.get("type") in hard_gap_types]
        unresolved_gaps = [
            gap for gap in raw_evidence_gaps
            if gap_decision != "proceed" or gap.get("type") in hard_gap_types
        ]
        soft_gaps = [gap for gap in unresolved_gaps if gap not in hard_gaps]
        unresolved_requests = [
            request
            for result in results_by_name.values()
            for request in result.get("evidence_requests", [])
            if isinstance(request, dict)
        ]
        conflicts = [
            conflict
            for result in results_by_name.values()
            for conflict in result.get("conflicts", [])
            if isinstance(conflict, dict)
        ]

        ready = not any((missing, incomplete, malformed, duplicate_results, hard_gaps))
        return {
            "turn_id": specialist_output.get("turn_id"),
            "mandatory_specialists": sorted(MANDATORY_SPECIALISTS),
            "required_specialists": sorted(required_set),
            "received_specialists": sorted(results_by_name),
            "missing_specialists": missing,
            "incomplete_specialists": incomplete,
            "malformed_handoffs": malformed,
            "duplicate_results": sorted(set(duplicate_results)),
            "evidence_gap_decision": gap_decision,
            "all_evidence_gaps": raw_evidence_gaps,
            "unresolved_evidence_gaps": unresolved_gaps,
            "hard_evidence_gaps": hard_gaps,
            "soft_evidence_gaps_for_lead": soft_gaps,
            "specialist_evidence_requests": unresolved_requests,
            "specialist_conflicts": conflicts,
            "ready_for_lead_resolver": ready,
            "lead_review_required": bool(soft_gaps or unresolved_requests or conflicts),
            "gate_status": "pass" if ready else "blocked",
        }

    @staticmethod
    def _evidence_gaps(specialist_output: dict[str, Any]) -> list[dict[str, Any]]:
        bundle = specialist_output.get("evidence_bundle")
        if isinstance(bundle, dict):
            gaps = bundle.get("evidence_gaps", [])
            if isinstance(gaps, list):
                return [gap for gap in gaps if isinstance(gap, dict)]
        gaps = specialist_output.get("evidence_gaps", [])
        if isinstance(gaps, list):
            return [gap for gap in gaps if isinstance(gap, dict)]
        coverage = specialist_output.get("coverage", {})
        section_gaps = coverage.get("section_gaps", []) if isinstance(coverage, dict) else []
        return [gap for gap in section_gaps if isinstance(gap, dict)]


def _load_json(argument: str) -> dict[str, Any]:
    raw = sys.stdin.read() if argument == "-" else Path(argument).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit("Coverage Check input must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Check specialist coverage before Lead Resolver")
    parser.add_argument("specialist_output", help="Specialist result JSON file or '-' for stdin")
    args = parser.parse_args()
    result = CoverageCheck().check(_load_json(args.specialist_output))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
