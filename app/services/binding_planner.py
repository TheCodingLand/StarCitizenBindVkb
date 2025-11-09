"""Service responsible for translating UI intents into control-map mutations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

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
            plan.record_remove(current_keys[key])

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

        slot_key = self._make_slot_key

        occupancy: Dict[Tuple[str, str, str], List[Binding]] = defaultdict(list)
        if self.context.default_profile is not None:
            for binding in self.context.default_profile.iter_bindings():
                occupancy[slot_key(binding)].append(binding)

        for binding in plan.to_remove:
            key = slot_key(binding)
            if key not in occupancy:
                continue
            remaining = [existing for existing in occupancy[key] if existing.key != binding.key]
            if remaining:
                occupancy[key] = remaining
            else:
                occupancy.pop(key)

        additions_by_slot: Dict[Tuple[str, str, str], List[Binding]] = defaultdict(list)
        for binding in plan.to_add:
            additions_by_slot[slot_key(binding)].append(binding)

        for key, bindings in additions_by_slot.items():
            slot_desc = f"{key[0]}:{key[2]}"
            actions_list = ", ".join(sorted({binding.action.name for binding in bindings}))

            if len(bindings) > 1:
                modifier_values = {binding.modifier for binding in bindings}
                if len(modifier_values) > 1:
                    report.add(
                        ValidationIssue(
                            level="error",
                            message=(
                                f"Modifier conflict: slot {slot_desc} receives both modifier and "
                                f"non-modifier bindings ({actions_list})."
                            ),
                            slot=bindings[0].slot,
                        )
                    )
                else:
                    report.add(
                        ValidationIssue(
                            level="error",
                            message=(
                                f"Duplicate slot assignment: slot {slot_desc} receives multiple "
                                f"bindings ({actions_list})."
                            ),
                            slot=bindings[0].slot,
                        )
                    )

            existing_bindings = occupancy.get(key, [])
            if existing_bindings:
                existing_actions = ", ".join(
                    sorted({binding.action.name for binding in existing_bindings})
                )
                existing_modifiers = {binding.modifier for binding in existing_bindings}
                addition_modifiers = {binding.modifier for binding in bindings}
                if existing_modifiers ^ addition_modifiers:
                    reason = "modifier conflict"
                else:
                    reason = "slot already mapped"
                report.add(
                    ValidationIssue(
                        level="error",
                        message=(
                            f"{reason.capitalize()}: slot {slot_desc} currently mapped to {existing_actions}; "
                            f"cannot add {actions_list}."
                        ),
                        slot=bindings[0].slot,
                    )
                )

        return report

    @staticmethod
    def _make_slot_key(binding: Binding) -> Tuple[str, str, str]:
        return binding.slot.device_uid, binding.slot.side, binding.slot.slot_id
