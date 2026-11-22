"""Dedicated Lead Resolver boundary for private autonomous backend ticks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from brain.assumption_wizard import AssumptionWizard
from brain.lead_resolver import LeadResolver


class BackendLeadResolver:
    """Resolve hidden autonomous plans from frozen specialist analysis.

    The backend resolver owns the decision boundary for autonomous actions. It
    may use a player-authorized temporary assumption, but it never narrates,
    edits campaign files, or silently invents an outcome.
    """

    def __init__(self, repo_root: str | Path = "."):
        self.root = Path(repo_root).resolve()
        self.lead_resolver = LeadResolver(self.root)

    def resolve(
        self,
        specialist_output: dict[str, Any],
        *,
        plan: dict[str, Any],
        context: dict[str, Any],
        dice_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        linked = context.get("active_clarification") or context.get("previous_clarification")
        backend_context = {
            **context,
            "backend_autonomy": True,
            "private_background": True,
            "backend_plan": plan,
            "message": "Resolve this private autonomous phase from the specialist handoff.",
        }
        if isinstance(linked, dict) and linked.get("status") == "answered":
            # Preserve the exact player answer and original option/result link;
            # backend resolution must not regenerate or detach it.
            backend_context["clarification_continuation"] = linked
        existing_assumption = context.get("assumption_record")
        if isinstance(existing_assumption, dict) and existing_assumption.get("status") == "provisional":
            assumption = existing_assumption
        else:
            assumption = AssumptionWizard(self.root).maybe_create(backend_context, specialist_output)
        if assumption:
            backend_context["assumption_record"] = assumption
        return self.lead_resolver.resolve(
            specialist_output,
            chat_context=backend_context,
            campaign_context=backend_context,
            dice_result=dice_result,
        )
