from pathlib import Path

import pytest

from app.domain import (
    BindingEdit,
    BindingInput,
    BindingReference,
    BindingSession,
    ExportResult,
    GameCatalog,
    GameCatalogVersion,
    PassthroughRecord,
    SessionCatalogSnapshot,
    TriggerMode,
    WorkingProfile,
)
from app.io import ActionCatalogRepository, DeviceLayoutRepository, StarCitizenProfileRepository
from app.services import BindingSessionService


def make_repository() -> StarCitizenProfileRepository:
    return StarCitizenProfileRepository(
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )


def make_binding_reference(binding) -> BindingReference:
    return BindingReference(
        role=binding.role,
        slot_id=binding.slot_id,
        action_name=binding.action_name,
        trigger_mode=binding.trigger_mode,
        modifier_token=binding.modifier_token,
        source_record_id=binding.source_record_id,
        source_actionmap_name=binding.source_actionmap_name,
        replaced_passthrough_record_id=binding.replaced_passthrough_record_id,
    )


def binding_snapshot(session: BindingSession) -> list[tuple[str, str, str, TriggerMode, str | None, str | None, str | None]]:
    return sorted(
        (
            binding.role,
            binding.slot_id,
            binding.action_name,
            binding.trigger_mode,
            binding.modifier_token,
            binding.source_actionmap_name,
            binding.replaced_passthrough_record_id,
        )
        for binding in session.profile.bindings
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


def test_open_profile_captures_catalog_snapshot_used_for_session() -> None:
    repository = make_repository()
    original_catalog = repository.catalog_repo.load()
    mutated_catalog = GameCatalog(version=GameCatalogVersion(key="mutated-catalog"))
    load_count = 0

    def load_catalog() -> GameCatalog:
        nonlocal load_count
        load_count += 1
        if load_count == 1:
            return original_catalog
        return mutated_catalog

    repository.catalog_repo.load = load_catalog  # type: ignore[method-assign]
    service = BindingSessionService(repository)

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )

    assert isinstance(session.catalog_snapshot, SessionCatalogSnapshot)
    assert session.catalog_snapshot.version.key == "live-sc-alpha-3.24.2"
    assert session.catalog_snapshot.catalog.version_key == session.catalog_snapshot.version.key
    assert session.catalog_snapshot.catalog.entry_for("v_emergency_exit", "seat_general") is not None


def test_open_profile_can_override_export_device_tokens_and_instances() -> None:
    repository = make_repository()
    service = BindingSessionService(repository)

    session = service.open_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
        export_role_tokens={"left_stick": "js1", "right_stick": "js2"},
    )
    exported = repository.export_profile(session)

    assert session.profile.role_device_tokens == {"left_stick": "js1", "right_stick": "js2"}
    assert exported.document is not None

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    quantum_toggle = next(action for action in seat_general.action if action.name == "v_toggle_quantum_mode")
    left_option = next(option for option in exported.document.options if option.type == "joystick" and "EVO L" in (option.product or ""))
    right_option = next(option for option in exported.document.options if option.type == "joystick" and "EVO R" in (option.product or ""))

    assert any(rebind.input == "js1_button20" for rebind in quantum_toggle.rebind)
    assert left_option.instance == 1
    assert right_option.instance == 2


def test_bind_validation_uses_catalog_captured_at_session_open(monkeypatch: pytest.MonkeyPatch) -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    baseline_unknown_action_count = sum(d.code == "unknown-action" for d in session.diagnostics)
    monkeypatch.setattr(
        service.profile_repository.catalog_repo,
        "load",
        lambda: GameCatalog(version=GameCatalogVersion(key="mutated-catalog")),
    )

    updated = service.bind("left_stick", "button3", "v_emergency_exit", "plain")

    assert any(
        binding.role == "left_stick"
        and binding.slot_id == "button3"
        and binding.action_name == "v_emergency_exit"
        for binding in updated.profile.bindings
    )
    assert sum(d.code == "unknown-action" for d in updated.diagnostics) == baseline_unknown_action_count


def test_export_uses_catalog_captured_at_session_open() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("left_stick", "button3", "v_emergency_exit", "plain")
    service.profile_repository._catalog = GameCatalog(version=GameCatalogVersion(key="mutated-catalog"))

    exported = service.export()

    assert exported.document is not None
    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    assert any(rebind.input == "js1_button3" for rebind in emergency_exit.rebind)


