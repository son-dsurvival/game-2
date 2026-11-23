"""Run the real BackendLeadResolver for the herb quantity decision.

Unlike the plumbing trials, this script does not provide a collection rate. The
configured model and the Assumption Wizard/Backend Lead Resolver decide it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.backend_lead_resolver import BackendLeadResolver

RESULT_JSON = ROOT / "trial" / "46_real_backend_lead_resolver_herbs_result.json"
RESULT_MD = ROOT / "trial" / "46_real_backend_lead_resolver_herbs_result.md"


def main() -> None:
    linked = {
        "id": "backend-herb-test:clarification:1",
        "status": "answered",
        "question": "How many medicinal herbs should Renn collect per phase?",
        "answer": "You decide",
        "result": {"gap": "No explicit herb collection rate is established."},
    }
    plan = {
        "tick_id": "day-1-midday",
        "previous": {"day": 1, "phase": "Late Morning", "progress": 0.0},
        "position": {"day": 1, "phase": "Midday", "progress": 0.0},
        "actions": [{
            "directive_id": "directive-renn-herbs",
            "actor": "Renn",
            "assigned_task": "Collect medicinal herbs in the north grove.",
            "chosen_action": "Collect medicinal herbs in the north grove.",
            "location": "north grove",
            "constraints": ["Return after three phases."],
            "requires_resolution": True,
        }],
        "instructions": "Resolve the autonomous action and calculate the gathered quantity.",
    }
    specialist_output = {
        "turn_id": "day-1-midday",
        "request_type": "backend_autonomy",
        "process_type": "backend_autonomy",
        "mode": "backend_autonomy",
        "coverage_check": {
            "ready_for_lead_resolver": True,
            "missing_specialists": [],
            "incomplete_specialists": [],
            "malformed_handoffs": [],
            "hard_evidence_gaps": [],
            "unresolved_evidence_gaps": [],
        },
        "specialist_results": [
            {
                "specialist": "rules",
                "status": "complete",
                "findings": ["Resolve gathering validity, time, risk, and quantity from applicable rules."],
                "conflicts": ["No explicit herb collection rate is established; an authorized assumption may be needed."],
                "evidence_requests": [],
                "recommendation": "Use the Backend Lead Resolver; do not hardcode a rate.",
            },
            {
                "specialist": "character",
                "status": "complete",
                "findings": ["Renn is capable of following the herb-gathering directive."],
                "conflicts": [],
                "evidence_requests": [],
                "recommendation": "Resolve the action using Renn's available capability and the north grove context.",
            },
        ],
        "action_frames": [{"text": "Renn gathers medicinal herbs in the north grove.", "actor": "Renn"}],
        "selected_sections": [],
        "specialist_updates": {},
    }
    context = {
        "turn_id": "day-1-midday",
        "campaign_id": "real-backend-herb-test",
        "position": plan["position"],
        "message": "Enter the north grove and meet Renn. You decide how many herbs he brings back.",
        "answers": ["You decide"],
        "active_clarification": linked,
        "party": [{"identity": {"name": "Renn"}, "description": "A capable field gatherer."}],
        "private_background": [],
        "backend_autonomy": True,
    }
    result = BackendLeadResolver(ROOT).resolve(specialist_output, plan=plan, context=context)
    record = result.get("resolution_record") or {}
    resource_changes = record.get("resource_changes", [])
    result_payload = {
        "input": {"plan": plan, "clarification_link": linked, "player_authorization": "You decide"},
        "backend_result": result,
        "quantity_decision": resource_changes,
        "resolver_decided_quantity": bool(resource_changes),
    }
    RESULT_JSON.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    quantity_text = json.dumps(resource_changes, ensure_ascii=False, indent=2)
    markdown = f"""# Real Backend Lead Resolver Herb Test

This run used the configured provider and the real `BackendLeadResolver`.
No herbs-per-phase value was supplied by the test.

## Player Authorization

> You decide

## Backend Plan

Renn is assigned to collect medicinal herbs in the north grove.

## Backend Lead Resolver Result

- **Status:** `{result.get('status')}`
- **Outcome:** {record.get('outcome')}
- **Resource changes:**

```json
{quantity_text}
```

## Assumption Record

```json
{json.dumps(result.get('assumption_record'), ensure_ascii=False, indent=2)}
```

The quantity in this file is the resolver's decision, not a test constant.
"""
    RESULT_MD.write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
