"""Phase arithmetic and idempotent phase-transition planning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .contracts import PhasePosition


PHASES = (
    "Early Morning",
    "Morning",
    "Late Morning",
    "Midday",
    "Mid Afternoon",
    "Late Afternoon",
    "Evening",
    "Night",
    "Midnight",
)


@dataclass(frozen=True)
class PhaseAdvance:
    tick_id: str
    previous: PhasePosition
    current: PhasePosition

    def to_dict(self) -> dict[str, Any]:
        return {
            "tick_id": self.tick_id,
            "previous": self.previous.to_dict(),
            "current": self.current.to_dict(),
        }


class PhaseClock:
    """Convert structured time changes into one tick per entered phase."""

    phases = PHASES

    def __init__(self, phases: tuple[str, ...] = PHASES):
        if not phases:
            raise ValueError("PhaseClock requires at least one phase")
        self.phases = tuple(phases)
        self._lookup = {self._key(name): name for name in self.phases}

    def normalize_phase(self, phase: str | int) -> str:
        if isinstance(phase, int):
            if 1 <= phase <= len(self.phases):
                return self.phases[phase - 1]
            raise ValueError(f"Phase number out of range: {phase}")
        key = self._key(str(phase))
        if key.isdigit():
            return self.normalize_phase(int(key))
        try:
            return self._lookup[key]
        except KeyError as exc:
            raise ValueError(f"Unknown phase: {phase!r}") from exc

    def position(self, day: int, phase: str | int, progress: float = 0.0) -> PhasePosition:
        if int(day) < 1:
            raise ValueError("Day must be positive")
        progress = float(progress)
        if not 0 <= progress < 1:
            raise ValueError("Phase progress must be in [0, 1)")
        return PhasePosition(int(day), self.normalize_phase(phase), progress)

    def advance(self, start: PhasePosition, phases_elapsed: float) -> list[PhaseAdvance]:
        phases_elapsed = float(phases_elapsed)
        if phases_elapsed < 0:
            raise ValueError("phases_elapsed cannot be negative")
        start = self.position(start.day, start.phase, start.progress)
        result: list[PhaseAdvance] = []
        day = start.day
        index = self.phases.index(start.phase)
        previous = start
        boundaries = int(start.progress + phases_elapsed)
        for _ in range(boundaries):
            index += 1
            if index >= len(self.phases):
                index = 0
                day += 1
            current = PhasePosition(day, self.phases[index], 0.0)
            result.append(PhaseAdvance(self.tick_id(current), previous, current))
            previous = current
        return result

    def transitions_from_time_change(
        self,
        before: PhasePosition,
        change: dict[str, Any],
    ) -> list[PhaseAdvance]:
        """Read a Lead Resolver time-change object without inferring outcomes."""
        elapsed = change.get("phases_elapsed", change.get("phases", change.get("phase_cost", 0)))
        if isinstance(elapsed, bool):
            elapsed = 0
        try:
            elapsed = float(elapsed)
        except (TypeError, ValueError):
            elapsed = 0
        if elapsed:
            return self.advance(before, elapsed)
        after_day = change.get("after_day", change.get("day"))
        after_phase = change.get("after_phase", change.get("phase"))
        if after_day is None or after_phase is None:
            return []
        after = self.position(int(after_day), after_phase, float(change.get("after_progress", change.get("progress", 0))))
        return self._path_to(before, after)

    def tick_id(self, position: PhasePosition) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", position.phase.lower()).strip("-")
        return f"day-{position.day}-{slug}"

    def _path_to(self, before: PhasePosition, after: PhasePosition) -> list[PhaseAdvance]:
        before = self.position(before.day, before.phase, before.progress)
        after = self.position(after.day, after.phase, after.progress)
        if before.day == after.day and before.phase == after.phase:
            return []
        result: list[PhaseAdvance] = []
        current = before
        # A bounded walk prevents malformed time changes from hanging the runtime.
        for _ in range(1, 1001):
            step = self.advance(current, 1)[0]
            result.append(step)
            if step.current.day == after.day and step.current.phase == after.phase:
                return result
            current = step.current
        raise ValueError(f"Cannot reach phase {after} from {before} within 1000 phases")

    @staticmethod
    def _key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
