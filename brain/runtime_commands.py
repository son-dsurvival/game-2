"""Validated command intents that model agents may request.

Agents request commands; the runtime remains the only component that executes
commands. Destructive reset/cancel commands and approval commands stay player
controlled.
"""
from __future__ import annotations

from typing import Any


ADMIN_AGENT_COMMANDS = frozenset({
    "/status", "/retry", "/pause", "/resume", "/review", "/next-file",
    "/back-setup", "/undo", "/undo-setup", "/cancel-operation", "/end-day",
    "/specialists", "/new-character", "/new-party-member", "/add", "/install",
})
LEAD_RESOLVER_COMMANDS = frozenset({"/end-day"})
FORBIDDEN_AGENT_COMMANDS = frozenset({
    "/new-game", "/cancel-setup", "/approve", "/approve-reset", "/main", "/quit",
})


def normalize_agent_command(value: Any, *, allowed: frozenset[str]) -> dict[str, Any] | None:
    """Validate one model command envelope without executing it."""
    if value is None:
        return None
    if isinstance(value, str):
        name, _, argument = value.strip().partition(" ")
        value = {"name": name, "argument": argument.strip()}
    if not isinstance(value, dict):
        raise ValueError("Agent runtime command must be an object or null.")
    name = str(value.get("name") or value.get("command") or "").strip().casefold()
    if name and not name.startswith("/"):
        name = "/" + name
    if name in FORBIDDEN_AGENT_COMMANDS:
        raise ValueError(f"Agent may not call protected command {name}.")
    if name not in allowed:
        raise ValueError(f"Agent requested an unsupported command: {name or '<empty>'}.")
    argument = value.get("argument", value.get("args", ""))
    if isinstance(argument, dict):
        argument = argument.get("value", argument.get("name", ""))
    return {"name": name, "argument": str(argument or "").strip()}
