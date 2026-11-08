"""Contracts shared by the conversational admin agent and editor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdminRequest:
    request_id: str
    message: str
    operation: str = "question"
    target: str = "game_state"
    entities: tuple[str, ...] = ()
    write_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "message": self.message,
            "operation": self.operation,
            "target": self.target,
            "entities": list(self.entities),
            "write_requested": self.write_requested,
        }


@dataclass
class AdminResponse:
    request_id: str
    status: str
    answer: str = ""
    diagnosis: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    changes: list[dict[str, Any]] = field(default_factory=list)
    instructions: list[dict[str, Any]] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    modifier_group_placements: list[dict[str, Any]] = field(default_factory=list)
    approval_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "answer": self.answer,
            "diagnosis": self.diagnosis,
            "evidence": self.evidence,
            "changes": self.changes,
            "instructions": self.instructions,
            "questions": self.questions,
            "conflicts": self.conflicts,
            "modifier_group_placements": self.modifier_group_placements,
            "approval_required": self.approval_required,
        }
