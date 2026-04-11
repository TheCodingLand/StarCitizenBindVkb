from pathlib import Path

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