def test_remove_binding_reference_removes_only_the_target_binding() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    target_binding = next(binding for binding in session.profile.bindings if binding.action_name == "v_emergency_exit")

    updated = service.remove_binding(make_binding_reference(target_binding))

    assert all(
        binding.source_record_id != target_binding.source_record_id
        for binding in updated.profile.bindings
    )
    assert any(binding.action_name == "v_ifcs_toggle_speed_limiter" for binding in updated.profile.bindings)


def test_move_binding_reference_restores_original_on_rejected_target() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    target_binding = next(binding for binding in session.profile.bindings if binding.action_name == "v_emergency_exit")
    before = binding_snapshot(session)
    baseline_unknown_slot_count = sum(d.code == "unknown-slot" for d in session.diagnostics)

    updated = service.move_binding(make_binding_reference(target_binding), "not_a_real_slot")

    assert binding_snapshot(updated) == before
    assert sum(d.code == "unknown-slot" for d in updated.diagnostics) == baseline_unknown_slot_count + 1


def test_move_binding_reference_restores_original_on_unexpected_bind_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    target_binding = next(binding for binding in session.profile.bindings if binding.action_name == "v_emergency_exit")
    before = binding_snapshot(session)

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "_upsert_binding", explode)

    with pytest.raises(RuntimeError, match="boom"):
        service.move_binding(make_binding_reference(target_binding), "button3")

    assert binding_snapshot(service._require_session()) == before


def test_move_binding_reference_preserves_provenance_and_modifier_state() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    modifier_binding = next(
        binding for binding in session.profile.bindings if binding.trigger_mode is TriggerMode.MODIFIER
    )

    updated = service.move_binding(make_binding_reference(modifier_binding), "button4")
    moved_binding = next(
        binding
        for binding in updated.profile.bindings
        if binding.action_name == modifier_binding.action_name and binding.slot_id == "button4"
    )

    assert moved_binding.trigger_mode is TriggerMode.MODIFIER
    assert moved_binding.modifier_token == modifier_binding.modifier_token
    assert moved_binding.source_actionmap_name == modifier_binding.source_actionmap_name


def test_move_binding_reference_rejects_ambiguous_duplicate_name_import() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_duplicate_actionmaps.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    target_binding = next(
        binding
        for binding in session.profile.bindings
        if binding.action_name == "v_flightready" and binding.source_actionmap_name == "spaceship_general"
    )
    before = binding_snapshot(session)
    baseline_ambiguous_count = sum(d.code == "ambiguous-actionmap" for d in session.diagnostics)

    updated = service.move_binding(make_binding_reference(target_binding), "button3")

    assert binding_snapshot(updated) == before
    assert sum(d.code == "ambiguous-actionmap" for d in updated.diagnostics) == baseline_ambiguous_count + 1


def test_move_binding_reference_rejects_target_slot_occupied_by_ambiguous_import() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_duplicate_actionmaps.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("left_stick", "button3", "v_toggle_qdrive_engagement", "plain")
    source_binding = next(
        binding
        for binding in session.profile.bindings
        if binding.slot_id == "button3" and binding.action_name == "v_toggle_qdrive_engagement"
    )
    before = binding_snapshot(session)
    baseline_ambiguous_count = sum(d.code == "ambiguous-actionmap" for d in session.diagnostics)

    updated = service.move_binding(make_binding_reference(source_binding), "button1")

    assert binding_snapshot(updated) == before
    assert sum(d.code == "ambiguous-actionmap" for d in updated.diagnostics) == baseline_ambiguous_count + 1


def test_remove_binding_reference_accepts_ambiguous_duplicate_name_import_by_identity() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_duplicate_actionmaps.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    target_binding = next(
        binding
        for binding in session.profile.bindings
        if binding.action_name == "v_flightready" and binding.source_actionmap_name == "spaceship_general"
    )

    updated = service.remove_binding(make_binding_reference(target_binding))

    assert len(updated.profile.bindings) == 1
    assert updated.profile.bindings[0].source_actionmap_name == "vehicle_general"
    assert updated.profile.bindings[0].slot_id == "button2"


