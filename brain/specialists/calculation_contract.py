"""Validation for specialist-owned numeric calculation contracts.

Specialists choose evidence-backed inputs; this module verifies that their
numeric handoff is complete, scoped, and internally consistent before the Lead
Resolver sees it.
"""

from __future__ import annotations

import re
from typing import Any


class CalculationContractError(ValueError):
    pass


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculationContractError(f"{field} must be numeric, got {value!r}")
    return float(value)


def _intish(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def validate_calculation(name: str, calculation: Any, *, status: str) -> dict[str, Any] | None:
    if name not in {"difficulty", "modifier"}:
        return calculation if calculation is not None else None
    if not isinstance(calculation, dict):
        if status == "needs_evidence":
            return calculation
        raise CalculationContractError(f"{name} must return a structured calculation")
    if calculation.get("kind") != name:
        raise CalculationContractError(
            f"{name} calculation kind must be {name!r}, got {calculation.get('kind')!r}"
        )
    if name == "difficulty":
        _validate_difficulty(calculation, status)
    else:
        _validate_modifier(calculation, status)
    return calculation


def _validate_difficulty(calc: dict[str, Any], status: str) -> None:
    target = calc.get("target_type")
    if target not in {"Task Value", "Reaction Total"}:
        raise CalculationContractError("difficulty target_type must be Task Value or Reaction Total")
    components = calc.get("components")
    if not isinstance(components, dict):
        raise CalculationContractError("difficulty components must be an object")
    required = ("difficulty", "novelty", "integration", "independence", "field_risk")
    for key in required:
        if key not in components:
            raise CalculationContractError(f"difficulty is missing component {key!r}")
        _number(components[key], f"difficulty.components.{key}")
    practice = components.get("practice_carryover", 0)
    _number(practice, "difficulty.components.practice_carryover")
    tier = calc.get("tier")
    if tier is not None and not isinstance(tier, (int, str)):
        raise CalculationContractError("difficulty tier must be an integer or label")
    total = _number(calc.get("total"), "difficulty.total")
    expected = sum(float(components[key]) for key in required) - float(practice)
    if target == "Reaction Total":
        reference = _number(calc.get("reaction_reference"), "difficulty.reaction_reference")
        expected += reference
    if abs(total - expected) > 0.001:
        # Models occasionally mis-sum their own explicit components. The
        # components are the evidence-backed source of truth; reconcile the
        # total from them rather than blocking the whole turn on arithmetic.
        calc.setdefault("reconciliations", []).append({
            "field": "total",
            "given": _intish(total),
            "reconciled": _intish(expected),
        })
        calc["total"] = _intish(expected)
    # A complete handoff must select one value, not defer a range to Lead.
    if status == "complete" and any(isinstance(components[key], str) for key in required):
        raise CalculationContractError("complete difficulty calculation cannot contain ranges")


def _validate_modifier(calc: dict[str, Any], status: str) -> None:
    action_type = str(calc.get("action_type", "")).lower()
    formula = str(calc.get("stat_formula", ""))
    if not formula:
        raise CalculationContractError("modifier stat_formula is required")
    if any(word in action_type for word in ("magic", "spell", "mana")):
        if "int" not in formula.lower() or "wis" not in formula.lower():
            raise CalculationContractError("magical modifier calculation must use INT and WIS")
    if "physical block" in action_type or action_type in {"block", "physical_block"}:
        if "str" not in formula.lower() or "end" not in formula.lower():
            raise CalculationContractError("physical block modifier calculation must use STR and END")
    components = calc.get("components")
    if not isinstance(components, list):
        raise CalculationContractError("modifier components must be a list")
    for index, component in enumerate(components):
        if not isinstance(component, dict):
            raise CalculationContractError(f"modifier component {index} must be an object")
        if not component.get("name"):
            raise CalculationContractError(f"modifier component {index} has no name")
        if component.get("included", True):
            _number(component.get("value"), f"modifier.components[{index}].value")
        elif not component.get("reason"):
            raise CalculationContractError(f"excluded modifier {component['name']!r} needs a reason")
    action_total = _number(calc.get("action_value_before_d20"), "modifier.action_value_before_d20")
    approach = _number(calc.get("realistic_approach"), "modifier.realistic_approach")
    if status == "complete" and approach <= 0:
        raise CalculationContractError("complete modifier calculation must select a positive Realistic Approach value")
    included_total = sum(
        float(component.get("value"))
        for component in components
        if component.get("included", True)
    )
    if not calc.get("team_action") and abs(action_total - (included_total + approach)) > 0.001:
        calc.setdefault("reconciliations", []).append({
            "field": "action_value_before_d20",
            "given": _intish(action_total),
            "reconciled": _intish(included_total + approach),
        })
        calc["action_value_before_d20"] = _intish(included_total + approach)
    participants = calc.get("participants", [])
    if participants is not None and not isinstance(participants, list):
        raise CalculationContractError("modifier participants must be a list")
    team = calc.get("team_action")
    if team is not None:
        if not isinstance(team, dict) or not team.get("main"):
            raise CalculationContractError("modifier team_action needs a main participant")
        _number(team.get("value_before_d20"), "modifier.team_action.value_before_d20")
        contributions = team.get("sub_contributions", [])
        if not isinstance(contributions, list):
            raise CalculationContractError("team sub_contributions must be a list")
        for item in contributions:
            if not isinstance(item, dict):
                raise CalculationContractError("team contribution must be an object")
            percentage = _number(item.get("percentage"), "team contribution percentage")
            sub_action = _number(item.get("sub_action_value"), "team contribution sub_action_value")
            contribution = _number(item.get("contribution"), "team contribution contribution")
            expected = sub_action * (percentage / 100)
            if abs(contribution - expected) > 0.001:
                raise CalculationContractError(
                    f"team contribution {contribution:g} does not equal {percentage:g}% of sub action {sub_action:g}"
                )
    if status == "complete" and not isinstance(calc.get("action_value_before_d20"), (int, float)):
        raise CalculationContractError("complete modifier calculation needs a numeric action value")
