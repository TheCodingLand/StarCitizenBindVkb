from pathlib import Path

import pytest

from app.io import ActionCatalogRepository


def test_action_catalog_repository_loads_fixture_catalog() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))

    catalog = repo.load()

    assert catalog.version_key == "live-sc-alpha-3.24.2"
    assert "v_emergency_exit" in catalog.actions_by_name
    assert catalog.actionmap_by_name["v_emergency_exit"] == "seat_general"


def test_action_catalog_repository_raises_for_missing_file() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/missing.json"))

    with pytest.raises(FileNotFoundError):
        repo.load()