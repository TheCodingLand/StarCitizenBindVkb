from pathlib import Path

from app.domain import BindingEdit, TriggerMode
from app.io import ActionCatalogRepository, DeviceLayoutRepository, StarCitizenProfileRepository
from app.io.repositories import ActionMapsRepository as CompatActionMapsRepository
from app.io.repositories import DeviceLayoutRepository as CompatLayoutRepository


UNKNOWNS_FIXTURE = Path("tests/fixtures/profiles/profile_with_unknowns.xml")


def make_repository() -> StarCitizenProfileRepository:
    return StarCitizenProfileRepository(
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )


def test_load_profile_classifies_known_and_unknown_records() -> None:
    repo = make_repository()

    session = repo.load_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )

    assert session.profile.bindings
    assert session.profile.bindings[0].slot_id == "button18"
    assert session.profile.passthrough_records
    assert any(d.code == "unknown-slot" for d in session.diagnostics)
    assert any(d.code == "unknown-action" for d in session.diagnostics)
    assert any(record.device_token == "js2" for record in session.profile.passthrough_records)
    assert any(record.device_token == "kb1" for record in session.profile.passthrough_records)


def test_load_profile_marks_unresolved_device_when_role_map_is_missing() -> None:
    repo = make_repository()

    session = repo.load_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick"},
    )

    assert any(d.code == "unresolved-device" for d in session.diagnostics)


def test_load_profile_preserves_known_action_with_unknown_actionmap_as_passthrough(tmp_path: Path) -> None:
    repo = make_repository()
    mutated_fixture = tmp_path / "profile_unknown_actionmap.xml"
    mutated_fixture.write_text(
        UNKNOWNS_FIXTURE.read_text(encoding="utf-8").replace(
            'actionmap name="seat_general"',
            'actionmap name="bogus_map"',
            1,
        ),
        encoding="utf-8",
    )

    session = repo.load_profile(
        mutated_fixture,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    exported = repo.export_profile(session)

    assert not any(binding.source_actionmap_name == "bogus_map" for binding in session.profile.bindings)
    assert any(record.record_id.startswith("bogus_map:v_emergency_exit") for record in session.profile.passthrough_records)
    assert any(d.code == "unknown-actionmap" for d in session.diagnostics)
    assert exported.document is not None
    bogus_map = next(action_map for action_map in exported.document.actionmap if action_map.name == "bogus_map")
    bogus_action = next(action for action in bogus_map.action if action.name == "v_emergency_exit")
    assert any(rebind.input == "js1_button18" for rebind in bogus_action.rebind)


def test_compatibility_repository_wrapper_delegates_to_headless_repository() -> None:
    compat_repo = CompatActionMapsRepository(
        root=Path("tests/fixtures/profiles"),
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )

    session = compat_repo.load_control_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )

    assert session.profile.profile_name == "ProfileWithUnknowns"


def test_compatibility_repository_wrapper_saves_and_lists_profiles() -> None:
    compat_repo = CompatActionMapsRepository(
        root=Path("tests/fixtures/profiles"),
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )
    compat_layout_repo = CompatLayoutRepository()

    session = compat_repo.load_control_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    exported = compat_repo.save_control_profile(session)
    available_maps = {path.name for path in compat_repo.list_available_maps()}

    assert exported.document is not None
    assert "profile_with_unknowns.xml" in available_maps
    assert compat_layout_repo.list_layouts() == ["VKB Default"]


def test_real_exported_profile_fixture_round_trips_through_headless_repository() -> None:
    repo = make_repository()

    session = repo.load_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    exported = repo.export_profile(session)

    assert session.profile.bindings
    assert exported.document is not None
    assert exported.document.profileName == "VKB_final_3_22"