def test_move_binding_reference_preserves_passthrough_replacement_identity() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
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

    replacement_binding = next(
        binding
        for binding in service._require_session().profile.bindings
        if binding.slot_id == "button3" and binding.replaced_passthrough_record_id is not None
    )
    updated = service.move_binding(make_binding_reference(replacement_binding), "button4")
    moved_binding = next(
        binding
        for binding in updated.profile.bindings
        if binding.slot_id == "button4" and binding.action_name == replacement_binding.action_name
    )

    assert moved_binding.replaced_passthrough_record_id == replacement_binding.replaced_passthrough_record_id
    assert moved_binding.source_actionmap_name == replacement_binding.source_actionmap_name


def test_move_binding_reference_overwrites_occupied_target_metadata() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
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
    service.bind("right_stick", "button4", "v_toggle_qdrive_engagement", "plain")
    source_binding = next(
        binding
        for binding in service._require_session().profile.bindings
        if binding.slot_id == "button4" and binding.action_name == "v_toggle_qdrive_engagement"
    )

    updated = service.move_binding(make_binding_reference(source_binding), "button3")
    moved_binding = next(
        binding
        for binding in updated.profile.bindings
        if binding.slot_id == "button3" and binding.action_name == "v_toggle_qdrive_engagement"
    )

    assert moved_binding.source_actionmap_name == "spaceship_quantum"
    assert moved_binding.replaced_passthrough_record_id is None


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
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")

    exported = service.export()

    assert exported.blocked_conflicts
    assert exported.blocked_conflicts[0].slot_token == "button2"


def test_preserve_passthrough_discards_conflicting_edit() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")

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
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")

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
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
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
    unknown_custom_action = next(
        action for action in seat_general.action if action.name == "v_unknown_custom_action"
    )

    assert any(rebind.input == "js2_button3" for rebind in emergency_exit.rebind)
    assert all(rebind.input != "js2_button2" for rebind in emergency_exit.rebind)
    assert all(rebind.input != "js2_button2" for rebind in unknown_custom_action.rebind)


def test_modifier_binding_round_trips_without_losing_modifier_token() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    modifier_binding = next(
        binding for binding in session.profile.bindings if binding.action_name == "prone_rollleft"
    )
    device_token = session.profile.role_device_tokens[modifier_binding.role]

    service.bind(
        modifier_binding.role,
        modifier_binding.slot_id,
        modifier_binding.action_name,
        modifier_binding.trigger_mode.value,
    )
    exported = service.profile_repository.export_profile(session)

    action_map = next(
        item for item in exported.document.actionmap if item.name == "prone"
    )
    action = next(item for item in action_map.action if item.name == modifier_binding.action_name)
    assert any(
        rebind.input == f"{device_token}_{modifier_binding.modifier_token}+{modifier_binding.slot_id}"
        and (rebind.model_extra or {}).get("@activationMode") == "press"
        for rebind in action.rebind
    )


def test_modifier_binding_without_press_activation_mode_round_trips_without_press() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    modifier_binding = next(
        binding
        for binding in session.profile.bindings
        if binding.action_name == "v_weapon_bombing_hud_range_decrease"
    )
    device_token = session.profile.role_device_tokens[modifier_binding.role]

    service.bind(
        modifier_binding.role,
        modifier_binding.slot_id,
        modifier_binding.action_name,
        modifier_binding.trigger_mode.value,
    )
    exported = service.profile_repository.export_profile(session)

    action_map = next(
        item for item in exported.document.actionmap if item.name == "spaceship_missiles"
    )
    action = next(item for item in action_map.action if item.name == modifier_binding.action_name)
    assert any(
        rebind.input == f"{device_token}_{modifier_binding.modifier_token}+{modifier_binding.slot_id}"
        and (rebind.model_extra or {}).get("@activationMode") is None
        for rebind in action.rebind
    )


def test_bind_preserves_existing_modifier_token_on_in_place_rebind() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    modifier_binding = next(
        binding for binding in session.profile.bindings if binding.trigger_mode is TriggerMode.MODIFIER
    )
    modifier_binding.modifier_token = "lctrl"
    device_token = session.profile.role_device_tokens[modifier_binding.role]

    service.bind(
        modifier_binding.role,
        modifier_binding.slot_id,
        modifier_binding.action_name,
        modifier_binding.trigger_mode.value,
    )
    exported = service.profile_repository.export_profile(session)

    assert exported.document is not None
    action_map = next(
        item for item in exported.document.actionmap if item.name == modifier_binding.source_actionmap_name
    )
    action = next(item for item in action_map.action if item.name == modifier_binding.action_name)
    assert any(rebind.input == f"{device_token}_lctrl+{modifier_binding.slot_id}" for rebind in action.rebind)


