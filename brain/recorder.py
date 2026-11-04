"""Session recorder and canon promotion gate.

A second DeepSeek call distills a Lead Resolver result into important facts and
routes each fact to an exact Markdown file/heading from the section index.
During play, and at day end, this recorder writes only to TEMP_MEMORY.md.
Day-end promotion is returned as an admin proposal; the separate Admin Editor
must apply any approved changes to other Markdown files.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any
from brain.persistence import atomic_text

try:
    from brain.build_canon_section_index import build_index
    from brain.model_gateway import ModelGateway
except ModuleNotFoundError:  # Direct execution: python brain/recorder.py
    from build_canon_section_index import build_index
    from model_gateway import ModelGateway

START_MARKER = "<!-- recorder:"
END_MARKER = "<!-- /recorder:"
EVENT_LOG = "markdown_files/🌍 CORE WORLD FRAME (REFINED).md"
TEMP_MEMORY = "markdown_files/TEMP_MEMORY.md"


class SessionRecorder:
    def __init__(
        self,
        repo_root: str | Path = ".",
        *,
        temp_memory_path: str | Path = "markdown_files/TEMP_MEMORY.md",
        event_log_path: str | Path = EVENT_LOG,
        section_index_path: str | Path = "brain/info/canon_section_index.json",
    ):
        root = Path(repo_root).resolve()
        self.root = root
        self.temp_memory_path = (root / temp_memory_path).resolve()
        self.event_log_path = (root / event_log_path).resolve()
        self.section_index_path = (root / section_index_path).resolve()
        try:
            loaded_index = json.loads(self.section_index_path.read_text(encoding="utf-8"))
            self.section_index = loaded_index if isinstance(loaded_index, dict) else build_index(root)
        except (OSError, json.JSONDecodeError):
            # Generated indexes may not exist yet (or may be empty in a fresh
            # checkout). Recording structured state must still work.
            self.section_index = build_index(root)

    def record(self, lead_result: dict[str, Any]) -> dict[str, Any]:
        source = self._lead_output(lead_result)
        resolution = source.get("resolution_record", source)
        turn_id = str(source.get("turn_id", resolution.get("turn_id", "unknown-turn")))
        content = self.temp_memory_path.read_text(encoding='utf-8')
        input_hash = hashlib.sha256(json.dumps(source, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        previous = next((item for item in self._pending_records(content, day=None) if item.get('turn_id') == turn_id), None)
        if previous:
            if previous.get('input_hash') and previous['input_hash'] != input_hash:
                raise RuntimeError('Recorded turn identity cannot be reused for different facts.')
            return {**previous, 'status': 'already_recorded', 'source': str(self.temp_memory_path)}
        day, phase = self._day_phase(source)
        plan = self._plan_with_deepseek(source)
        segments = self._validate_plan(plan, turn_id)
        resource_commit = self._resource_commit(source)
        state_updates = self._state_updates(resource_commit)
        modifier_updates = self._modifier_updates(source)
        branch_updates = self._branch_updates(source)
        # LeadResolver wraps ordinary output in resolution_record; normalize
        # the cache delta from that canonical layer before recording it.
        cache_delta = source.get("cache_delta")
        if not isinstance(cache_delta, dict) and isinstance(resolution, dict):
            cache_delta = resolution.get("cache_delta")
        if not isinstance(cache_delta, dict):
            cache_delta = None
        content = self.temp_memory_path.read_text(encoding="utf-8")
        previous_records = self._pending_records(content, day=None)
        record = {
            "commit_id": f"commit-{turn_id}",
            'input_hash': input_hash,
            "parent_commit": previous_records[-1].get("commit_id") if previous_records else None,
            "turn_id": turn_id,
            "day": day,
            "phase": phase,
            "promotion_status": "pending" if source.get("status", resolution.get("status")) == "resolved" else "not_promotable",
            "summary": plan["summary"],
            "resource_commit": resource_commit,
            "state_updates": state_updates,
            "modifier_updates": modifier_updates,
            "branch_updates": branch_updates,
            "cache_delta": cache_delta,
            "target_segments": segments,
        }
        if f"{START_MARKER}{turn_id} -->" in content:
            raise RuntimeError(f"Turn is already recorded in TEMP_MEMORY.md: {turn_id}")
        block = self._record_block(record)
        marker = "## Pending Session Canon"
        position = content.find(marker)
        if position < 0:
            content = content.rstrip() + "\n\n" + marker + "\n"
            position = content.find(marker)
        insert_at = content.find("\n", position)
        if insert_at < 0:
            insert_at = len(content)
        content = content[:insert_at + 1] + "\n" + block + content[insert_at + 1:]
        content = self._update_session_resource_ledger(content)
        content = self._update_session_modifier_ledger(content)
        content = self._update_pending_branch_registry(content)
        content = self._update_session_position(content, record["day"], record["phase"])
        atomic_text(self.temp_memory_path, content)
        return {
            "status": "recorded",
            "turn_id": turn_id,
            "day": day,
            "phase": phase,
            "promotion_status": record["promotion_status"],
            "summary": record["summary"],
            "commit_id": record["commit_id"],
            "resource_commit": record["resource_commit"],
            "state_updates": state_updates,
            "modifier_updates": modifier_updates,
            "branch_updates": branch_updates,
            "target_segments": segments,
            "cache_delta": cache_delta,
            "source": str(self.temp_memory_path),
        }

    def pending_records(self, *, day: int | None = None) -> list[dict[str, Any]]:
        content = self.temp_memory_path.read_text(encoding='utf-8')
        return [item for item in self._pending_records(content, day=day) if item.get('promotion_status') == 'pending']

    def mark_promoted(self, turn_ids: list[str]) -> None:
        content = self.temp_memory_path.read_text(encoding='utf-8')
        content = self._mark_promoted(content, set(turn_ids))
        atomic_text(self.temp_memory_path, content)

    def record_background_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        """Persist a resolved background tick in Experimentation Register.md.

        Background resolution is separate from player-facing narration and is
        kept with experiments and off-screen turns, using idempotent tick IDs.
        """
        try:
            from backend.background_state import BackgroundStateStore
        except ModuleNotFoundError:  # Direct execution from the brain folder.
            from ..backend.background_state import BackgroundStateStore
        return BackgroundStateStore(self.root / "markdown_files" / "Experimentation Register.md").commit_tick(tick)

    def day_end(self, *, day: int | None = None, decision: str = "ask") -> dict[str, Any]:
        content = self.temp_memory_path.read_text(encoding="utf-8")
        records = self._pending_records(content, day=day)
        promotable = [r for r in records if r.get("promotion_status") == "pending"]
        if not promotable:
            return {"status": "nothing_to_promote", "day": day, "records": len(records), "promotable": 0}

        proposal = self._promotion_proposal(promotable)
        if decision == "ask":
            print(proposal)
            approved = input("Promote these records to the Markdown canon files? [y/N]: ").strip().lower() in {"y", "yes"}
        elif decision == "approve":
            approved = True
        elif decision == "reject":
            approved = False
        else:
            raise ValueError(f"Unknown decision: {decision}")
        if not approved:
            return {
                "status": "promotion_pending",
                "day": day,
                "records": len(records),
                "promotable": len(promotable),
                "files_changed": [],
            }

        # The Recorder never applies canon or registry changes. It hands the
        # readable proposal to the outside-game Admin Editor, which has its own
        # approval and audit boundary.
        return {
            "status": "promotion_ready_for_admin_editor",
            "day": day,
            "records": len(records),
            "promotable": len(promotable),
            "files_changed": [],
            "promotion_proposal": proposal,
            "next_step": "Submit the approved proposal to outside game/admin_editor.py.",
        }

    def _plan_with_deepseek(self, lead_output: dict[str, Any]) -> dict[str, Any]:
        api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path=self.root / ".env")
            api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")
        except ImportError:
            pass
        if not api_key:
            raise RuntimeError("Recorder requires DEEPSEEK_API_KEY or API_KEY")
        catalog = {
            path: [" > ".join(section["heading_path"]) for section in data.get("sections", [])]
            for path, data in self.section_index.get("files", {}).items()
        }
        prompt = {
            "lead_resolver_output": lead_output,
            "available_markdown_sections": catalog,
        }
        system = """You are the Session Recorder Planner. Read the complete Lead Resolver output,
