"""Service responsible for translating UI intents into control-map mutations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from app.domain import Binding, BindingPlan, ControlProfile, ValidationIssue, ValidationReport


@dataclass
class BindingPlannerContext:
    """Aggregates dependencies required by the binding planner."""

    default_profile: Optional[ControlProfile] = None


class BindingPlanner:
    """Coordinates the application of binding operations across devices."""

    def __init__(self, context: BindingPlannerContext) -> None:
        self.context = context

    def plan_from_profile(self, profile: ControlProfile) -> BindingPlan:
        """Generate a plan from an existing ControlProfile."""

        plan = BindingPlan()
        for binding in profile.iter_bindings():
            plan.record_add(binding)
        return plan

    def plan_diff(
        self,
        current_profile: ControlProfile,
        desired_bindings: Iterable[Binding],
    ) -> BindingPlan:
        """Calculate the diff between the current profile and desired bindings."""

        plan = BindingPlan()
        current_keys = {binding.key: binding for binding in current_profile.iter_bindings()}
        desired_keys = {binding.key: binding for binding in desired_bindings}

        for key in current_keys.keys() - desired_keys.keys():
            plan.record_remove(key)

        for key, binding in desired_keys.items():
            if key not in current_keys:
                plan.record_add(binding)

        return plan

    def validate_plan(self, plan: BindingPlan) -> ValidationReport:
        """Validate a binding plan before execution."""

        report = plan.validation
        if not plan.to_add and not plan.to_remove:
            report.add(
                ValidationIssue(
                    level="info",
                    message="No binding changes detected.",
                )
            )
        return report
