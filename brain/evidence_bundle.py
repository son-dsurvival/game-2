"""Select indexed evidence references for a routed turn.

This module does not read campaign Markdown sections. It accepts an existing Turn
Router record, uses the evidence index descriptions to select relevant section
references, and freezes those references for specialists to inspect later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from brain.model_gateway import ModelGateway
    from brain.turn_router import RoutingRecord
except ModuleNotFoundError:  # Direct execution: python brain/evidence_bundle.py
    from model_gateway import ModelGateway
    from turn_router import RoutingRecord


ACTION_FRAME_PROMPT = """You are the Action Frame Extractor for a tabletop campaign.

Return JSON only:
{
  "actions": [
    {
      "actor": {"name": "...", "kind": "character"},
      "intent": "what the actor wants to do",
      "target": {"name": "...", "kind": "object|character|location|system|unknown", "specific_evidence_required": true},
      "method": "how the actor plans to do it",
      "participants": [
        {"name": "...", "role": "helper|companion|opponent|other", "specific_evidence_required": true}
      ],
      "ambiguities": []
    }
  ],
  "evidence_gaps": []
}

Separate every declared action. Preserve names exactly as written. Do not invent
participants, targets, methods, rules, outcomes, or consequences. Set
specific_evidence_required to true when a named or campaign-specific person,
object, location, or system needs its own state; set it false for a generic noun.
This step extracts intent only and does not select evidence sections.
"""


SELECTOR_PROMPT = """You are the Evidence Section Selector for a tabletop campaign.

Select indexed evidence sections that specialists should read. You are given a
player prompt, a Turn Router record, and candidate entries from an evidence
index. Use only the candidate IDs. Do not read or invent files, headings, line
ranges, facts, outcomes, costs, or consequences. Do not resolve the turn.

Return JSON only:
{
  "sections": [
    {"id": "candidate-id", "reason": "why this section is relevant"}
  ],
  "evidence_gaps": [
    {"request": "...", "reason": "why no candidate is sufficient"}
  ]
}