select only important facts that must persist, summarize them, and route each
fact to the exact Markdown file and heading where it belongs.

Do not invent facts, state changes, or targets. Prefer existing exact heading
paths from available_markdown_sections. A resolved turn must include an event
log segment. Use markdown_files/... paths. TEMP_MEMORY.md is for temporary
session state; other files are proposed canon promotions only.

Return JSON only:
{
  "turn_id": "...",
  "summary": "short session summary",
  "segments": [
    {
      "target_file": "markdown_files/file.md",
      "target_section": "Parent > Exact Heading",
      "importance": "required|important|context",
      "summary": "what belongs there",
      "content": "concise Markdown-safe update",
      "reason": "why this section owns the update",
      "promote_to_canon": true
    }
  ]
}

Do not put player narration in content. Store facts, state changes, unresolved
items, autonomy changes, and canonical event information only."""
        raw = ModelGateway(self.root).complete(
            stage="recorder.plan",
            request_id=str(lead_output.get("turn_id", "")) or None,
            model=os.getenv("RECORDER_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
            json_mode=True,
            timeout=180,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
        ).content
        if not raw:
            raise RuntimeError("Recorder Planner returned an empty response")
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Recorder Planner returned invalid JSON") from exc
        if not isinstance(plan, dict) or not isinstance(plan.get("summary"), str) or not isinstance(plan.get("segments"), list):
            raise RuntimeError("Recorder Planner returned an invalid storage plan")
        return plan

    def _validate_plan(self, plan: dict[str, Any], turn_id: str) -> list[dict[str, Any]]:
        if str(plan.get("turn_id", turn_id)) != turn_id:
            raise RuntimeError("Recorder Planner turn_id does not match Lead Resolver turn_id")
        segments: list[dict[str, Any]] = []
        for item in plan["segments"]:
            if not isinstance(item, dict):
                continue
            target_file = self._normalise_file(str(item.get("target_file", "")))
            target_section = str(item.get("target_section", "")).strip()
            mapping = self._section_mapping(target_file, target_section)
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            if len(content) > 3000:
                content = content[:3000].rstrip() + " …"
            segments.append({
                "file": target_file or "UNMAPPED",
                "section": target_section or "UNMAPPED",
                "mapping": mapping,
                "importance": str(item.get("importance", "important")),
                "summary": str(item.get("summary", content[:240])).strip()[:500],
                "content": content,
                "reason": str(item.get("reason", "")).strip()[:500],
                "promote_to_canon": bool(item.get("promote_to_canon", True)),
            })
        event_file = EVENT_LOG
        if not any(s["file"] == event_file for s in segments):
            segments.append({
                "file": event_file,
                "section": "Event log",
                "mapping": self._section_mapping(event_file, "Event log"),
                "importance": "required",
                "summary": plan["summary"][:500],
                "content": plan["summary"][:2000],
                "reason": "Every resolved turn receives a canonical event entry.",
                "promote_to_canon": True,
            })
        if not segments:
            raise RuntimeError("Recorder Planner produced no storable segments")
        return segments

    @staticmethod
    def _resource_commit(source: dict[str, Any]) -> list[dict[str, Any]]:
        resolution = source.get("resolution_record", source)
        raw = resolution.get("resource_changes", []) if isinstance(resolution, dict) else []
        grouped: dict[str, dict[str, Any]] = {}
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            original = str(item.get("resource", item.get("type", "unspecified resource"))).strip()
            name = original.casefold()
            if "relay" in name or "relay-space" in name:
                canonical = "relay-space mana"
            elif "personal mp" in name or name in {"mp", "mana", "personal mana", "current mp"}:
                canonical = "current MP"
            elif name in {"gold", "money", "cash", "currency"} or " gold" in name:
                canonical = "money"
            elif "sp" == name or name.startswith("sp "):
                canonical = "SP"
            else:
                canonical = original
            entry = grouped.setdefault(canonical, {
                "resource": canonical,
                "delta": None,
                "before": None,
                "after": None,
                "reconciliation": [],
                "unresolved": False,
            })
            delta = item.get("delta", item.get("change"))
            if isinstance(delta, (int, float)) and not isinstance(delta, bool):
                entry["delta"] = (entry["delta"] or 0) + delta
            elif isinstance(delta, str):
                match = re.search(r"[-+]?\d+(?:\.\d+)?", delta.replace(",", ""))
                if match:
                    entry["delta"] = (entry["delta"] or 0) + float(match.group(0))
            for key in ("before", "after"):
                value = item.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    entry[key] = value
                elif value not in (None, ""):
                    entry["unresolved"] = True
                    entry["reconciliation"].append(f"{key}: {value}")
            for key in ("reason", "note"):
                if item.get(key):
                    entry["reconciliation"].append(str(item[key]))
        result = []
        for entry in grouped.values():
            entry["status"] = "resolved" if not entry["unresolved"] and entry["before"] is not None and entry["after"] is not None else "delta_only_requires_reconciliation"
            if not entry["reconciliation"] and entry["status"] != "resolved":
                entry["reconciliation"].append("Absolute current value was not supplied by Lead Resolver.")
            result.append(entry)
        return result

    @staticmethod
    def _state_updates(commits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return only exact post-resolution values for TEMP_MEMORY.

        The recorder never replays the player's prose or asks a model to infer
        balances. Lead Resolver's structured ``after`` value is authoritative.
        """
        updates = []
        for item in commits:
            after = item.get("after")
            if isinstance(after, (int, float)) and not isinstance(after, bool):
                updates.append({"state": item["resource"], "value": after})
        return updates

    @staticmethod
    def _modifier_updates(source: dict[str, Any]) -> list[dict[str, str]]:
        """Extract newly gained modifiers, storing only name and description."""
        resolution = source.get("resolution_record", source)
        raw = resolution.get("modifier_changes", []) if isinstance(resolution, dict) else []
        if not isinstance(raw, list):
            return []
        updates = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            modifier = item.get("modifier", item.get("name"))
            description = item.get("description")
            if not isinstance(modifier, str) or not modifier.strip():
                continue
            if not isinstance(description, str) or not description.strip():
                continue
            updates.append({
                "modifier": modifier.strip(),
                "description": description.strip(),
            })
        return updates

    @staticmethod
    def _branch_updates(source: dict[str, Any]) -> list[dict[str, Any]]:
        """Accept only resolved branch unlocks from the Lead Resolver."""
        resolution = source.get("resolution_record", source)
        raw = resolution.get("branch_changes", []) if isinstance(resolution, dict) else []
        if not isinstance(raw, list):
            return []
        updates = []
        for item in raw:
            if not isinstance(item, dict) or str(item.get("status", "")).casefold() != "unlocked":
                continue
            branch = item.get("branch", item.get("name"))
            specialist = item.get("specialist")
            if not isinstance(branch, str) or not branch.strip() or not isinstance(specialist, str) or not specialist.strip():
                continue
            updates.append({
                "branch": branch.strip(),
                "status": "unlocked",
                "specialist": specialist.strip(),
                "template": str(item.get("template", "none")),
                "activation_tags": [str(tag) for tag in item.get("activation_tags", []) if str(tag).strip()],
                "reason": str(item.get("reason", "Resolved branch establishment.")).strip(),
            })
        return updates

    @staticmethod
    def _resource_commit_markdown(commits: list[dict[str, Any]]) -> str:
        if not commits:
            return "- No resource changes committed.\n"
        lines = []
        for item in commits:
            delta = item.get("delta")
            delta_text = "unknown delta" if delta is None else str(delta)
            line = f"- {item['resource']}: delta {delta_text}"
            if item.get("before") is not None or item.get("after") is not None:
                line += f" (before {item.get('before')}, after {item.get('after')})"
            if item.get("status") != "resolved":
                line += " [reconciliation required]"
            lines.append(line)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _update_session_position(content: str, day: Any, phase: Any) -> str:
        section = (
            "## Current Session Position\n\n"
            f"day: {day}\n"
            f"phase: {phase}\n\n"
            "The phase above is the current position after the latest committed turn. "
            "Turn commits retain their starting and ending phase history.\n"
        )
        match = re.search(r"^## Current Session Position\s*$", content, re.M)
        if match:
            next_section = re.search(r"^##\s+", content[match.end():], re.M)
            end = match.end() + (next_section.start() if next_section else len(content[match.end():]))
            return content[:match.start()] + section + content[end:]
        marker = "## Named Character Autonomy Action Register"
        if marker in content:
            return content.replace(marker, section + "\n" + marker, 1)
        return section + "\n" + content

    def _update_session_resource_ledger(self, content: str) -> str:
        records = self._pending_records(content, day=None)
        latest: dict[str, dict[str, Any]] = {}
        running: dict[str, float] = {}
        for record in records:
            for item in record.get("resource_commit", []):
                name = item.get("resource")
                if not name:
                    continue
                latest[name] = item
                if isinstance(item.get("delta"), (int, float)):
                    running[name] = running.get(name, 0) + item["delta"]
        lines = ["## Session Resource Ledger", "", "This is a consolidated working ledger for the active session. It is not established canon until promotion.", ""]
        if not latest:
            lines.append("- No committed resource changes.")
        else:
            for name, item in latest.items():
                if item.get("after") is not None:
                    # These are the direct, reviewable state assignments the
                    # player asked for: current MP = 95, money = 48, etc.
                    lines.append(f"- {name} = {item['after']}")
                    continue
                line = f"- {name}: latest delta {item.get('delta', 'unknown')}"
                if name in running:
                    line += f"; running session delta {running[name]:g}"
                line += "; absolute value requires reconciliation"
                lines.append(line)
        section = "\n".join(lines) + "\n"
        match = re.search(r"^## Session Resource Ledger\s*$", content, re.M)
        if match:
            next_section = re.search(r"^##\s+", content[match.end():], re.M)
            end = match.end() + (next_section.start() if next_section else len(content[match.end():]))
            return content[:match.start()] + section + content[end:]
        return content.rstrip() + "\n\n" + section

    def _update_session_modifier_ledger(self, content: str) -> str:
        """Maintain a minimal modifier ledger: name and description only."""
        records = self._pending_records(content, day=None)
        latest: dict[str, str] = {}
        for record in records:
            for item in record.get("modifier_updates", []):
                if not isinstance(item, dict):
                    continue
                modifier = item.get("modifier")
                description = item.get("description")
                if isinstance(modifier, str) and isinstance(description, str) and modifier and description:
                    latest[modifier] = description
        if not latest:
            return content
        lines = [
            "## Session Modifier Ledger",
            "",
            "These are session updates and are not established canon until promotion.",
            "",
            *[f"- {modifier}: {description}" for modifier, description in latest.items()],
            "",
        ]
        section = "\n".join(lines)
        match = re.search(r"^## Session Modifier Ledger\s*$", content, re.M)
        if match:
            next_section = re.search(r"^##\s+", content[match.end():], re.M)
            end = match.end() + (next_section.start() if next_section else len(content[match.end():]))
            return content[:match.start()] + section + "\n" + content[end:]
        return content.rstrip() + "\n\n" + section + "\n"

    def _update_pending_branch_registry(self, content: str) -> str:
        records = self._pending_records(content, day=None)
        latest: dict[str, dict[str, Any]] = {}
        for record in records:
            for item in record.get("branch_updates", []):
                if isinstance(item, dict) and item.get("branch"):
                    latest[str(item["branch"])] = item
        if not latest:
            return content
        lines = [
            "## Pending Branch Registry Updates",
            "",
            "Resolved branch unlocks pending promotion to Branch Registry.md.",
            "",
        ]
        for branch, item in latest.items():
            lines.extend([
                f"## {branch}",
                f"status: {item['status']}",
                f"specialist: {item['specialist']}",
                f"template: {item['template']}",
                f"activation tags: {', '.join(item['activation_tags']) or 'none'}",
                f"reason: {item['reason']}",
                "",
            ])
        section = "\n".join(lines)
        match = re.search(r"^## Pending Branch Registry Updates\s*$", content, re.M)
        if match:
            next_section = re.search(r"^##\s+", content[match.end():], re.M)
            end = match.end() + (next_section.start() if next_section else len(content[match.end():]))
            return content[:match.start()] + section + "\n" + content[end:]
        return content.rstrip() + "\n\n" + section + "\n"

    def _normalise_file(self, value: str) -> str:
        value = value.replace("\\", "/").strip()
        for path in self.section_index.get("files", {}):
            if value.casefold() in {path.casefold(), Path(path).name.casefold(), (self.root / path).as_posix().casefold()}:
                return path
        return value

    def _section_mapping(self, file_path: str, section_path: str) -> str:
        data = self.section_index.get("files", {}).get(file_path)
        if not data:
            return "unmapped_target_file"
        wanted = re.sub(r"\s+", " ", section_path).strip().casefold()
        for section in data.get("sections", []):
            actual = " > ".join(section["heading_path"])
            if actual.casefold() == wanted or section["heading"].casefold() == wanted:
                return "mapped"
        if file_path == EVENT_LOG and wanted.startswith("event log >"):
            return "mapped"
        return "file_mapped_section_unresolved"

    @staticmethod
    def _lead_output(lead_result: dict[str, Any]) -> dict[str, Any]:
        nested = lead_result.get("lead_resolver")
        return nested if isinstance(nested, dict) else lead_result

    @staticmethod
    def _day_phase(source: dict[str, Any]) -> tuple[int | None, str | None]:
        position = source.get('position')
        if isinstance(position, dict) and position.get('day') is not None:
            return int(position['day']), position.get('phase')
        resolution = source.get("resolution_record", source)
        changes = resolution.get("time_changes", []) if isinstance(resolution, dict) else []
        if isinstance(changes, list) and changes and isinstance(changes[0], dict):
            day = changes[0].get("day")
            phase = changes[0].get("phase")
            if day is not None or phase is not None:
                try:
                    day = int(day) if day is not None else None
                except (TypeError, ValueError):
                    day = None
                return day, phase
        text = json.dumps(resolution, ensure_ascii=False)
        matches = [int(value) for value in re.findall(r"\bDay\s+(\d+)\b", text, re.I)]
        return (max(matches) if matches else None), None

    @staticmethod
    def _record_block(record: dict[str, Any]) -> str:
        def one_line(value: Any) -> str:
            return re.sub(r"\s+", " ", str(value)).strip()

        lines = [
            f"{START_MARKER}{record['turn_id']} -->",
            f"### Recorded Turn — {record['turn_id']}",
            f"day: {record['day']}",
            f"phase: {record['phase']}",
            f"promotion_status: {record['promotion_status']}",
            f"summary: {one_line(record['summary'])}",
            f"commit_id: {record['commit_id']}",
            f"input_hash: {record.get('input_hash', '')}",
            f"parent_commit: {record.get('parent_commit')}",
            "",
            "### State Updates",
        ]
        state_updates = record.get("state_updates", [])
        lines.extend(
            f"- {one_line(item['state'])} = {one_line(item['value'])}"
            for item in state_updates
        )
        if not state_updates:
            lines.append("- No exact state updates.")
        lines.extend(["", "### Resource Commit"])
        resource_commit = record.get("resource_commit", [])
        for item in resource_commit:
            lines.append(
                f"- {one_line(item['resource'])}: before {one_line(item.get('before'))}; "
                f"delta {one_line(item.get('delta'))}; after {one_line(item.get('after'))}; "
                f"status {one_line(item.get('status'))}"
            )
        if not resource_commit:
            lines.append("- No resource changes committed.")
        lines.extend(["", "### New Modifiers"])
        modifier_updates = record.get("modifier_updates", [])
        lines.extend(
            f"- {one_line(item['modifier'])}: {one_line(item['description'])}"
            for item in modifier_updates
        )
        if not modifier_updates:
            lines.append("- None.")
        lines.extend(["", "### Branch Registry Updates"])
        branch_updates = record.get("branch_updates", [])
        for item in branch_updates:
            lines.append(
                f"- {one_line(item['branch'])}: status {one_line(item['status'])}; "
                f"specialist {one_line(item['specialist'])}; template {one_line(item['template'])}; "
                f"activation tags {one_line(', '.join(item.get('activation_tags', [])))}; "
                f"reason {one_line(item['reason'])}"
            )
        if not branch_updates:
            lines.append("- None.")
        lines.extend(["", "### Game Cache Delta"])
        cache_delta = record.get("cache_delta")
        cache_fields = (
            "durable_facts", "active_threads", "pending_commitments",
            "unresolved_questions", "expiring_facts",
        )
        if isinstance(cache_delta, dict):
            for field in cache_fields:
                entries = cache_delta.get(field, [])
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if isinstance(entry, dict):
                        value = entry.get("fact", entry.get("thread", entry.get("commitment", entry.get("question", ""))))
                        source_turn = entry.get("source_turn", entry.get("source", "unknown"))
                        status = entry.get("status", "active")
                        if value:
                            lines.append(f"- {field}: {one_line(value)}; status {one_line(status)}; source {one_line(source_turn)}")
                    elif entry:
                        lines.append(f"- {field}: {one_line(entry)}")
        if not any(line.startswith("- ") for line in lines[lines.index("### Game Cache Delta") + 1:]):
            lines.append("- No cache changes.")
        lines.extend(["", "### Target Updates"])
        for segment in record["target_segments"]:
            lines.extend([
                f"- file: {one_line(segment['file'])}",
                f"- section: {one_line(segment['section'])}",
                f"- mapping: {one_line(segment['mapping'])}",
                f"- importance: {one_line(segment['importance'])}",
                f"- summary: {one_line(segment['summary'])}",
                f"- pending content: {one_line(segment['content'])}",
                "",
            ])
        lines.append(f"{END_MARKER}{record['turn_id']} -->")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _pending_records(content: str, *, day: int | None) -> list[dict[str, Any]]:
        pattern = re.compile(
            re.escape(START_MARKER) + r"(?P<id>[^ ]+) -->\n(?P<body>.*?)\n"
            + re.escape(END_MARKER) + r"(?P=id) -->",
            re.S,
        )
        records = []
        for match in pattern.finditer(content):
            body = match.group("body")
            # Read old recorder blocks during migration, but all new blocks are
            # plain Markdown fields and lists.
            json_match = re.search(r"```json\n(.*?)\n```", body, re.S)
            if json_match:
                try:
                    record = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    continue
            else:
                record = SessionRecorder._parse_readable_record(match.group("id"), body)
            if day is None or record.get("day") == day:
                records.append(record)
        return records

    @staticmethod
    def _parse_readable_record(turn_id: str, body: str) -> dict[str, Any]:
        def value(raw: str) -> Any:
            text = raw.strip()
            if text.casefold() in {"none", "null", "unknown", ""}:
                return None if text.casefold() != "unknown" else "unknown"
            try:
                return int(text)
            except ValueError:
                try:
                    return float(text)
                except ValueError:
                    return text

        record: dict[str, Any] = {
            "turn_id": turn_id,
            "resource_commit": [],
            "state_updates": [],
            "modifier_updates": [],
            "branch_updates": [],
            "cache_delta": {
                "durable_facts": [], "active_threads": [], "pending_commitments": [],
                "unresolved_questions": [], "expiring_facts": [],
            },
            "target_segments": [],
        }
        section = ""
        target: dict[str, Any] | None = None
        for line in body.splitlines():
            heading = re.match(r"^###\s+(.+?)\s*$", line)
            if heading:
                section = heading.group(1).casefold()
                continue
            field = re.match(r"^(day|phase|promotion_status|summary|commit_id|parent_commit|input_hash):\s*(.*)$", line)
            if field:
                key, raw = field.groups()
                record[key] = value(raw)
                continue
            if section == "state updates":
                match = re.match(r"^-\s+(.+?)\s*=\s*(.+)$", line)
                if match and not match.group(1).casefold().startswith("no exact"):
                    record["state_updates"].append({"state": match.group(1).strip(), "value": value(match.group(2))})
            elif section == "resource commit":
                match = re.match(r"^-\s+(.+?):\s+before\s+(.+?);\s+delta\s+(.+?);\s+after\s+(.+?);\s+status\s+(.+)$", line)
                if match and not match.group(1).casefold().startswith("no resource"):
                    resource, before, delta, after, status = match.groups()
                    record["resource_commit"].append({
                        "resource": resource.strip(), "before": value(before), "delta": value(delta),
                        "after": value(after), "status": status.strip(), "unresolved": status.strip() != "resolved",
                        "reconciliation": [],
                    })
            elif section == "new modifiers":
                match = re.match(r"^-\s+([^:]+):\s*(.+)$", line)
                if match and match.group(1).strip().casefold() != "none":
                    record["modifier_updates"].append({"modifier": match.group(1).strip(), "description": match.group(2).strip()})
            elif section == "game cache delta":
                match = re.match(r"^-\s+(durable_facts|active_threads|pending_commitments|unresolved_questions|expiring_facts):\s+(.+?)(?:;\s+status\s+(.+?))?(?:;\s+source\s+(.+))?$", line)
                if match:
                    field, text, status, source = match.groups()
                    key = {"durable_facts": "fact", "active_threads": "thread", "pending_commitments": "commitment", "unresolved_questions": "question", "expiring_facts": "fact"}[field]
                    record["cache_delta"][field].append({key: text.strip(), "status": (status or "active").strip(), "source_turn": (source or "unknown").strip()})
            elif section == "branch registry updates":
                match = re.match(r"^-\s+(.+?):\s+status\s+(.+?);\s+specialist\s+(.+?);\s+template\s+(.+?);\s+activation tags\s+(.+?);\s+reason\s+(.+)$", line)
                if match:
                    branch, status, specialist, template, tags, reason = match.groups()
                    if branch.strip().casefold() != "none":
                        record["branch_updates"].append({
                            "branch": branch.strip(), "status": status.strip(), "specialist": specialist.strip(),
                            "template": template.strip(), "activation_tags": [item.strip() for item in tags.split(",") if item.strip()],
                            "reason": reason.strip(),
                        })
            elif section == "target updates":
                match = re.match(r"^-\s+(file|section|mapping|importance|summary|pending content):\s*(.*)$", line)
                if match:
                    key, raw = match.groups()
                    if key == "file":
                        if target:
                            record["target_segments"].append(target)
                        target = {"file": raw.strip()}
                    elif target is not None:
                        target[key if key != "pending content" else "content"] = raw.strip()
        if target:
            record["target_segments"].append(target)
        if isinstance(record.get("day"), str):
            try:
                record["day"] = int(record["day"])
            except ValueError:
                pass
        return record

    @staticmethod
    def _promotion_proposal(records: list[dict[str, Any]]) -> str:
        lines = ["\nCANON PROMOTION PROPOSAL", "The following summarized updates are proposed for the mapped sections:\n"]
        for record in records:
            lines.append(f"- {record['turn_id']} (Day {record.get('day')}, {record.get('phase')}): {record['summary']}")
            for segment in record.get("target_segments", []):
                lines.append(f"  - {segment['file']} :: {segment['section']} [{segment['mapping']}] — {segment['content']}")
        return "\n".join(lines) + "\n"

    def _promote_branch_registry(self, records: list[dict[str, Any]]) -> list[str]:
        # Canonical promotion belongs to outside game/admin_editor.py.
        return []
        updates = {
            str(item.get("branch")): item
            for record in records
            for item in record.get("branch_updates", [])
            if isinstance(item, dict) and item.get("branch")
        }
        if not updates:
            return []
        path = self.root / "markdown_files" / "Branch Registry.md"
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []
        for branch, item in updates.items():
            title = branch.replace("_", " ").title()
            replacement = "\n".join([
                f"## {title}",
                f"status: {item.get('status', 'unlocked')}",
                f"specialist: {item.get('specialist', branch)}",
                f"template: {item.get('template', 'none')}",
                f"activation tags: {', '.join(item.get('activation_tags', [])) or 'none'}",
                f"reason: {item.get('reason', '')}",
                "",
            ])
            match = re.search(rf"^##\s+{re.escape(title)}\s*$", content, re.M | re.I)
            if match:
                next_heading = re.search(r"^##\s+", content[match.end():], re.M)
                end = match.end() + (next_heading.start() if next_heading else len(content[match.end():]))
                content = content[:match.start()] + replacement + content[end:]
            else:
                unlock_rules = re.search(r"^##\s+Unlock Rules\s*$", content, re.M | re.I)
                if unlock_rules:
                    content = content[:unlock_rules.start()] + replacement + "\n" + content[unlock_rules.start():]
                else:
                    content = content.rstrip() + "\n\n" + replacement
        path.write_text(content.rstrip() + "\n", encoding="utf-8")
        return ["markdown_files/Branch Registry.md"]

    def _promote_to_markdown(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        # Kept as a compatibility stub; SessionRecorder is TEMP_MEMORY-only.
        return {
            "files_changed": [],
            "unapplied_segments": [
                {"turn_id": record.get("turn_id"), "reason": "Use outside game/admin_editor.py."}
                for record in records
            ],
        }
        changed: set[str] = set()
        unapplied: list[dict[str, Any]] = []
        event_records: list[dict[str, Any]] = []
        for record in records:
            for segment in record.get("target_segments", []):
                if not segment.get("promote_to_canon") or segment.get("mapping") != "mapped":
                    unapplied.append({"turn_id": record["turn_id"], "segment": segment})
                    continue
                if segment["file"] == EVENT_LOG:
                    event_records.append({"record": record, "segment": segment})
                elif segment["file"] != TEMP_MEMORY:
                    if self._insert_into_section(segment["file"], segment["section"], record["turn_id"], segment["content"]):
                        changed.add(segment["file"])
                    else:
                        unapplied.append({"turn_id": record["turn_id"], "segment": segment})
        if event_records:
            self._append_event_segments(event_records)
            changed.add(self.event_log_path.relative_to(self.root).as_posix())
        return {"files_changed": sorted(changed), "unapplied_segments": unapplied}

    def _insert_into_section(self, relative: str, section_path: str, turn_id: str, content: str) -> bool:
        raise RuntimeError("SessionRecorder is TEMP_MEMORY-only; use outside game/admin_editor.py.")
        path = self.root / relative
        if not path.exists():
            return False
        lines = path.read_text(encoding="utf-8").splitlines()
        index = build_index(self.root)["files"].get(relative, {}).get("sections", [])
        section = next((s for s in index if " > ".join(s["heading_path"]) == section_path), None)
        if not section:
            return False
        insertion = [f"- Session update ({turn_id}): {line.lstrip('- ').strip()}" for line in content.splitlines() if line.strip()]
        lines[section["line_end"]:section["line_end"]] = insertion + [""]
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return True

    def _append_event_segments(self, entries: list[dict[str, Any]]) -> None:
        raise RuntimeError("SessionRecorder is TEMP_MEMORY-only; use outside game/admin_editor.py.")
        path = self.event_log_path
        content = path.read_text(encoding="utf-8")
        grouped: dict[int | None, list[dict[str, Any]]] = {}
        for entry in entries:
            grouped.setdefault(entry["record"].get("day"), []).append(entry)
        for day, day_entries in grouped.items():
            heading = f"### Day {day}" if day is not None else "### Session Promotion"
            block = "\n".join(
                f"- **Recorded turn {entry['record']['turn_id']}:** {entry['segment']['content']}"
                for entry in day_entries
            ) + "\n"
            match = re.search(rf"^### Day {re.escape(str(day))}\s*$", content, re.M) if day is not None else None
            if match:
                next_heading = re.search(r"^### Day \d+\s*$", content[match.end():], re.M)
                insert = match.end() + (next_heading.start() if next_heading else len(content[match.end():]))
                content = content[:insert].rstrip() + "\n\n" + block + content[insert:]
            else:
                content = content.rstrip() + f"\n\n{heading}\n\n{block}"
        path.write_text(content.rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def _mark_promoted(content: str, turn_ids: set[str]) -> str:
        for turn_id in turn_ids:
            start = f"{START_MARKER}{turn_id} -->"
            end = f"{END_MARKER}{turn_id} -->"
            left = content.find(start)
            right = content.find(end, left)
            if left < 0 or right < 0:
                continue
            segment = content[left:right]
            segment = re.sub(r"promotion_status: pending", "promotion_status: promoted", segment, count=1)
            content = content[:left] + segment + content[right:]
        return content


def _load_json(path: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise SystemExit("Recorder input must be a JSON object")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Lead Resolver output and gate canon promotion")
    parser.add_argument("lead_result", nargs="?", help="Lead Resolver JSON file, or '-' for stdin")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--day-end", action="store_true")
    parser.add_argument("--day", type=int)
    parser.add_argument("--decision", choices=("ask", "approve", "reject"), default="ask")
    parser.add_argument("--temp-memory", default="markdown_files/TEMP_MEMORY.md")
    parser.add_argument("--event-log", default=EVENT_LOG)
    parser.add_argument("--section-index", default="brain/info/canon_section_index.json")
    args = parser.parse_args()
    if args.record == args.day_end:
        parser.error("choose exactly one of --record or --day-end")
    recorder = SessionRecorder(".", temp_memory_path=args.temp_memory, event_log_path=args.event_log, section_index_path=args.section_index)
    result = recorder.record(_load_json(args.lead_result)) if args.record else recorder.day_end(day=args.day, decision=args.decision)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
