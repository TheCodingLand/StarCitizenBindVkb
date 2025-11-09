from app.domain import (
    ActionIdentifier,
    Binding,
    BindingSet,
    ControlProfile,
    InputSlot,
)
from app.services import BindingPlanner, BindingPlannerContext


def make_binding(
    name: str,
    slot_id: str,
    *,
    side: str = "left",
    device: str = "js1",
    modifier: bool = False,
    hold: bool = False,
    multitap: bool = False,
) -> Binding:
    action = ActionIdentifier(name=name, main_category="mc", sub_category="sc")
    slot = InputSlot(device_uid=device, side=side, slot_id=slot_id)
    return Binding(
        action=action,
        slot=slot,
        modifier=modifier,
        hold=hold,
        multitap=multitap,
    )


def make_profile(
    left_bindings: list[Binding], right_bindings: list[Binding] | None = None
) -> ControlProfile:
    left = BindingSet(side="left")
    for binding in left_bindings:
        left.add(binding)

    right = BindingSet(side="right")
    for binding in right_bindings or []:
        right.add(binding)

    return ControlProfile(profile_name="test", left=left, right=right)


def test_plan_from_profile_collects_all_bindings() -> None:
    planner = BindingPlanner(BindingPlannerContext())
    profile = make_profile(
        [
            make_binding("action_one", "button1"),
            make_binding("action_two", "button2", modifier=True),
        ]
    )

    plan = planner.plan_from_profile(profile)

    assert len(plan.to_add) == 2
    assert plan.to_remove == []


def test_plan_diff_detects_additions_and_removals() -> None:
    planner = BindingPlanner(BindingPlannerContext())

    existing = make_profile(
        [
            make_binding("keep", "button1"),
            make_binding("remove", "button2"),
        ]
    )
    desired = make_profile(
        [
            make_binding("keep", "button1"),
            make_binding("add", "button3", modifier=True),
        ]
    )

    plan = planner.plan_diff(existing, desired.left.bindings.values())

    assert {binding.action.name for binding in plan.to_remove} == {"remove"}
    assert {binding.action.name for binding in plan.to_add} == {"add"}


def test_plan_diff_removals_reference_original_binding_instances() -> None:
    planner = BindingPlanner(BindingPlannerContext())

    binding_to_remove = make_binding(
        "remove_me",
        "button9",
        modifier=True,
        hold=True,
        multitap=True,
    )
    existing = make_profile(
        [
            make_binding("keep", "button1"),
            binding_to_remove,
        ]
    )

    # Desired bindings intentionally omit the binding, forcing a removal diff.
    plan = planner.plan_diff(
        existing, [b for b in existing.left.bindings.values() if b is not binding_to_remove]
    )

    assert len(plan.to_remove) == 1
    removal = plan.to_remove[0]

    # Ensure we removed the exact binding (identity) so downstream consumers have full detail.
    assert removal is binding_to_remove
    assert removal.slot.slot_id == "button9"
    assert removal.modifier and removal.hold and removal.multitap


def test_plan_diff_ignores_identical_desired_bindings() -> None:
    planner = BindingPlanner(BindingPlannerContext())

    existing_binding = make_binding("action", "button4", modifier=True)
    existing = make_profile([existing_binding])

    # Desired contains a structurally equivalent binding. Diff should be empty.
    desired = [make_binding("action", "button4", modifier=True)]

    plan = planner.plan_diff(existing, desired)

    assert not plan.to_add
    assert not plan.to_remove


def test_validate_plan_reports_no_changes() -> None:
    planner = BindingPlanner(BindingPlannerContext())
    empty_plan = BindingPlanner(BindingPlannerContext()).plan_from_profile(make_profile([]))
    empty_plan.to_add.clear()

    report = planner.validate_plan(empty_plan)

    assert not report.has_errors
    assert any("No binding changes" in issue.message for issue in report.issues)


def test_validate_plan_detects_duplicate_slot_assignments() -> None:
    existing = make_profile([])
    planner = BindingPlanner(BindingPlannerContext(default_profile=existing))
    desired = make_profile(
        [
            make_binding("action_one", "button1"),
            make_binding("action_two", "button1"),
        ]
    )

    plan = planner.plan_diff(existing, desired.left.bindings.values())
    report = planner.validate_plan(plan)

    assert report.has_errors
    assert any("duplicate slot assignment" in issue.message.lower() for issue in report.issues)


def test_validate_plan_detects_modifier_conflict_against_existing() -> None:
    existing = make_profile([make_binding("action", "button1")])
    planner = BindingPlanner(BindingPlannerContext(default_profile=existing))
    desired = make_profile(
        [
            make_binding("action", "button1"),
            make_binding("action_modifier", "button1", modifier=True),
        ]
    )

    plan = planner.plan_diff(existing, desired.left.bindings.values())
    report = planner.validate_plan(plan)

    assert report.has_errors
    assert any("modifier conflict" in issue.message.lower() for issue in report.issues)