def test_service_export_keeps_distinct_trigger_modes_for_same_input() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("left_stick", "button6", "v_emergency_exit", "plain")
    service.bind("left_stick", "button6", "v_emergency_exit", "hold")

    exported = service.export()

    assert exported.document is not None
    assert not any(d.code == "validation-error" for d in service._require_session().diagnostics)


def test_rebinding_existing_passthrough_replacement_preserves_replacement_identity() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
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
    service.bind("right_stick", "button3", "v_toggle_qdrive_engagement", "plain")
    exported = service.export()

    assert exported.document is not None
    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    unknown_custom_action = next(
        action for action in seat_general.action if action.name == "v_unknown_custom_action"
    )
    quantum_map = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "spaceship_quantum"
    )
    qdrive_action = next(
        action for action in quantum_map.action if action.name == "v_toggle_qdrive_engagement"
    )

    assert all(rebind.input != "js2_button2" for rebind in unknown_custom_action.rebind)
    assert any(rebind.input == "js2_button3" for rebind in qdrive_action.rebind)


def test_failed_export_counts_only_unreplaced_passthrough_records() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
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
    service._require_session().profile.bindings.append(
        BindingEdit(
            role="right_stick",
            slot_id="button3",
            action_name="v_toggle_qdrive_engagement",
            trigger_mode=TriggerMode.PLAIN,
        )
    )

    failed_export = service.export()

    assert failed_export.document is None
    assert failed_export.preserved_passthrough_count == len(service._require_session().profile.passthrough_records) - 1


def test_bind_rejects_unknown_action_before_export() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    updated = service.bind("left_stick", "button3", "not_in_catalog", "plain")
    exported = service.export()

    assert not any(binding.action_name == "not_in_catalog" for binding in updated.profile.bindings)
    assert any(d.code == "unknown-action" for d in updated.diagnostics)
    assert all(
        action.name != "not_in_catalog"
        for action_map in exported.document.actionmap
        for action in action_map.action
    )


def test_bind_rejects_role_without_imported_device_token() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick"},
    )
    updated = service.bind("right_stick", "button3", "v_emergency_exit", "plain")
    exported = service.export()

    assert not any(
        binding.role == "right_stick" and binding.slot_id == "button3"
        for binding in updated.profile.bindings
    )
    assert any(d.code == "unresolved-device" for d in updated.diagnostics)
    assert all(
        rebind.input != "right_stick_button3"
        for action_map in exported.document.actionmap
        for action in action_map.action
        for rebind in action.rebind
    )


def test_bind_rejects_ambiguous_modifier_slot_without_modifier_token() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    session.profile.bindings.extend(
        [
            BindingEdit(
                role="left_stick",
                slot_id="button18",
                action_name="v_emergency_exit",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="rctrl",
                source_actionmap_name="seat_general",
            ),
            BindingEdit(
                role="left_stick",
                slot_id="button18",
                action_name="v_toggle_qdrive_engagement",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="lalt",
                source_actionmap_name="spaceship_quantum",
            ),
        ]
    )
    before = binding_snapshot(session)
    baseline_ambiguous_count = sum(d.code == "ambiguous-modifier-token" for d in session.diagnostics)

    updated = service.bind("left_stick", "button18", "v_ifcs_toggle_speed_limiter", "modifier")

    assert binding_snapshot(updated) == before
    assert sum(d.code == "ambiguous-modifier-token" for d in updated.diagnostics) == baseline_ambiguous_count + 1


def test_unbind_rejects_ambiguous_modifier_slot_without_modifier_token() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    session.profile.bindings.extend(
        [
            BindingEdit(
                role="left_stick",
                slot_id="button18",
                action_name="v_emergency_exit",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="rctrl",
                source_actionmap_name="seat_general",
            ),
            BindingEdit(
                role="left_stick",
                slot_id="button18",
                action_name="v_toggle_qdrive_engagement",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="lalt",
                source_actionmap_name="spaceship_quantum",
            ),
        ]
    )
    before = binding_snapshot(session)
    baseline_ambiguous_count = sum(d.code == "ambiguous-modifier-token" for d in session.diagnostics)

    updated = service.unbind("left_stick", "button18", "modifier")

    assert binding_snapshot(updated) == before
    assert sum(d.code == "ambiguous-modifier-token" for d in updated.diagnostics) == baseline_ambiguous_count + 1


