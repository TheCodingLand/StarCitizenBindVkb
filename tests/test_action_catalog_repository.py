from pathlib import Path

import pytest

from app.domain import TriggerMode
from app.io import ActionCatalogRepository


def test_action_catalog_repository_loads_fixture_catalog() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))

    catalog = repo.load()

    assert catalog.version_key == "live-sc-alpha-3.24.2"
    assert "v_emergency_exit" in catalog.actions_by_name
    assert catalog.actionmap_by_name["v_emergency_exit"] == "seat_general"


def test_action_catalog_repository_exposes_provenance_aware_entries() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))

    catalog = repo.load()
    entry = catalog.entry_for("v_emergency_exit", None)

    assert entry is not None
    assert catalog.entry_for("v_emergency_exit", "seat_general") == entry
    assert entry.action_name == "v_emergency_exit"
    assert entry.actionmap_name == "seat_general"
    assert entry.category == "@ui_CCSeatGeneral"
    assert entry.subcategory == "@ui_CGSeatGeneral"
    assert entry.display_label == "@ui_CIEmergencyExit"
    assert entry.supports_joystick is True
    assert TriggerMode.PLAIN in entry.supported_trigger_modes


def test_action_catalog_repository_rejects_ambiguous_name_only_lookup() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))

    catalog = repo.load()
    spaceship_entry = catalog.entry_for("v_flightready", "spaceship_general")
    vehicle_entry = catalog.entry_for("v_flightready", "vehicle_general")

    assert spaceship_entry is not None
    assert spaceship_entry.actionmap_name == "spaceship_general"
    assert vehicle_entry is not None
    assert vehicle_entry.actionmap_name == "vehicle_general"
    assert catalog.entry_for("v_flightready", None) is None


def test_action_catalog_repository_raises_for_missing_file() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/missing.json"))

    with pytest.raises(FileNotFoundError):
        repo.load()