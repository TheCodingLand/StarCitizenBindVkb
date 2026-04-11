from pathlib import Path

from app.domain import BindingInput, BindingSession, ExportResult, PassthroughRecord, TriggerMode, WorkingProfile
from app.io import ActionCatalogRepository, DeviceLayoutRepository, StarCitizenProfileRepository
from app.services import BindingSessionService


def make_repository() -> StarCitizenProfileRepository:
    return StarCitizenProfileRepository(
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )


def test_working_profile_keeps_bindings_and_passthrough_separate() -> None:
    profile = WorkingProfile(profile_name="fixture")

    profile.passthrough_records.append(
        PassthroughRecord(
            record_id="pt-1",
            action_name="unknown_action",
            device_token="js2",
            slot_token="unknown_button",
            trigger_token="plain",
            raw_payload={"@input": "js2_unknown_button"},
        )
    )

    assert profile.bindings == []
    assert profile.passthrough_records[0].device_token == "js2"


def test_trigger_mode_value_is_stable() -> None:
    assert TriggerMode.PLAIN.value == "plain"


def test_export_result_starts_unblocked() -> None:
    result = ExportResult()

    assert result.blocked_conflicts == []
    assert result.preserved_passthrough_count == 0


def test_binding_session_exposes_profile_and_diagnostics() -> None:
    session = BindingSession(profile=WorkingProfile(profile_name="fixture"))

    assert session.profile.profile_name == "fixture"
    assert session.diagnostics == []


def test_bind_and_export_updates_known_binding_without_dropping_passthrough() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("left_stick", "button1", "v_emergency_exit", "plain")

    exported = service.export()

    assert exported.changed_bindings
    assert exported.preserved_passthrough_count >= 2
    assert exported.document is not None

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    assert any(rebind.input == "js1_button1" for rebind in emergency_exit.rebind)


def test_export_blocks_when_edit_conflicts_with_passthrough() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "unknown_button", "v_emergency_exit", "plain")

    exported = service.export()

    assert exported.blocked_conflicts
    assert exported.blocked_conflicts[0].slot_token == "unknown_button"


def test_preserve_passthrough_discards_conflicting_edit() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "unknown_button", "v_emergency_exit", "plain")

    blocked = service.export()

    service.preserve_passthrough(blocked.blocked_conflicts[0].conflict_id)
    exported = service.export()

    assert exported.blocked_conflicts == []


def test_discard_pending_edit_removes_conflicting_binding() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "unknown_button", "v_emergency_exit", "plain")

    blocked = service.export()

    service.discard_pending_edit(blocked.blocked_conflicts[0].conflict_id)
    exported = service.export()

    assert exported.blocked_conflicts == []


def test_unbind_removes_existing_editable_binding_from_export() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.unbind("left_stick", "button18", "plain")

    exported = service.export()

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    assert all(rebind.input != "js1_button18" for rebind in emergency_exit.rebind)


def test_replace_passthrough_adds_replacement_binding() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "unknown_button", "v_emergency_exit", "plain")
    blocked = service.export()

    service.replace_passthrough(
        blocked.blocked_conflicts[0].conflict_id,
        BindingInput(
            role="right_stick",
            slot_id="button3",
            action_name="v_emergency_exit",
            trigger_mode=TriggerMode.PLAIN,
        ),
    )
    exported = service.export()

    assert exported.blocked_conflicts == []
    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    assert any(rebind.input == "js2_button3" for rebind in emergency_exit.rebind)


def test_modifier_binding_round_trips_without_losing_modifier_token() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    modifier_binding = next(
        binding for binding in session.profile.bindings if binding.trigger_mode is TriggerMode.MODIFIER
    )

    service.bind(
        modifier_binding.role,
        modifier_binding.slot_id,
        modifier_binding.action_name,
        modifier_binding.trigger_mode.value,
    )
    exported = service.profile_repository.export_profile(session)

    action_map = next(
        item for item in exported.document.actionmap if item.name == "seat_general"
    )
    action = next(item for item in action_map.action if item.name == modifier_binding.action_name)
    assert any(
        rebind.input == f"js1_{modifier_binding.modifier_token}+{modifier_binding.slot_id}"
        for rebind in action.rebind
    )