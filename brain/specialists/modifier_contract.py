"""Shared modifier magnitude rules for Stat, Effect, and Class Modifiers."""
from __future__ import annotations

from typing import Any


# Inclusive absolute magnitude bounds for one modifier at each character tier.
TIER_MODIFIER_MAGNITUDE_BANDS: dict[int, tuple[int, int]] = {
    0: (1, 2),
    1: (2, 5),
    2: (5, 10),
    3: (10, 20),
    4: (20, 50),
    5: (50, 100),
}

MODIFIER_MAGNITUDE_PROMPT = (
    "Universal modifier magnitude contract: one Stat, Effect, or Class Modifier "
    "must use the inclusive absolute magnitude band for its character tier: "
    "Tier 0 = +1 to +2; Tier 1 = +2 to +5; Tier 2 = +5 to +10; "
    "Tier 3 = +10 to +20; Tier 4 = +20 to +50; Tier 5 = +50 to +100. "
    "The tier band is a hard bound, not an automatic award of the maximum. "
    "Evidence/basis selects the value within the band; slot role determines "
    "where an option may be selected, not a replacement for the tier rule. "
    "Keep the sign separate from magnitude for penalties, and sum relevant "
    "modifiers unless an explicit rule restricts stacking."
)


def tier_number(value: Any) -> int:
    """Return a numeric tier from an integer or a ``Tier N`` label."""
    if isinstance(value, bool):
        raise ValueError("tier must be an integer from 0 through 5")
    if isinstance(value, int):
        tier = value
    elif isinstance(value, str):
        text = value.strip().casefold().replace("tier", "").strip()
        try:
            tier = int(text)
        except ValueError as exc:
            raise ValueError("tier must be an integer from 0 through 5") from exc
    else:
        raise ValueError("tier must be an integer from 0 through 5")
    if tier not in TIER_MODIFIER_MAGNITUDE_BANDS:
        raise ValueError("tier must be an integer from 0 through 5")
    return tier


def magnitude_number(value: Any) -> float:
    """Parse a signed or unsigned magnitude value."""
    if isinstance(value, bool):
        raise ValueError("magnitude must be numeric")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace("+", "")
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError("magnitude must be numeric") from exc
    raise ValueError("magnitude must be numeric")


def validate_magnitude(value: Any, tier: Any) -> str | None:
    """Return a player-safe validation reason, or ``None`` when valid."""
    try:
        tier_value = tier_number(tier)
        magnitude = abs(magnitude_number(value))
    except ValueError as exc:
        return str(exc)
    minimum, maximum = TIER_MODIFIER_MAGNITUDE_BANDS[tier_value]
    if magnitude < minimum or magnitude > maximum:
        return f"magnitude must be between {minimum} and {maximum} for Tier {tier_value}"
    return None