def test_move_binding_reference_rejects_ambiguous_modifier_target_slot() -> None:
    service = BindingSessionService(make_repository())

    session = service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    session.profile.bindings.extend(
        [
            BindingEdit(
                role="left_stick",
                slot_id="button18",
                action_name="v_emergency_exit",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="rctrl",
                source_actionmap_name="seat_general",
            ),
            BindingEdit(
                role="left_stick",
                slot_id="button18",
                action_name="v_toggle_qdrive_engagement",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="lalt",
                source_actionmap_name="spaceship_quantum",
            ),
        ]
    )
    session = service.bind("left_stick", "button17", "v_ifcs_toggle_speed_limiter", "modifier")
    source_binding = next(
        binding
        for binding in session.profile.bindings
        if binding.role == "left_stick"
        and binding.slot_id == "button17"
        and binding.trigger_mode is TriggerMode.MODIFIER
    )
    before = binding_snapshot(session)
    baseline_ambiguous_count = sum(d.code == "ambiguous-modifier-token" for d in session.diagnostics)

    updated = service.move_binding(make_binding_reference(source_binding), "button18")

    assert binding_snapshot(updated) == before
    assert sum(d.code == "ambiguous-modifier-token" for d in updated.diagnostics) == baseline_ambiguous_count + 1


def test_bind_rejects_invalid_slot_before_export() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    updated = service.bind("left_stick", "not_a_real_slot", "v_emergency_exit", "plain")
    exported = service.export()

    assert not any(binding.slot_id == "not_a_real_slot" for binding in updated.profile.bindings)
    assert any(d.code == "unknown-slot" for d in updated.diagnostics)
    assert all(
        rebind.input != "js1_not_a_real_slot"
        for action_map in exported.document.actionmap
        for action in action_map.action
        for rebind in action.rebind
    )


def test_rebinding_existing_control_moves_binding_to_new_actionmap() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("left_stick", "button18", "v_ifcs_toggle_speed_limiter", "plain")
    exported = service.export()

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    movement_map = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "spaceship_movement"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    speed_limiter = next(
        action for action in movement_map.action if action.name == "v_ifcs_toggle_speed_limiter"
    )

    assert all(rebind.input != "js1_button18" for rebind in emergency_exit.rebind)
    assert any(rebind.input == "js1_button18" for rebind in speed_limiter.rebind)


def test_replace_passthrough_rejects_invalid_replacement_without_dropping_conflict() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
    blocked = service.export()

    service.replace_passthrough(
        blocked.blocked_conflicts[0].conflict_id,
        BindingInput(
            role="right_stick",
            slot_id="button3",
            action_name="not_in_catalog",
            trigger_mode=TriggerMode.PLAIN,
        ),
    )
    exported = service.export()

    assert exported.blocked_conflicts
    assert any(d.code == "unknown-action" for d in service._require_session().diagnostics)


def test_bind_rejects_ambiguous_duplicate_actionmap_action() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_duplicate_actionmaps.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    updated = service.bind("left_stick", "button3", "v_flightready", "plain")
    exported = service.export()

    assert any(d.code == "ambiguous-actionmap" for d in updated.diagnostics)
    assert all(
        rebind.input != "js1_button3"
        for action_map in exported.document.actionmap
        for action in action_map.action
        for rebind in action.rebind
    )


def test_unbinding_replacement_restores_original_passthrough_record() -> None:
    service = BindingSessionService(make_repository())

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "button2", "v_emergency_exit", "plain")
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
    service.unbind("right_stick", "button3", "plain")
    exported = service.export()

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    unknown_custom_action = next(
        action for action in seat_general.action if action.name == "v_unknown_custom_action"
    )

    assert all(rebind.input != "js2_button3" for rebind in emergency_exit.rebind)
    assert any(rebind.input == "js2_button2" for rebind in unknown_custom_action.rebind)