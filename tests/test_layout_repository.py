from app.io import DeviceLayoutRepository


def test_layout_repository_loads_vkb_default_left_layout() -> None:
    repo = DeviceLayoutRepository()

    layout = repo.load_layout("VKB Default", "left")

    assert layout is not None
    assert layout.side == "left"
    assert "button1" in layout.slots


def test_layout_repository_returns_none_for_unknown_layout() -> None:
    repo = DeviceLayoutRepository()

    assert repo.load_layout("Missing Device", "left") is None


def test_layout_repository_returns_none_for_unsupported_side() -> None:
    repo = DeviceLayoutRepository()

    assert repo.load_layout("VKB Default", "throttle") is None