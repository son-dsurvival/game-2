"""Render the complete Lead Resolver output into player-facing narration.

The Lead Resolver is authoritative. The Narrator separates its action
narration, mathematical calculation display, and result narration without
resolving mechanics or adding facts.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any
try:
    from brain.model_gateway import ModelGateway
except ModuleNotFoundError:  # Direct execution: python brain/narrator.py
    from model_gateway import ModelGateway


NARRATOR_SYSTEM = """You are the campaign Narrator.

The complete Lead Resolver output is authoritative. Do not resolve mechanics,
recalculate outcomes, add facts, or turn uncertainty into certainty.

Use exactly one of these templates.

Noncombat:
### TIME
{Day / Phase}
### ACTION NARRATION
{Only what the player attempts}
### CALCULATION
{The Lead Resolver's mechanical calculation}
### RESULT NARRATION
{What the Lead Resolver says actually happens, as book-like prose}
### RESOURCE CHANGE
{Resource changes, or None}

Combat:
### TIME
{Day / Phase}
### PLAYER ACTION NARRATION
{Only what the player attempts}
### OPPONENT ACTION NARRATION
{What the opponent attempts, or Not applicable}
### CALCULATION
{Player roll, Task Value or Reaction Total, modifiers, and comparison}
### RESULT NARRATION
{What the resolved exchange causes, as book-like prose}
### RESOURCE CHANGE
{Resource changes, or None}

The Narrator's job is to turn the Lead Resolver's authoritative result into a
player-facing story, not to repeat an analysis.

ACTION NARRATION should describe the player's action as a scene: setting,
movement, posture, sensory detail, intent, and established character voice.
It may make the attempt vivid, but must not reveal whether it succeeds.

RESULT NARRATION should turn the resolved outcome into a story: describe what
changes, how the scene and characters react, and use natural dialogue when
appropriate. It must follow the Lead Resolver exactly, but should not expose
internal reasoning, evidence gaps, specialist notes, or uncertainty analysis.

CALCULATION must remain concise and mechanical, preferably as short bullets.
Keep story prose in ACTION NARRATION and RESULT NARRATION. Do not put raw
resource dictionaries or implementation notes in either story section.

Use quotation marks for spoken dialogue. Keep character voice specific to the
supplied guidance. Action narration must not reveal the result. Result narration
must not change the Lead Resolver's outcome. Calculations must copy supplied
values and must never invent a roll or calculation. Do not mention JSON, models,
specialists, evidence, or internal processing. Do not return JSON.
"""


class Narrator:
    def __init__(
        self,
        *,
        host: str | None = None,
        model: str | None = None,
        timeout: float = 180.0,
        rules_path: str | Path = "markdown_files/game rules (1).md",
        backend: str | None = None,
    ):
        self.backend = backend or os.getenv("NARRATOR_BACKEND", "deepseek")
        self.host = (host or os.getenv("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        if model:
            self.model = model
        elif self.backend == "deepseek":
            self.model = os.getenv("NARRATOR_DEEPSEEK_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat"))
        else:
            self.model = os.getenv("NARRATOR_MODEL", os.getenv("OLLAMA_MODEL", "tinydolphin"))
        self.timeout = timeout
        self.rules_path = Path(rules_path).resolve()
        self.repo_root = self.rules_path.parents[1]

    @staticmethod
    def player_input(lead_result: dict[str, Any]) -> dict[str, Any]:
        """Build a fail-closed narration projection; never pass internal output."""
        source = lead_result.get("lead_resolver") if isinstance(lead_result.get("lead_resolver"), dict) else lead_result
        record = source.get("resolution_record", source) if isinstance(source, dict) else {}
        if not isinstance(record, dict):
            return {}
        visible = {"visible", "public", "roleplay_revealed"}
        def safe_list(value: Any) -> list[dict[str, Any]]:
            return [item for item in value if isinstance(item, dict) and str(item.get("roleplay_visibility", item.get("visibility", "hidden"))).casefold() in visible] if isinstance(value, list) else []
        return {
            "turn_id": record.get("turn_id"),
            "status": record.get("status"),
            "outcome": record.get("outcome"),
            "consequences": safe_list(record.get("consequences")),
            "resource_changes": safe_list(record.get("resource_changes")),
            "time_changes": safe_list(record.get("time_changes")),
            "relationship_changes": safe_list(record.get("relationship_changes")),
            "visibility": record.get("visibility") if isinstance(record.get("visibility"), dict) else {},
            "narrative_packet": record.get("narrative_packet") if isinstance(record.get("narrative_packet"), dict) else {},
        }

    def render(self, lead_result: dict[str, Any]) -> dict[str, Any]:
        facts = self.player_input(lead_result)
        narration, source = self._call_model(facts)
        return {
            "turn_id": facts.get("turn_id"),
            "status": "rendered",
            "narration": narration,
            "source": source,
            "backend": self.backend,
            "model": self.model,
        }

    def _build_prompt(self, facts: dict[str, Any]) -> str:
        rules = self._read_narration_rules()
        return (
            "Apply the narration rules below to the complete Lead Resolver output. "
            "Choose the noncombat or combat template from the complete Lead Resolver output. "
            "Return only the player-facing scene and use the exact headings from that template. "
            "Action Narration must add vivid but evidence-grounded scene description to the player's "
            "attempt without revealing its result. Result Narration must turn the Lead Resolver's outcome "
            "into natural story prose with scene changes, reactions, and dialogue where supported. Keep "
            "raw mechanics and resource dictionaries out of both story sections. Calculations show only "
            "the supplied mechanical values, including Task Value or Reaction Total when present, as concise "
            "bullets. Do not copy internal notes, conflict traces, evidence gaps, or specialist analysis into "
            "the player-facing story. Do not add facts, rolls, costs, reactions, or consequences.\n\n"
            "NARRATION RULES FROM game rules (1).md:\n"
            + rules
            + "\n\nCOMPLETE LEAD RESOLVER OUTPUT:\n"
            + json.dumps(facts, ensure_ascii=False, indent=2)
            + "\n\nPLAYER-FACING SCENE:\n"
        )

    def _call_model(self, facts: dict[str, Any]) -> tuple[str, str]:
        if self.backend == "deepseek":
            return self._call_deepseek(facts)
        if self.backend == "ollama":
            return self._call_ollama(facts)
        raise RuntimeError(f"Unsupported narrator backend: {self.backend}")

    def _call_ollama(self, facts: dict[str, Any]) -> tuple[str, str]:
        return self._gateway_narration(facts, provider="ollama")

    def _call_deepseek(self, facts: dict[str, Any]) -> tuple[str, str]:
        return self._gateway_narration(facts, provider="deepseek")

    def _gateway_narration(self, facts: dict[str, Any], *, provider: str) -> tuple[str, str]:
        content = ModelGateway(self.repo_root).complete(
            stage="narrator",
            request_id=str(facts.get("turn_id", "")) or None,
            provider=provider,
            model=self.model,
            temperature=0.4 if provider == "deepseek" else 0.2,
            timeout=self.timeout,
            ollama_host=self.host if provider == "ollama" else None,
            messages=[
                {"role": "system", "content": NARRATOR_SYSTEM + "\n\n" + self._read_narration_rules()},
                {"role": "user", "content": self._build_prompt(facts)},
            ],
        ).content.strip()
        # A structured echo is not narration and risks exposing internal data.
        if self._looks_like_structured_echo(content):
            return self._safe_fallback(facts), "lead_resolver_fallback"
        return content, provider

    def _read_narration_rules(self) -> str:
        try:
            text = self.rules_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"Narration rules file could not be read: {self.rules_path}: {exc}") from exc
        start = text.find("## VII. NARRATION SYSTEM")
        end = text.find("## VIII. OUTPUT TEMPLATE (ENFORCED)", start)
        if start < 0 or end < 0:
            raise RuntimeError("Could not locate the NARRATION SYSTEM section in the rules file")
        template_end = text.find("## VII. NPC AUTONOMY SYSTEM", end)
        if template_end < 0:
            template_end = min(len(text), end + 5000)
        return (text[start:template_end]).strip()

    @staticmethod
    def _opening_sentence(facts: dict[str, Any]) -> str:
        outcome = facts.get("outcome")
        if isinstance(outcome, dict):
            summary = str(outcome.get("summary", "")).strip()
        else:
            summary = str(outcome or "").strip()
        if not summary:
            return "The turn unfolds as resolved."
        for marker in (". ", "! ", "? "):
            if marker in summary:
                return summary.split(marker, 1)[0] + marker[0]
        return summary[:240].rstrip(" ,;:") + "."

    @staticmethod
    def _looks_like_structured_echo(content: str) -> bool:
        lowered = content.lower()
        headings = (
            "### TIME",
            "### CALCULATION",
            "### RESULT NARRATION",
            "### RESOURCE CHANGE",
        )
        has_template = all(heading in content for heading in headings) and (
            "### ACTION NARRATION" in content or "### PLAYER ACTION NARRATION" in content
        )
        return (
            content.startswith("{")
            or '"turn_id"' in lowered
            or '"business_result"' in lowered
            or '"resource_changes"' in lowered
            or '"time_changes"' in lowered
            or "authoritative facts:" in lowered
            or "narration rules" in lowered
            or "specialists" in lowered
            or "evidence" in lowered
            or len(content) > 4000
            or not has_template
        )

    @staticmethod
    def _safe_fallback(facts: dict[str, Any]) -> str:
        resolution = facts.get("resolution_record")
        if not isinstance(resolution, dict):
            resolution = facts
        time_changes = resolution.get("time_changes", [])
        day_phase = "Not specified"
        if time_changes and isinstance(time_changes[0], dict):
            item = time_changes[0]
            day = item.get("day", "?")
            phase = item.get("phase", "?")
            day_phase = f"Day {day} — {phase}"

        actions = resolution.get("player_action", [])
        locked = resolution.get("locked_calculation", {})
        if not actions and isinstance(locked, dict):
            actions = locked.get("action_frames", [])
        action_lines = []
        for action in actions:
            if not isinstance(action, dict):
                continue
            actor = action.get("actor", "The player")
            intent = action.get("intent", "acts")
            target = action.get("target")
            method = action.get("method")
            sentence = f"{actor} {intent}"
            if target:
                sentence += f" with {target}"
            if method and method not in str(intent):
                sentence += f" by {method}"
            action_lines.append(sentence.rstrip(".") + ".")

        packet = resolution.get("narrative_packet", {})
        packet_action = packet.get("action_summary") if isinstance(packet, dict) else None
        if packet_action:
            action_lines = [str(packet_action)]
        scene_context = packet.get("scene_context") if isinstance(packet, dict) else None
        if scene_context and action_lines:
            action_lines.insert(0, str(scene_context).strip())

        outcome = resolution.get("outcome", {})
        if isinstance(outcome, dict):
            result_parts = [outcome.get("summary"), outcome.get("npc_reaction")]
            business = outcome.get("business_result")
            if business and str(business).lower() != "none":
                result_parts.append(business)
        else:
            result_parts = [outcome]
        result_text = " ".join(str(part).strip() for part in result_parts if part not in (None, ""))
        if not action_lines:
            action_lines.append("The resolved action begins.")

        calculations = "No dice roll was required." if resolution.get("status", facts.get("status")) == "resolved" else "The resolution is not complete."
        consequences = resolution.get("consequences", [])
        visible = [
            str(item)
            for item in consequences
            if "autonomy action register" not in str(item).lower()
            and "reset rule" not in str(item).lower()
        ]
        result_block = " ".join(visible) if visible else result_text
        result_story = result_block or "The resolved result takes shape."
        resources = []
        for field in ("resource_changes", "relationship_changes", "xp_changes"):
            value = resolution.get(field)
            if not isinstance(value, list):
                continue
            for item in value:
                if isinstance(item, dict):
                    label = item.get("resource") or item.get("relationship") or item.get("type") or field
                    delta = item.get("delta", item.get("change", item.get("amount")))
                    reason = item.get("reason") or item.get("note")
                    line = f"{label}: {delta}" if delta is not None else str(label)
                    if reason:
                        line += f" ({reason})"
                    resources.append(line)
                else:
                    resources.append(str(item))
        mode = str(facts.get("mode", resolution.get("mode", ""))).lower()
        combat = mode == "combat" or "opponent" in json.dumps(resolution, ensure_ascii=False).lower()
        locked_text = []
        locked = resolution.get("locked_calculation", {})
        if isinstance(locked, dict):
            for key in ("action_type", "time_cost", "resource_cost", "roll", "player_roll", "task_value", "reaction_total", "outcome", "escalation_triggered"):
                if locked.get(key) not in (None, "", [], {}):
                    locked_text.append(f"{key}: {locked[key]}")
        calculation_text = "\n".join(f"- {line}" for line in locked_text) or f"- {calculations}"
        if combat:
            opponent = resolution.get("opponent_action") or (outcome.get("opponent_action") if isinstance(outcome, dict) else None) or "Not applicable."
            return (
                f"### TIME\n{day_phase}\n\n"
                "### PLAYER ACTION NARRATION\n" + " ".join(action_lines) + "\n\n"
                "### OPPONENT ACTION NARRATION\n" + str(opponent) + "\n\n"
                "### CALCULATION\n" + calculation_text + "\n\n"
                "### RESULT NARRATION\n" + result_story + "\n\n"
                "### RESOURCE CHANGE\n" + (" ".join(resources) if resources else "None")
            )
        return (
            f"### TIME\n{day_phase}\n\n"
            "### ACTION NARRATION\n" + " ".join(action_lines) + "\n\n"
            "### CALCULATION\n" + calculation_text + "\n\n"
            "### RESULT NARRATION\n" + result_story + "\n\n"
            "### RESOURCE CHANGE\n" + (" ".join(resources) if resources else "None")
        )


def _load_json(path_or_stdin: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path_or_stdin == "-" else Path(path_or_stdin).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("Narrator input must be a JSON object")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a Lead Resolver result with local Ollama")
    parser.add_argument("lead_result", help="Lead Resolver JSON file or '-' for stdin")
    parser.add_argument("--backend", choices=("deepseek", "ollama"), help="Narrator backend; defaults to NARRATOR_BACKEND or deepseek")
    parser.add_argument("--host", help="Ollama host when using --backend ollama")
    parser.add_argument("--model", help="Model override for the selected backend")
    parser.add_argument("--dry-run", action="store_true", help="Print the complete Lead Resolver input without calling the model")
    parser.add_argument("--json", action="store_true", help="Print the structured narrator result instead of plain narration")
    args = parser.parse_args()

    lead_result = _load_json(args.lead_result)
    narrator = Narrator(host=args.host, model=args.model, backend=args.backend)
    if args.dry_run:
        output = narrator.player_input(lead_result)
    else:
        output = narrator.render(lead_result)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.dry_run or args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(output if isinstance(output, str) else output["narration"])


if __name__ == "__main__":
    main()
