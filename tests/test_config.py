from pathlib import Path
from typing import Iterator

import pytest

import app.config as app_config


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Iterator[Path]:
    original_path = app_config.get_config_path()
    config_path = tmp_path / "config.json"
    app_config.set_config_path(config_path)
    yield config_path
    app_config.set_config_path(original_path)


def test_get_config_creates_file_and_uses_cache(temp_config_file: Path) -> None:
    first = app_config.Config.get_config()
    assert temp_config_file.exists()
    second = app_config.Config.get_config()
    assert first is second


def test_get_config_force_reload_refreshes_from_disk(temp_config_file: Path) -> None:
    config = app_config.Config.get_config()
    config.install_type = "PTU"
    config.save()
    config.install_type = "LIVE"
    reloaded = app_config.Config.get_config(force_reload=True)
    assert reloaded.install_type == "PTU"


def test_get_config_invalid_json_raises_value_error(temp_config_file: Path) -> None:
    temp_config_file.write_text("{invalid json}")
    with pytest.raises(ValueError):
        app_config.Config.get_config(force_reload=True)
