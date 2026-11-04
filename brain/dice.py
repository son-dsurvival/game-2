"""Persistent dice ownership; retries cannot reroll or change a saved die."""
from __future__ import annotations

import json
import secrets
import threading
from pathlib import Path
from typing import Any, Callable

from brain.persistence import atomic_json

_LOCK = threading.Lock()


class DiceJournal:
    def __init__(self, root: str | Path, *, random_below: Callable[[int], int] = secrets.randbelow):
        self.path = Path(root) / 'brain/state/dice.json'
        self.random_below = random_below

    def roll(self, identity: str, *, sides: int = 20, count: int = 1) -> dict[str, Any]:
        if type(sides) is not int or type(count) is not int or not 2 <= sides <= 100 or not 1 <= count <= 20:
            raise ValueError('Unsupported dice request.')
        with _LOCK:
            try:
                saved = json.loads(self.path.read_text(encoding='utf-8'))
            except FileNotFoundError:
                saved = {}
            if identity in saved:
                previous = saved[identity]
                if previous['sides'] != sides or previous['count'] != count:
                    raise ValueError('A saved roll cannot change shape.')
                return previous
            rolls = [self.random_below(sides) + 1 for _ in range(count)]
            result = {'roll_id': identity, 'sides': sides, 'count': count, 'rolls': rolls, 'result': sum(rolls)}
            saved[identity] = result
            atomic_json(self.path, saved)
            return result
