from __future__ import annotations

from typing import Any

from app.utils.devices import PygameJoystickBackend


class FakeJoystick:
    def __init__(self, index: int) -> None:
        self.index = index
        self._initialized = False
        self.init_calls = 0

    def get_init(self) -> bool:
        return self._initialized

    def init(self) -> None:
        self._initialized = True
        self.init_calls += 1

    def get_name(self) -> str:
        return f"Joystick {self.index}"

    def get_guid(self) -> str:
        return f"guid-{self.index}"

    def get_numaxes(self) -> int:
        return 2

    def get_numbuttons(self) -> int:
        return 3

    def get_numhats(self) -> int:
        return 1

    def get_button(self, index: int) -> int:
        return 1 if index == 0 else 0

    def get_hat(self, index: int) -> tuple[int, int]:
        del index
        return (0, 0)

    def get_axis(self, index: int) -> float:
        return 0.5 if index == 0 else 0.0


class FakeJoystickModule:
    def __init__(self) -> None:
        self._initialized = False
        self.factory_calls = 0
        self.joysticks = {0: FakeJoystick(0), 1: FakeJoystick(1)}

    def get_init(self) -> bool:
        return self._initialized

    def init(self) -> None:
        self._initialized = True

    def get_count(self) -> int:
        return len(self.joysticks)

    def Joystick(self, index: int) -> FakeJoystick:
        self.factory_calls += 1
        return self.joysticks[index]


class FakeEventModule:
    def pump(self) -> None:
        return None


class FakePygame:
    def __init__(self) -> None:
        self._initialized = False
        self.joystick = FakeJoystickModule()
        self.event = FakeEventModule()

    def get_init(self) -> bool:
        return self._initialized

    def init(self) -> None:
        self._initialized = True


def test_read_snapshots_reuses_initialized_joystick_handles(monkeypatch: Any) -> None:
    fake_pygame = FakePygame()
    monkeypatch.setattr("app.utils.devices.pygame", fake_pygame)

    backend = PygameJoystickBackend()

    devices = backend.list_devices()
    first = backend.read_snapshots()
    second = backend.read_snapshots()

    assert len(devices) == 2
    assert sorted(first) == [0, 1]
    assert sorted(second) == [0, 1]
    assert fake_pygame.joystick.factory_calls == 2
    assert fake_pygame.joystick.joysticks[0].init_calls == 1
    assert fake_pygame.joystick.joysticks[1].init_calls == 1