"""Keep roleplay-unrevealed outcomes out of narration, not out of OOC records."""

from __future__ import annotations

from typing import Any, Iterable


HIDDEN_VISIBILITY = {"hidden", "private", "unknown", "hidden_until_reported", "offscreen", "roleplay_unrevealed"}
OOC_VISIBLE = {"teammate_status", "background_status", "ooc_visible", "public"}


class VisibilityFilter:
    """Filter narration input without deleting player-readable OOC state.

    A hidden/offscreen label means the player character has not learned the
    fact. It does not make Experimentation Register.md secret from the player.
    """

    def for_narrator(self, tick: dict[str, Any]) -> dict[str, Any]:
        result = dict(tick)
        for field in (
            "actions",
            "automatic_updates",
            "resource_changes",
            "world_updates",
            "visibility_events",
        ):
            values = tick.get(field, [])
            if isinstance(values, list):
                result[field] = [item for item in values if self.is_visible(item)]
        result["hidden_event_count"] = sum(
            1
            for field in ("actions", "automatic_updates", "resource_changes", "world_updates", "visibility_events")
            for item in (tick.get(field, []) if isinstance(tick.get(field, []), list) else [])
            if not self.is_visible(item)
        )
        result["player_view"] = True
        return result

    def visible_events(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in events if self.is_visible(item)]

    @staticmethod
    def is_visible(event: Any) -> bool:
        if not isinstance(event, dict):
            return False
        # Background records are private unless explicitly classified as safe
        # OOC teammate/background status or as a revealed public fact.
        if str(event.get("ooc_visibility", "private")).casefold() not in OOC_VISIBLE:
            return False
        visibility = event.get("player_visibility", event.get("visibility", "hidden"))
        return str(visibility).casefold() not in HIDDEN_VISIBILITY