def test_default_profile_fixture_round_trips_through_headless_repository() -> None:
    repo = make_repository()

    session = repo.load_profile(
        Path("tests/fixtures/profiles/SCBindsDefault.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    exported = repo.export_profile(session)

    assert exported.document is not None
    assert exported.document.profileName == "Default"


def test_export_can_create_new_actionmap_for_valid_new_binding() -> None:
    repo = make_repository()

    session = repo.load_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    session.profile.bindings.append(
        BindingEdit(
            role="left_stick",
            slot_id="button4",
            action_name="v_toggle_qdrive_engagement",
            trigger_mode=TriggerMode.PLAIN,
        )
    )
    exported = repo.export_profile(session)

    quantum_map = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "spaceship_quantum"
    )
    qdrive_action = next(
        action for action in quantum_map.action if action.name == "v_toggle_qdrive_engagement"
    )

    assert any(rebind.input == "js1_button4" for rebind in qdrive_action.rebind)


def test_hold_binding_round_trips_activation_mode() -> None:
    repo = make_repository()

    session = repo.load_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    hold_binding = next(binding for binding in session.profile.bindings if binding.trigger_mode is TriggerMode.HOLD)
    exported = repo.export_profile(session)

    movement_map = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "spaceship_movement"
    )
    speed_limiter = next(
        action for action in movement_map.action if action.name == hold_binding.action_name
    )

    assert any(
        rebind.input == "js1_button5"
        and (rebind.model_extra or {}).get("@activationMode") == "delayed_press"
        for rebind in speed_limiter.rebind
    )


def test_multitap_binding_round_trips_multitap_flag() -> None:
    repo = make_repository()

    session = repo.load_profile(
        Path("tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml"),
        imported_role_map={"js1": "right_stick", "js2": "left_stick"},
    )
    multitap_binding = next(
        binding for binding in session.profile.bindings if binding.trigger_mode is TriggerMode.MULTITAP
    )
    exported = repo.export_profile(session)

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    action = next(item for item in seat_general.action if item.name == multitap_binding.action_name)

    assert any(
        rebind.input.endswith(multitap_binding.slot_id) and rebind.multitap == 2
        for rebind in action.rebind
    )


def test_duplicate_actionmap_round_trip_preserves_original_actionmaps() -> None:
    repo = make_repository()

    session = repo.load_profile(
        Path("tests/fixtures/profiles/profile_duplicate_actionmaps.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    exported = repo.export_profile(session)

    spaceship_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "spaceship_general"
    )
    vehicle_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "vehicle_general"
    )

    assert any(
        rebind.input == "js1_button1"
        for action in spaceship_general.action
        if action.name == "v_flightready"
        for rebind in action.rebind
    )
    assert any(
        rebind.input == "js2_button2"
        for action in vehicle_general.action
        if action.name == "v_flightready"
        for rebind in action.rebind
    )


def test_export_keeps_distinct_trigger_modes_for_same_input() -> None:
    repo = make_repository()

    session = repo.load_profile(
        UNKNOWNS_FIXTURE,
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    session.profile.bindings.append(
        BindingEdit(
            role="left_stick",
            slot_id="button6",
            action_name="v_emergency_exit",
            trigger_mode=TriggerMode.PLAIN,
        )
    )
    session.profile.bindings.append(
        BindingEdit(
            role="left_stick",
            slot_id="button6",
            action_name="v_emergency_exit",
            trigger_mode=TriggerMode.HOLD,
        )
    )

    exported = repo.export_profile(session)

    seat_general = next(
        action_map for action_map in exported.document.actionmap if action_map.name == "seat_general"
    )
    emergency_exit = next(action for action in seat_general.action if action.name == "v_emergency_exit")
    button6_rebinds = [rebind for rebind in emergency_exit.rebind if rebind.input == "js1_button6"]

    assert len(button6_rebinds) == 2
    assert any((rebind.model_extra or {}).get("@activationMode") == "delayed_press" for rebind in button6_rebinds)
    assert any((rebind.model_extra or {}).get("@activationMode") is None for rebind in button6_rebinds)