Use the action frames to keep evidence entity-specific. Never substitute a
section about another named person or object. If a needed entity-specific
section is absent from the candidates, report an evidence gap. Select every
section needed by the prompt and routed tags, including sections
that explain NPC autonomy, resources, time, rules, canon, or experimentation.
Prefer specific sections over broad parent sections. Select no more than 12
additional semantic sections unless a larger set is clearly necessary. Multiple
sections may be selected. Reasons must be short and grounded in the supplied
descriptions. Keep each reason under 20 words and keep the complete response
compact.
"""


@dataclass(frozen=True)
class SelectedSection:
    section_id: str
    name: str
    description: str
    source: str
    location: str
    path: tuple[str, ...]
    selected_by: tuple[str, ...]
    reasons: tuple[str, ...]
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.section_id,
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "location": self.location,
            "path": list(self.path),
            "selected_by": list(self.selected_by),
            "reasons": list(self.reasons),
            "text": self.text,
        }


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    turn_id: str
    source_snapshot: dict[str, Any]
    player_input: dict[str, Any]
    current_state: dict[str, Any]
    action_frames: tuple[dict[str, Any], ...]
    selected_sections: tuple[SelectedSection, ...]
    evidence_gaps: tuple[dict[str, Any], ...]
    selection_source: str
    expansion_note: str | None = None
    specialist_bundles: dict[str, dict[str, Any]] | None = None
    admin_sources: tuple[dict[str, Any], ...] = ()
    bundle_status: str = "frozen"
    conversation_history: Any = None
    history_breakdown: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "turn_id": self.turn_id,
            "source_snapshot": self.source_snapshot,
            "player_input": self.player_input,
            "current_state": self.current_state,
            "action_frames": list(self.action_frames),
            "selected_sections": [item.to_dict() for item in self.selected_sections],
            "evidence_gaps": list(self.evidence_gaps),
            "selection_source": self.selection_source,
            "expansion_note": self.expansion_note,
            "specialist_bundles": self.specialist_bundles or {},
            "admin_sources": list(self.admin_sources),
            "bundle_status": self.bundle_status,
            "conversation_history": self.conversation_history,
            "history_breakdown": list(self.history_breakdown),
        }


class EvidenceBundleBuilder:
    """Select evidence references without reading campaign Markdown content."""

    def __init__(
        self,
        repo_root: str | Path = ".",
        markdown_root: str | Path = "markdown_files",
        index_path: str | Path | None = None,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.markdown_root = (self.repo_root / markdown_root).resolve()
        self.index_path = (
            Path(index_path).resolve()
            if index_path
            else self.repo_root / "brain" / "info" / "evidence_index.json"
        )
        try:
            self.index_text = self.index_path.read_text(encoding="utf-8")
            parsed_index = json.loads(self.index_text)
            if not isinstance(parsed_index, dict):
                raise ValueError("evidence index is not an object")
        except (OSError, json.JSONDecodeError, ValueError):
            parsed_index = self._build_in_memory_index()
            self.index_text = json.dumps(parsed_index, ensure_ascii=False, sort_keys=True)
        self.index_hash = hashlib.sha256(self.index_text.encode("utf-8")).hexdigest()
        self.indexed_sources = self._load_evidence_index(parsed_index)

    def build(
        self,
        routing_record: RoutingRecord | dict[str, Any],
        *,
        player_input: str | None = None,
        current_state: dict[str, Any] | None = None,
        conversation_history: Any = None,
        selector: str = "auto",
        evidence_note: str | None = None,
        additional_specialists: Iterable[str] = (),
    ) -> EvidenceBundle:
        record = (
            routing_record.to_dict()
            if isinstance(routing_record, RoutingRecord)
            else routing_record
        )
        turn_id = str(record.get("turn_id", "unknown-turn"))
        prompt = self._player_prompt(record, player_input)
        transcript_history = self._load_player_history()
        supplied_history = conversation_history if isinstance(conversation_history, list) else []
        history = self._normalise_history([*transcript_history, *supplied_history])
        deduped_history: list[dict[str, Any]] = []
        seen_history_text: set[str] = set()
        for item in history:
            key = str(item.get('text', '')).strip()
            if key and key not in seen_history_text:
                seen_history_text.add(key)
                deduped_history.append(item)
        history = deduped_history
        history_breakdown = self._break_down_history(history)
        tags: list[str] = []
        for item in record.get("tags", []):
            if isinstance(item, dict) and isinstance(item.get("tag"), str):
                tags.append(str(item["tag"]))
        requests = self._normalise_requests(record.get("evidence_requests", []))
        selected: dict[str, dict[str, Any]] = {}
        gaps: list[dict[str, Any]] = []
        action_frames: list[dict[str, Any]] = []

        admin_request = record.get("admin_request")
        is_admin = record.get("request_type") in {"admin", "out_of_game"} or isinstance(admin_request, dict)
        if record.get("request_type") == "in_game":
            previous_bundle = record.get("evidence_bundle")
            if isinstance(previous_bundle, dict):
                for previous in previous_bundle.get("selected_sections", []):
                    if isinstance(previous, dict):
                        node = self._node_by_id(previous.get("id"))
                        if node:
                            self._add_selection(
                                selected,
                                node,
                                "previous_bundle",
                                "retained from the previous evidence round",
                            )
            action_frames, frame_gaps, frame_source = self._extract_action_frames(
                prompt, record, selector, history
            )
            gaps.extend(frame_gaps)
            gaps.extend(self._entity_evidence_gaps(action_frames))

            required, required_gaps = self._required_sections(requests, action_frames)
            gaps.extend(required_gaps)
            for node, reason in required:
                self._add_selection(selected, node, "routing_requirement", reason)

            temporary_nodes = self._temporary_memory_sections()
            for node in temporary_nodes:
                self._add_selection(
                    selected,
                    node,
                    "temporary_memory",
                    "temporary session memory is available to specialists",
                )

            candidates = self._candidate_nodes(
                prompt,
                tags,
                requests,
                selected,
                action_frames,
                evidence_note,
                120 if evidence_note else 180,
                history=history,
            )
            model_sections, model_gaps, selector_source = self._select_with_model(
                prompt,
                record,
                candidates,
                selector,
                action_frames,
                evidence_note,
                history,
            )
            gaps.extend(model_gaps)
            for node, reason in model_sections:
                self._add_selection(selected, node, "semantic_selector", reason)
            self._remove_entity_mismatches(selected, action_frames, gaps)
            selection_source = f"{frame_source}+{selector_source}"
        elif is_admin:
            action_frames = self._admin_action_frames(record, prompt)
            temporary_nodes = self._temporary_memory_sections()
            for node in temporary_nodes:
                self._add_selection(selected, node, "admin_context", "temporary session state is relevant to administrative review")
            for node, reason in self._admin_required_sections(record, prompt):
                self._add_selection(selected, node, "admin_requirement", reason)
            candidates = self._candidate_nodes(prompt, tags, requests, selected, action_frames, evidence_note, 120, history=history)
            if selector == "heuristic" or not self._deepseek_api_key():
                model_sections, model_gaps, selector_source = [], [], "admin_deterministic_selector"
            else:
                model_sections, model_gaps, selector_source = self._select_with_model(
                    prompt, record, candidates, selector, action_frames, evidence_note, history
                )
            gaps.extend(model_gaps)
            for node, reason in model_sections:
                self._add_selection(selected, node, "admin_semantic_selector", reason)
            selection_source = selector_source
        else:
            selection_source = "preflight"

        sections = tuple(
            SelectedSection(
                section_id=node["id"],
                name=node["name"],
                description=node["description"],
                source=node["source"],
                location=node["location"],
                path=tuple(node["path"]),
                selected_by=tuple(sorted(node["selected_by"])),
                reasons=tuple(dict.fromkeys(node["reasons"])),
                text=self._read_section_text(node),
            )
            for node in sorted(selected.values(), key=lambda item: item["id"])
        )
        player = {
            "raw": prompt,
            "segments": record.get("segments", []),
            "tags": tags,
        }
        snapshot = {
            "index_file": self._relative_index_path(),
            "index_hash": self.index_hash,
            "indexed_source_hashes": {
                section.source: self.indexed_sources[section.source]["source_hash"]
                for section in sections
                if self.indexed_sources.get(section.source, {}).get("source_hash")
            },
            "git_commit": self._git_commit(),
        }
        return EvidenceBundle(
            bundle_id=f"evidence-{turn_id}-{uuid.uuid4().hex[:8]}",
            turn_id=turn_id,
            source_snapshot=snapshot,
            player_input=player,
            current_state=dict(current_state or {}),
            action_frames=tuple(action_frames),
            selected_sections=sections,
            evidence_gaps=tuple(self._dedupe_gaps(gaps)),
            selection_source=selection_source,
            expansion_note=evidence_note,
            specialist_bundles=self._specialist_bundles(
                record,
                [section.to_dict() for section in sections],
                list(self._dedupe_gaps(gaps)),
                history=history,
                history_breakdown=history_breakdown,
                current_state=current_state or {},
                additional_specialists=additional_specialists,
            ),
            admin_sources=tuple(self._admin_sources(record, prompt)) if is_admin else (),
            conversation_history=history,
            history_breakdown=tuple(history_breakdown),
        )

    def _read_section_text(self, section: dict[str, Any]) -> str:
        source = section.get('source')
        location = section.get('location')
        if not isinstance(source, str) or not isinstance(location, str):
            return ''
        match = re.fullmatch(r'lines?\s+(\d+)-(\d+)', location.strip())
        if not match:
            return ''
        start, end = int(match.group(1)), int(match.group(2))
        path = (self.repo_root / source).resolve()
        try:
            path.relative_to(self.repo_root)
            lines = path.read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeDecodeError, ValueError):
            return ''
        if start < 1 or end < start or start > len(lines):
            return ''
        return '\n'.join(lines[start - 1:min(end, len(lines))])

    def _build_in_memory_index(self) -> dict[str, Any]:
        try:
            from brain.build_evidence_index import build_file_node
        except ModuleNotFoundError:
            from build_evidence_index import build_file_node
        under = []
        if self.markdown_root.exists():
            for path in sorted(self.markdown_root.rglob("*.md")):
                under.append(build_file_node(path, self.markdown_root))
        return {"under": under, "schema_version": 1, "name": "in_memory_campaign_evidence_index"}

    def _load_player_history(self) -> list[dict[str, Any]]:
        path = self.repo_root / 'brain/state/player_prompt_history.txt'
        try:
            text = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            return []
        pattern = re.compile(
            r'(?ms)^Day .*?\n\nPlayer:\n(.*?)\n\nGame:\n(.*?)(?=^Day .*?\n\nPlayer:\n|\Z)'
        )
        return [
            {
                'history_id': f'transcript-{index}',
                'source': 'player_transcript',
                'prompt': match.group(1).strip(),
                'result': match.group(2).strip(),
                'priority': 'foundational' if index <= 3 else 'normal',
            }
            for index, match in enumerate(pattern.finditer(text), start=1)
        ]

    @staticmethod
    def _normalise_history(value: Any) -> list[dict[str, Any]]:
        """Turn setup chat and completed-turn records into one ordered history."""
        if not isinstance(value, list):
            return []
        result: list[dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            history_id = str(item.get('history_id') or item.get('turn_id') or f'history-{index + 1}')
            role = str(item.get('role') or 'player')
            source = str(item.get('source') or ('setup_conversation' if 'content' in item else 'completed_turn'))
            content = item.get('content')
            prompt = item.get('prompt')
            result_text = item.get('result')
            text_parts = []
            if isinstance(content, str) and content.strip():
                text_parts.append(content.strip())
            if isinstance(prompt, str) and prompt.strip():
                text_parts.append('Player action: ' + prompt.strip())
            if isinstance(result_text, str) and result_text.strip():
                text_parts.append('Outcome: ' + result_text.strip())
            text = '\n'.join(text_parts).strip()
            if not text:
                continue
            result.append({
                'history_id': history_id,
                'sequence': index,
                'role': role,
                'source': source,
                'text': text,
                'day': item.get('day'),
                'turn_id': item.get('turn_id'),
                'priority': item.get('priority') or ('foundational' if source == 'setup_conversation' else 'normal'),
            })
        return result

    @staticmethod
    def _break_down_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract lightweight, source-linked categories without inventing facts."""
        category_terms = {
            'identity': ('name', 'age', 'race', 'ancestry', 'identity'),
            'background': ('background', 'work', 'engineer', 'trainer', 'family', 'home', 'live'),
            'ability': ('ability', 'skill', 'class', 'technique', 'can ', 'built', 'training'),
            'relationship': ('friend', 'housemate', 'relationship', 'trust', 'family', 'companion'),
            'system': ('ai', 'network', 'relay', 'assistant', 'computer', 'system', 'magic'),
            'resource': ('money', 'equipment', 'resource', 'material', 'weapon', 'tool'),
            'rule_or_constraint': ('must', 'cannot', 'only', 'rule', 'agreement', 'consent'),
            'decision': ('choose', 'decided', 'remain', 'main character', 'classless'),
        }
        broken_down: list[dict[str, Any]] = []
        for item in history:
            text = str(item.get('text', ''))
            lowered = text.casefold()
            categories = [
                category for category, terms in category_terms.items()
                if any(term in lowered for term in terms)
            ]
            if not categories:
                categories = ['context']
            priority = str(item.get('priority') or 'normal')
            important = priority == 'foundational' or len(categories) > 1 or any(
                category in categories for category in ('identity', 'ability', 'system', 'rule_or_constraint', 'decision')
            )
            broken_down.append({
                **item,
                'categories': categories,
                'important': important,
            })
        return broken_down

    @staticmethod
    def _player_prompt(record: dict[str, Any], explicit: str | None) -> str:
        if explicit is not None:
            return explicit
        player_input = record.get("player_input")
        if isinstance(player_input, dict) and isinstance(player_input.get("raw"), str):
            return player_input["raw"]
        texts = [
            item.get("text", "")
            for item in record.get("segments", [])
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ]
        return " ".join(texts).strip()

    @staticmethod
    def _admin_action_frames(record: dict[str, Any], prompt: str) -> list[dict[str, Any]]:
        request = record.get("admin_request")
        if not isinstance(request, dict):
            request = {"operation": "question", "target": "game_state", "player_message": prompt}
        return [{"kind": "admin_request", **request}]

    def _admin_required_sections(
        self, record: dict[str, Any], prompt: str
    ) -> list[tuple[dict[str, Any], str]]:
        request = record.get("admin_request", {})
        target = str(request.get("target", "game_state")) if isinstance(request, dict) else "game_state"
        lowered = f"{prompt} {target}".casefold()
        if target == "character" or any(word in lowered for word in ("character", "relationship", "npc", "modifier", "autonomy", "status")):
            keywords = {"character", "relationship", "status", "autonomy", "modifier"}
            preferred_sources = {"character relationship", "status sheet", "temp_memory"}
        elif target == "document" or any(word in lowered for word in ("document", "rule", "sheet", "ledger", "markdown")):
            keywords = {"rule", "status", "relationship", "ledger"}
            preferred_sources = set()
        elif target == "turn_history" or any(word in lowered for word in ("turn", "result", "resource", "history", "event")):
            keywords = {"temp_memory", "event", "resource"}
            preferred_sources = {"temp_memory", "core world"}
        else:
            keywords = {"game", "rules", "temp_memory", "terms", "branch", "registry"}
            preferred_sources = {"temp_memory", "game rules", "branch registry"}
        ranked: list[tuple[int, dict[str, Any], set[str]]] = []
        for indexed in self.indexed_sources.values():
            for node in indexed["nodes"]:
                text = " ".join(str(node.get(key, "")) for key in ("name", "description", "source", "path")).casefold()
                words = set(re.findall(r"[a-z0-9_]+", text))
                matches = keywords & words
                source_name = str(node.get("source", "")).casefold()
                score = len(matches) + sum(5 for value in preferred_sources if value in source_name)
                if score:
                    ranked.append((score, node, matches))
        ranked.sort(key=lambda item: (-item[0], str(item[1].get("id", ""))))
        return [
            (node, f"admin target requires {', '.join(sorted(matches))} evidence")
            for _score, node, matches in ranked[:40]
        ]

    def _admin_sources(self, record: dict[str, Any], prompt: str) -> list[dict[str, Any]]:
        """Collect safe non-Markdown sources for backend/code admin questions."""
        request = record.get("admin_request", {})
        target = str(request.get("target", "")) if isinstance(request, dict) else ""
        if target not in {"backend", "brain"} and not any(word in prompt.casefold() for word in ("backend", "brain", "code", "python", "specialist")):
            return []
        terms = set(re.findall(r"[a-z0-9_]{4,}", f"{prompt} {target}".casefold()))
        roots = [self.repo_root / name for name in ("brain", "backend", "outside game")]
        candidates: list[tuple[int, Path]] = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".py", ".md", ".json"}:
                    continue
                if any(part in {"__pycache__", "state"} for part in path.parts):
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                score = sum(text.casefold().count(term) for term in terms)
                if score:
                    candidates.append((score, path))
        sources: list[dict[str, Any]] = []
        budget = 60_000
        for score, path in sorted(candidates, key=lambda item: (-item[0], str(item[1]))):
            if budget <= 0:
                break
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            excerpt = text[: min(len(text), 12_000, budget)]
            relative = path.relative_to(self.repo_root).as_posix()
            sources.append({"source": relative, "score": score, "content": excerpt})
            budget -= len(excerpt)
        return sources

    def _load_evidence_index(self, index: dict[str, Any]) -> dict[str, dict[str, Any]]:
        sources: dict[str, dict[str, Any]] = {}
        for root in index.get("under", []):
            if not isinstance(root, dict) or not isinstance(root.get("location"), str):
                continue
            source = root["location"]
            entry = sources.setdefault(source, {
                "source_hash": root.get("source_hash"),
                "nodes": [],
            })

            def walk(node: dict[str, Any], path: list[str]) -> None:
                location = node.get("location")
                if isinstance(location, str) and location.startswith("lines "):
                    node_path = [*path, str(node.get("name", ""))]
                    entry["nodes"].append({
                        "id": self._section_id(source, node_path, location),
                        "name": str(node.get("name", "")),
                        "description": str(node.get("description", "")),
                        "source": source,
                        "source_hash": entry["source_hash"],
                        "location": location,
                        "path": node_path,
                        "selected_by": set(),
                        "reasons": [],
                    })
                for child in node.get("under", []):
                    if isinstance(child, dict):
                        walk(child, [*path, str(node.get("name", ""))])

            walk(root, [])
        return sources

    @staticmethod
    def _section_id(source: str, path: list[str], location: str) -> str:
        def slug(value: str) -> str:
            return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")

        start = location.removeprefix("lines ").split("-", 1)[0]
        return f"{slug(source)}.{slug('.'.join(path))}.{start}"

    def _extract_action_frames(
        self,
        prompt: str,
        record: dict[str, Any],
        selector: str,
        history: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
        api_key = self._deepseek_api_key()
        if selector == "heuristic" or (selector == "auto" and not api_key):
            return self._heuristic_action_frames(prompt, record), [], "heuristic_action_frame"
        if not api_key:
            raise RuntimeError("Action-frame extraction requires DEEPSEEK_API_KEY or API_KEY")
        payload = {
            "player_prompt": prompt,
            "player_history": history or [],
            "routing_record": {
                "mode": record.get("mode"),
                "tags": record.get("tags", []),
                "segments": record.get("segments", []),
            },
        }
        content = ModelGateway(self.repo_root).complete(
            stage="evidence.action_frames",
            request_id=str(record.get("turn_id", "")) or None,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            json_mode=True,
            messages=[
                {"role": "system", "content": ACTION_FRAME_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        ).content
        if not content:
            raise RuntimeError("DeepSeek returned an empty action-frame response")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError("DeepSeek returned invalid action-frame JSON") from exc

        raw_actions = result.get("actions", [])
        if not isinstance(raw_actions, list):
            raise RuntimeError("DeepSeek action-frame response has invalid actions")
        frames: list[dict[str, Any]] = []
        for raw in raw_actions:
            if not isinstance(raw, dict):
                raise RuntimeError("DeepSeek returned a malformed action frame")
            frame = self._normalise_action_frame(raw)
            if not frame["intent"]:
                raise RuntimeError("DeepSeek returned an action without an intent")
            frames.append(frame)

        gaps: list[dict[str, Any]] = []
        raw_gaps = result.get("evidence_gaps", [])
        if isinstance(raw_gaps, list):
            for item in raw_gaps:
                if isinstance(item, dict) and isinstance(item.get("reason"), str):
                    gaps.append({
                        "type": "action_frame_gap",
                        "request": str(item.get("request", "unspecified")),
                        "reason": item["reason"].strip(),
                    })
        return frames, gaps, "deepseek_action_frame"

    @staticmethod
    def _normalise_action_frame(raw: dict[str, Any]) -> dict[str, Any]:
        def entity(value: Any, default_kind: str) -> dict[str, Any] | None:
            if isinstance(value, str) and value.strip():
                return {
                    "name": value.strip(),
                    "kind": default_kind,
                    "specific_evidence_required": True,
                }
            if isinstance(value, dict) and isinstance(value.get("name"), str):
                return {
                    "name": value["name"].strip(),
                    "kind": str(value.get("kind", default_kind)),
                    "specific_evidence_required": bool(
                        value.get("specific_evidence_required", True)
                    ),
                }
            return None

        participants: list[dict[str, Any]] = []
        raw_participants = raw.get("participants", [])
        if isinstance(raw_participants, list):
            for item in raw_participants:
                participant = entity(item, "character")
                if participant:
                    participant["role"] = (
                        item.get("role", "other") if isinstance(item, dict) else "other"
                    )
                    participants.append(participant)
        actor = entity(raw.get("actor"), "character")
        target = entity(raw.get("target"), "unknown")
        return {
            "actor": actor,
            "intent": str(raw.get("intent", "")).strip(),
            "target": target,
            "method": str(raw.get("method", "")).strip(),
            "participants": participants,
            "ambiguities": [
                str(item).strip()
                for item in raw.get("ambiguities", [])
                if isinstance(item, str) and item.strip()
            ],
        }

    @staticmethod
    def _heuristic_action_frames(
        prompt: str, record: dict[str, Any]
    ) -> list[dict[str, Any]]:
        text = prompt.strip()
        names = re.findall(r"\b[A-Z][a-z]+\b", text)
        actor = names[0] if names else None
        participants = [
            {
                "name": name,
                "kind": "character",
                "role": "participant",
                "specific_evidence_required": True,
            }
            for name in names[1:]
            if name != actor
        ]
        segment_text = " ".join(
            item.get("text", "")
            for item in record.get("segments", [])
            if isinstance(item, dict)
        )
        return [{
            "actor": {
                "name": actor,
                "kind": "character",
                "specific_evidence_required": True,
            } if actor else None,
            "intent": segment_text or text,
            "target": None,
            "method": text,
            "participants": participants,
            "ambiguities": ["Heuristic action frame; semantic extraction was unavailable."],
        }]

    def _entity_evidence_gaps(
        self, action_frames: Iterable[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        for frame in action_frames:
            subjects: list[tuple[str, str]] = []
            target = frame.get("target")
            if isinstance(target, dict) and target.get("specific_evidence_required"):
                subjects.append((str(target["name"]), "target"))
            for participant in frame.get("participants", []):
                if isinstance(participant, dict) and participant.get("specific_evidence_required"):
                    subjects.append((str(participant["name"]), "participant"))
            for name, role in subjects:
                if not self._has_entity_path(name):
                    gaps.append({
                        "type": "missing_entity_evidence",
                        "entity": name,
                        "role": role,
                        "reason": "No indexed section is specific to this entity.",
                    })
        return gaps

    def _has_entity_path(self, entity_name: str) -> bool:
        wanted = self._normalise(entity_name)
        if not wanted:
            return False
        for indexed in self.indexed_sources.values():
            for node in indexed["nodes"]:
                path = self._normalise(" ".join(node["path"]))
                if wanted in path:
                    return True
        return False

    def _remove_entity_mismatches(
        self,
        selected: dict[str, dict[str, Any]],
        action_frames: Iterable[dict[str, Any]],
        gaps: list[dict[str, Any]],
    ) -> None:
        expected = {
            self._normalise(str(participant["name"]))
            for frame in action_frames
            for participant in frame.get("participants", [])
            if isinstance(participant, dict)
            and participant.get("specific_evidence_required")
        }
        expected.update(
            self._normalise(str(frame["actor"]["name"]))
            for frame in action_frames
            if isinstance(frame.get("actor"), dict)
            and frame["actor"].get("specific_evidence_required")
        )
        if not expected:
            return
        for section_id, node in list(selected.items()):
            if "character relationship" not in node["source"].lower():
                continue
            path = self._normalise(" ".join(node["path"]))
            named = self._known_character_names()
            mismatched = [name for name in named if name in path and name not in expected]
            if mismatched:
                del selected[section_id]
                gaps.append({
                    "type": "entity_mismatch",
                    "entity": ", ".join(sorted(expected)),
                    "rejected_section": node["name"],
                    "reason": f"Section is specific to {', '.join(mismatched)}, not the requested participant.",
                })

    def _known_character_names(self) -> set[str]:
        names: set[str] = set()
        indexed = self.indexed_sources.get("markdown_files/character relationship.md")
        if not indexed:
            return names
        generic = {
            "character relationship", "character relationships", "contents",
            "record conventions", "player character", "core cognitive network nodes",
            "developing relationships", "contract and protective relationships",
            "professional relationships", "shared network records",
        }
        for node in indexed["nodes"]:
            for part in node["path"]:
                normal = self._normalise(part)
                if (
                    normal
                    and normal not in generic
                    and len(normal.split()) == 1
                    and part[:1].isupper()
                ):
                    names.add(normal)
        return names

    def _normalise_requests(self, raw_requests: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_requests, list):
            return []
        requests: list[dict[str, Any]] = []
        for item in raw_requests:
            if not isinstance(item, dict) or not isinstance(item.get("tag"), str):
                continue
            requests.append({
                "tag": item["tag"],
                "sources": [x for x in item.get("required_sources", []) if isinstance(x, str)],
                "headings": [x for x in item.get("required_headings", []) if isinstance(x, str)],
            })
        return requests

    def _required_sections(
        self,
        requests: Iterable[dict[str, Any]],
        action_frames: Iterable[dict[str, Any]],
    ) -> tuple[list[tuple[dict[str, Any], str]], list[dict[str, Any]]]:
        selected: list[tuple[dict[str, Any], str]] = []
        gaps: list[dict[str, Any]] = []
        entity_tags = {
            "context.emotional",
            "context.relationship",
            "participant.companion",
            "mechanic.relationship_change",
            "mechanic.npc_autonomy",
        }
        entities = self._frame_entity_names(action_frames)
        for request in requests:
            for source_name in request["sources"]:
                source = f"markdown_files/{source_name}"
                indexed = self.indexed_sources.get(source)
                if indexed is None:
                    gaps.append({
                        "type": "missing_index_source",
                        "source": source,
                        "requested_by_tags": [request["tag"]],
                    })
                    continue
                for heading in request["headings"]:
                    node = self._resolve_heading(heading, indexed["nodes"])
                    if node is None:
                        gaps.append({
                            "type": "missing_index_heading",
                            "source": source,
                            "heading": heading,
                            "requested_by_tags": [request["tag"]],
                        })
                    elif request["tag"] in entity_tags and entities and "character relationship" in source.lower():
                        if not any(
                            entity in self._normalise(" ".join(node["path"]))
                            for entity in entities
                        ):
                            gaps.append({
                                "type": "missing_entity_heading",
                                "source": source,
                                "heading": heading,
                                "entity": ", ".join(sorted(entities)),
                                "requested_by_tags": [request["tag"]],
                                "reason": "A similarly named section exists for another entity, but no matching entity section exists.",
                            })
                        else:
                            selected.append((node, f"required for {request['tag']}: {heading}"))
                    else:
                        selected.append((node, f"required for {request['tag']}: {heading}"))
        return selected, gaps

    @staticmethod
    def _frame_entity_names(action_frames: Iterable[dict[str, Any]]) -> set[str]:
        names: set[str] = set()
        for frame in action_frames:
            for key in ("actor", "target"):
                entity = frame.get(key)
                if isinstance(entity, dict) and entity.get("specific_evidence_required"):
                    names.add(re.sub(r"[^a-z0-9]+", " ", str(entity["name"]).lower()).strip())
            for entity in frame.get("participants", []):
                if isinstance(entity, dict) and entity.get("specific_evidence_required"):
                    names.add(re.sub(r"[^a-z0-9]+", " ", str(entity["name"]).lower()).strip())
        return {name for name in names if name}

    def _temporary_memory_sections(self) -> list[dict[str, Any]]:
        """Return session memory plus the stable terminology reference.

        Both are bounded reference sources that specialists should see directly
        rather than rediscovering through semantic candidate selection.
        """
        nodes: list[dict[str, Any]] = []
        for source in (
            "markdown_files/TEMP_MEMORY.md",
            "markdown_files/TERMS_AND_NOMENCLATURE.md",
        ):
            indexed = self.indexed_sources.get(source)
            if indexed:
                nodes.extend(indexed["nodes"])
        return nodes

    def _specialist_bundles(
        self,
        record: dict[str, Any],
        sections: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
        *,
        history: list[dict[str, Any]] | None = None,
        history_breakdown: list[dict[str, Any]] | None = None,
        current_state: dict[str, Any] | None = None,
        additional_specialists: Iterable[str] = (),
    ) -> dict[str, dict[str, Any]]:
        """Partition the frozen references so each specialist gets a scoped bundle."""
        try:
            from brain.specialists.registry import get_specialist
        except ModuleNotFoundError:
            from specialists.registry import get_specialist
        names = list(dict.fromkeys([
            *(record.get("required_specialists", []) if isinstance(record.get("required_specialists", []), list) else []),
            *(str(name) for name in additional_specialists),
        ]))
        result: dict[str, dict[str, Any]] = {}
        keyword_map = {
            # Core lanes receive broad but intentional views of the same frozen
            # bundle. The Create Specialist must be able to compare all current
            # scopes before proposing a new branch specialist.
            "rules": ("rule", "combat", "difficulty", "xp", "time", "resource", "experiment", "terms"),
            "character": ("character", "status", "relationship", "modifier", "autonomy", "terms"),
            "special": ("business", "alchemy", "class", "politic", "faction", "relay", "lore", "branch", "registry", "terms"),
            "create": (),
            "resources": ("resource", "mana", "ledger", "status", "spell", "terms"),
            "time": ("time", "phase", "day", "action", "terms"),
            "experimentation": ("experiment", "practice", "refinement", "spell", "terms"),
            "relay": ("relay", "mana", "spell computer", "terms"),
            "cognitive_assistance": ("ava", "cognitive", "spell computer", "terms"),
            "modifier": ("resource", "mana", "cost", "modifier", "spell", "terms"),
            "modifier_creation": ("effect modifier", "repeated", "breakthrough", "training", "experiment", "modifier", "terms"),
            "spell": ("spell", "magic", "mana", "relay", "cost", "terms"),
            "difficulty": ("difficulty", "task", "reaction", "opponent", "roll", "experiment", "spell", "terms"),
            "current_state": ("status", "current", "temporary", "state", "terms"),
            "rules": ("rule", "game rules", "terms"),
            "xp": ("xp", "experience", "practice", "terms"),
        }
        history = history or []
        history_breakdown = history_breakdown or []
        current_state = current_state or {}
        state_scopes = {
            'rules': ('position', 'world_pool', 'pending_world_event', 'saved_rolls', 'game_cache', 'answers'),
            'character': ('position', 'party', 'main_character', 'draft', 'answers', 'game_cache'),
            'special': ('position', 'party', 'main_character', 'pending_world_event', 'specialist_proposals', 'game_cache'),
            'create': ('position', 'party', 'main_character', 'draft', 'specialist_proposals', 'answers', 'game_cache'),
            'resources': ('position', 'party', 'main_character', 'draft', 'game_cache', 'answers'),
            'time': ('position', 'pending_world_event', 'saved_rolls', 'answers'),
            'experimentation': ('position', 'party', 'game_cache', 'answers'),
            'relay': ('position', 'party', 'game_cache', 'answers'),
            'cognitive_assistance': ('position', 'party', 'main_character', 'game_cache', 'answers'),
            'modifier': ('position', 'party', 'draft', 'game_cache', 'answers'),
            'modifier_creation': ('position', 'party', 'draft', 'game_cache', 'answers'),
            'spell': ('position', 'party', 'game_cache', 'answers'),
            'difficulty': ('position', 'party', 'pending_world_event', 'saved_rolls', 'game_cache', 'answers'),
            'current_state': ('position', 'party', 'main_character', 'draft', 'game_cache', 'answers'),
            'xp': ('position', 'party', 'game_cache', 'answers'),
        }
        for name in names:
            try:
                definition = get_specialist(name)
                activation = set(definition.activation_tags)
            except ValueError:
                try:
                    from brain.branch_registry import BranchRegistry
                except ModuleNotFoundError:
                    from branch_registry import BranchRegistry
                branch = BranchRegistry(self.repo_root).entry(name)
                raw_activation = branch.get("activation_tags", []) if branch else []
                activation = set(raw_activation if isinstance(raw_activation, list) else [raw_activation])
            keywords = keyword_map.get(name, (name.replace("_", " "), "terms"))
            scoped = []
            for section in sections:
                text = " ".join(str(section.get(key, "")) for key in ("name", "description", "source", "path", "selected_by", "reasons")).lower()
                if "terms_and_nomenclature.md" in text or "temp_memory.md" in text:
                    scoped.append(section)
                elif any(keyword in text for keyword in keywords):
                    scoped.append(section)
                elif any(tag in text for tag in activation):
                    scoped.append(section)
            if not scoped:
                scoped = sections[:]
            history_keywords = tuple(keywords) + tuple(str(tag).replace('_', ' ') for tag in activation)
            scoped_history = []
            for item in history_breakdown:
                text = str(item.get('text', '')).casefold()
                foundational = item.get('priority') == 'foundational' or item.get('source') == 'setup_conversation'
                relevant = any(keyword.casefold() in text for keyword in history_keywords if keyword)
                if name in {'character', 'create'} and foundational:
                    relevant = True
                if item.get('important') and foundational and name in {'rules', 'special', 'resources', 'difficulty', 'modifier', 'modifier_creation'}:
                    relevant = True
                if relevant or (not history_breakdown and history):
                    scoped_history.append(item)
            if not scoped_history and history:
                scoped_history = history
            state_keys = state_scopes.get(name, ('position', 'party', 'draft', 'answers', 'game_cache'))
            scoped_state = {key: current_state[key] for key in state_keys if key in current_state}
            scoped_ids = {section.get("id") for section in scoped}
            scoped_gaps = []
            for gap in gaps:
                requested = gap.get("requested_by_tags", []) if isinstance(gap, dict) else []
                if not activation or set(requested) & activation or gap.get("source") in {s.get("source") for s in scoped}:
                    scoped_gaps.append(gap)
            scoped_history_ids = {
                str(item.get('history_id'))
                for item in scoped_history
                if isinstance(item, dict) and item.get('history_id')
            }
            evidence_ids = sorted({
                str(section.get('evidence_id') or section.get('id'))
                for section in scoped
                if isinstance(section, dict) and (section.get('evidence_id') or section.get('id'))
            })
            history_ids = sorted(scoped_history_ids)
            result[name] = {
                "specialist": name,
                "selected_sections": scoped,
                "evidence_gaps": scoped_gaps,
                "history": scoped_history,
                "history_breakdown": [item for item in history_breakdown if item.get('history_id') in scoped_history_ids],
                "state": scoped_state,
                "citation_allowlist": {
                    "evidence_ids": evidence_ids,
                    "history_ids": history_ids,
                    "all_ids": sorted(set(evidence_ids) | set(history_ids)),
                },
                "section_count": len(scoped_ids),
            }
        return result

    def _node_by_id(self, section_id: Any) -> dict[str, Any] | None:
        if not isinstance(section_id, str):
            return None
        for indexed in self.indexed_sources.values():
            for node in indexed["nodes"]:
                if node["id"] == section_id:
                    return node
        return None

    def _candidate_nodes(
        self,
        prompt: str,
        tags: list[str],
        requests: list[dict[str, Any]],
        selected: dict[str, dict[str, Any]],
        action_frames: Iterable[dict[str, Any]],
        evidence_note: str | None = None,
        limit: int = 180,
        history: Iterable[dict[str, Any]] = (),
    ) -> list[dict[str, Any]]:
        frame_text = json.dumps(list(action_frames), ensure_ascii=False)
        evidence_note = (evidence_note or "")[:4000]
        history_text = ' '.join(str(item.get('text', '')) for item in history if isinstance(item, dict))
        query = self._normalise(" ".join([prompt, history_text, evidence_note, frame_text, *tags, *(r["tag"] for r in requests)]))
        words = {word for word in query.split() if len(word) > 2}
        required_sources = {
            f"markdown_files/{source}"
            for request in requests
            for source in request["sources"]
        }
        ranked: list[tuple[int, dict[str, Any]]] = []
        for indexed in self.indexed_sources.values():
            for node in indexed["nodes"]:
                text = self._normalise(
                    " ".join([node["name"], node["description"], " ".join(node["path"])])
                )
                score = len(words & set(text.split()))
                if node["source"] in required_sources:
                    score += 8
                if node["id"] in selected:
                    score += 20
                if score:
                    ranked.append((score, node))
        ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
        result: dict[str, dict[str, Any]] = {node["id"]: node for _, node in ranked[:limit]}
        result.update(selected)
        return list(result.values())

    @staticmethod
    def _recover_selector_json(content: str) -> dict[str, Any] | None:
        """Recover completed section objects from a truncated JSON response."""
        matches = re.findall(
            r'"id"\s*:\s*"([^"\\]+)"\s*,\s*"reason"\s*:\s*"((?:\\.|[^"\\])*)"',
            content,
        )
        if not matches:
            return None
        return {
            "sections": [{"id": section_id, "reason": reason} for section_id, reason in matches],
            "evidence_gaps": [{
                "request": "complete semantic evidence selection",
                "reason": "The model response was truncated; recovered completed selections only.",
            }],
        }

    def _select_with_model(
        self,
        prompt: str,
        record: dict[str, Any],
        candidates: list[dict[str, Any]],
        selector: str,
        action_frames: Iterable[dict[str, Any]],
        evidence_note: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> tuple[list[tuple[dict[str, Any], str]], list[dict[str, Any]], str]:
        if selector == "heuristic":
            return [], [], "heuristic_index_selector"
        api_key = self._deepseek_api_key()
        if selector == "auto" and not api_key:
            return [], [{
                "type": "selector_unavailable",
                "reason": "No DeepSeek API key was found; required indexed sections were preserved.",
            }], "required_sections_only"
        if not api_key:
            raise RuntimeError("Evidence selection requires DEEPSEEK_API_KEY or API_KEY")

        payload = {
            "player_prompt": prompt,
            "player_history": history or [],
            "routing_record": {
                "request_type": record.get("request_type"),
                "mode": record.get("mode"),
                "tags": record.get("tags", []),
                "segments": record.get("segments", []),
                "required_specialists": record.get("required_specialists", []),
            },
            "action_frames": list(action_frames),
            "evidence_note": (evidence_note or "")[:4000],
            "candidate_sections": [
                {
                    "id": node["id"],
                    "name": node["name"],
                    "description": node["description"],
                    "source": node["source"],
                    "location": node["location"],
                    "path": node["path"],
                }
                for node in candidates
            ],
        }
        content = ModelGateway(self.repo_root).complete(
            stage="evidence.selection",
            request_id=str(record.get("turn_id", "")) or None,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            json_mode=True,
            messages=[
                {"role": "system", "content": SELECTOR_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        ).content
        if not content:
            raise RuntimeError("DeepSeek returned an empty evidence-selection response")
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # DeepSeek can occasionally truncate a long JSON response despite
            # response_format=json_object. Recover completed section entries;
            # otherwise preserve deterministic required sections and continue.
            result = self._recover_selector_json(content)
            if result is None:
                return [], [{
                    "type": "selector_invalid_output",
                    "reason": "DeepSeek returned truncated or invalid evidence-selection JSON; semantic selection was skipped and required sections were preserved.",
                }], "required_sections_only_after_invalid_model_response"

        if not isinstance(result, dict):
            return [], [{
                "type": "selector_invalid_output",
                "reason": "DeepSeek returned a non-object evidence-selection response; required sections were preserved.",
            }], "required_sections_only_after_invalid_model_response"

        by_id = {node["id"]: node for node in candidates}
        sections: list[tuple[dict[str, Any], str]] = []
        gaps: list[dict[str, Any]] = []
        raw_sections = result.get("sections", [])
        if not isinstance(raw_sections, list):
            gaps.append({
                "type": "selector_invalid_output",
                "reason": "DeepSeek returned a non-list sections value.",
            })
            raw_sections = []
        for item in raw_sections:
            if not isinstance(item, dict) or item.get("id") not in by_id:
                gaps.append({
                    "type": "selector_invalid_section",
                    "section_id": str(item.get("id", "unknown")) if isinstance(item, dict) else "unknown",
                    "reason": "DeepSeek selected a section that is not present in the evidence index.",
                })
                continue
            reason = item.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                gaps.append({
                    "type": "selector_invalid_section",
                    "section_id": item["id"],
                    "reason": "DeepSeek selected a section without a reason.",
                })
                continue
            sections.append((by_id[item["id"]], reason.strip()))

        if len(sections) > 12:
            gaps.append({
                "type": "selector_truncated",
                "reason": "DeepSeek selected more than 12 additional sections; the first 12 were retained.",
                "discarded_count": len(sections) - 12,
            })
            sections = sections[:12]

        raw_gaps = result.get("evidence_gaps", [])
        if isinstance(raw_gaps, list):
            for item in raw_gaps:
                if isinstance(item, dict) and isinstance(item.get("reason"), str):
                    gaps.append({
                        "type": "selector_gap",
                        "request": str(item.get("request", "unspecified")),
                        "reason": item["reason"].strip(),
                    })
        return sections, gaps, "deepseek_index_selector"

    @staticmethod
    def _add_selection(
        selected: dict[str, dict[str, Any]],
        node: dict[str, Any],
        selected_by: str,
        reason: str,
    ) -> None:
        existing = selected.setdefault(node["id"], dict(node))
        existing.setdefault("selected_by", set()).add(selected_by)
        existing.setdefault("reasons", []).append(reason)

    def _resolve_heading(
        self, requested: str, nodes: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        wanted = self._normalise(requested)
        best: tuple[int, dict[str, Any]] | None = None
        for node in nodes:
            name = self._normalise(node["name"])
            description = self._normalise(node["description"])
            score = 0
            if wanted == name:
                score = 100
            elif wanted in name:
                score = 90
            elif name and all(word in name.split() for word in wanted.split()):
                score = 80
            elif wanted in description:
                score = 50
            if score and (best is None or score > best[0]):
                best = score, node
        return best[1] if best else None

    @staticmethod
    def _normalise(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @staticmethod
    def _deepseek_api_key() -> str | None:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:
            pass
        return os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY")

    @staticmethod
    def _dedupe_gaps(gaps: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for gap in gaps:
            key = json.dumps(gap, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen.add(key)
                result.append(gap)
        return result

    def _relative_index_path(self) -> str:
        try:
            return self.index_path.relative_to(self.repo_root).as_posix()
        except ValueError:
            return str(self.index_path)

    def _git_commit(self) -> str | None:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        commit = result.stdout.strip()
        return commit or None


def _load_routing_record(argument: str) -> dict[str, Any]:
    if argument == "-":
        raw = sys.stdin.read()
    else:
        candidate = Path(argument)
        if candidate.is_file():
            raw = candidate.read_text(encoding="utf-8")
        else:
            raw = argument
    try:
        record = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit("Evidence Bundle input must be routing-record JSON or a JSON file") from exc
    if not isinstance(record, dict):
        raise SystemExit("Evidence Bundle input must be a JSON object")
    required = {"turn_id", "request_type", "segments", "tags", "evidence_requests"}
    missing = sorted(required - set(record))
    if missing:
        raise SystemExit(f"Routing record is missing required fields: {', '.join(missing)}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Select indexed Evidence Bundle references from a Turn Router JSON record"
    )
    parser.add_argument(
        "routing_record",
        help="Turn Router JSON file, inline JSON, or '-' to read JSON from stdin",
    )
    parser.add_argument("--player-prompt", help="Original player prompt if not present in the record")
    parser.add_argument("--selector", choices=("auto", "deepseek", "heuristic"), default="auto")
    parser.add_argument("--gap-mode", choices=("auto", "deepseek", "heuristic"), default="auto")
    parser.add_argument("--evidence-note", help="Gap note from a previous adjudication round")
    parser.add_argument("--markdown-root", default="markdown_files")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    record = _load_routing_record(args.routing_record)
    builder = EvidenceBundleBuilder(repo_root, args.markdown_root)
    bundle = builder.build(
        record,
        player_input=args.player_prompt,
        current_state=record.get("current_state", {}),
        selector=args.selector,
        evidence_note=args.evidence_note,
    )
    output = dict(record)
    output["evidence_bundle"] = bundle.to_dict()
    try:
        from brain.specialists.gap_adjudicator import GapAdjudicator
    except ModuleNotFoundError:  # Direct execution: python brain/evidence_bundle.py
        from specialists.gap_adjudicator import GapAdjudicator
    gap_adjudication = GapAdjudicator().adjudicate(output, mode=args.gap_mode)
    output["gap_adjudication"] = gap_adjudication
    output["evidence_bundle"]["gap_adjudication"] = gap_adjudication
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
