"""Convert approved technical clarification text into player-safe language."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from brain.state.model_gateway import ModelGateway

try:
    # The outside-game directory is loaded as a runtime module folder rather
    # than a Python package because its name contains a space.
    from player_clarification import PlayerClarification
except ModuleNotFoundError:  # pragma: no cover - package-style loading
    from .player_clarification import PlayerClarification


PLAYER_LANGUAGE_PROMPT = """You are the Player Language Agent.

Rewrite the supplied technical clarification for the player. Return JSON only:
{"player_message": "...", "player_question": "..."}

Rules:
- Make the message easy to understand and concise.
- Remove specialist names, Admin names, backend terms, evidence references,
  internal reasoning, file names, templates, formulas, and diagnostics.
- Preserve exact option names, numbers, magnitudes, limits, and conditions.
- Do not choose an option, change a rule, add facts, or omit a required choice.
- If the technical text contains option descriptions, include those descriptions
  in player_message before the question.
- Keep player_question as the exact decision still required.
- The output must be safe to show directly to the player.
"""


class PlayerLanguageAgent:
    def __init__(self, repo_root: str | Path = "."):
        self.root = Path(repo_root).resolve()

    def render(self, response: dict[str, Any]) -> dict[str, str] | None:
        technical_answer = str(response.get("answer") or "").strip()
        technical_question = PlayerClarification.from_response(response)
        if not technical_answer and not technical_question:
            return None
        payload = {
            "technical_message": technical_answer,
            "technical_question": technical_question or "",
        }
        try:
            raw = ModelGateway(self.root).complete(
                stage="player_language",
                request_id=f"player-language-{response.get('batch_id', 'clarification')}",
                model=os.getenv("PLAYER_LANGUAGE_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-chat")),
                json_mode=True,
                messages=[
                    {"role": "system", "content": PLAYER_LANGUAGE_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
            ).content
            value = json.loads(raw)
            if not isinstance(value, dict):
                return None
            message = str(value.get("player_message") or "").strip()
            question = str(value.get("player_question") or "").strip()
            if not question:
                question = technical_question or ""
            if not message and not question:
                return None
            return {"player_message": message, "player_question": question}
        except Exception:
            # The private technical result remains available for retry; never
            # expose the raw Admin answer as a fallback.
            return None
