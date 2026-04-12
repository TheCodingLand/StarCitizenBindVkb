from __future__ import annotations

from dataclasses import dataclass, field

from app.models.joystick_layout_support import SUPPORTED_LAYOUTS, SupportedJoystickLayout
from app.services import (
    DetectedJoystickDevice,
    JoystickMonitorService,
    list_detected_devices,
)
from app.utils.devices import DeviceSnapshot, RawJoystickDevice


@dataclass
class FakeJoystickBackend:
    devices: list[RawJoystickDevice]
    snapshots: list[dict[int, DeviceSnapshot]] = field(default_factory=list)
    failure: Exception | None = None

    def list_devices(self) -> list[RawJoystickDevice]:
        if self.failure is not None:
            raise self.failure
        return list(self.devices)

    def read_snapshots(self) -> dict[int, DeviceSnapshot]:
        if self.failure is not None:
            raise self.failure
        if not self.snapshots:
            return {}
        return self.snapshots.pop(0)


def build_monitor_with_layout(backend: FakeJoystickBackend) -> JoystickMonitorService:
    return JoystickMonitorService(backend=backend, interval_ms=16)


def test_detected_device_uses_one_based_saved_instance_and_layout_match() -> None:
    backend = FakeJoystickBackend(
        devices=[
            RawJoystickDevice(
                pygame_index=0,
                product_name="VKBsim Gladiator EVO L",
                product_guid="guid-left",
                num_axes=8,
                num_buttons=32,
            )
        ]
    )

    devices = list_detected_devices(backend, SUPPORTED_LAYOUTS)

    assert devices == [
        DetectedJoystickDevice(
            display_name="VKB Default",
            product_name="VKBsim Gladiator EVO L",
            product_guid="guid-left",
            pygame_index=0,
            saved_instance=1,
            num_axes=8,
            num_buttons=32,
            layout_key="vkb_default",
        )
    ]


def test_supported_layout_matches_product_name_fragments_case_insensitively() -> None:
    layout = SupportedJoystickLayout(
        key="test_layout",
        display_name="Test Layout",
        chart_name="VKB Default",
        product_name_fragments=("vkbsim", "gladiator", "evo"),
        button_slots={},
        hat_slots={},
        trigger_axes=(),
    )

    assert layout.matches("VKBsim Gladiator EVO Omni Throttle") is True
    assert layout.matches("Generic USB Joystick") is False


def test_button_press_emits_slot_once_per_transition() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {
                0: DeviceSnapshot(
                    buttons=(False, False, True),
                    hats=((0, 0),),
                    axes=(0.0, 0.0),
                )
            },
            {
                0: DeviceSnapshot(
                    buttons=(False, False, True),
                    hats=((0, 0),),
                    axes=(0.0, 0.0),
                )
            },
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert [event.slot_name for event in first] == ["button3"]
    assert second == []


def test_hat_direction_emits_active_and_clear_events() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 1),), axes=(0.0,) * 8)},
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 0),), axes=(0.0,) * 8)},
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert [(event.slot_name, event.active) for event in first] == [("hat1_up", True)]
    assert [(event.slot_name, event.active) for event in second] == [("hat1_up", False)]


def test_trigger_threshold_emits_active_and_clear_events() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {
                0: DeviceSnapshot(
                    buttons=(False,) * 32,
                    hats=((0, 0),),
                    axes=(0.0, 0.0, 0.82, 0.0, 0.0, 0.0, 0.0, 0.0),
                )
            },
            {
                0: DeviceSnapshot(
                    buttons=(False,) * 32,
                    hats=((0, 0),),
                    axes=(0.0, 0.0, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0),
                )
            },
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert [(event.slot_name, event.active) for event in first] == [("trigger_left", True)]
    assert [(event.slot_name, event.active) for event in second] == [("trigger_left", False)]


def test_unmapped_axis_motion_is_ignored() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {
                0: DeviceSnapshot(
                    buttons=(False,) * 32,
                    hats=((0, 0),),
                    axes=(0.0, 0.0, 0.0, 0.0, 0.91, 0.0, 0.0, 0.0),
                )
            },
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    assert monitor.poll_once() == []


def test_refresh_devices_returns_empty_list_when_backend_has_none() -> None:
    backend = FakeJoystickBackend(devices=[])

    monitor = build_monitor_with_layout(backend)

    assert monitor.refresh_devices() == []


def test_poll_once_emits_warning_and_preserves_state_on_backend_failure() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {0: DeviceSnapshot(buttons=(False, False, True), hats=((0, 0),), axes=(0.0,) * 8)},
        ],
    )
    monitor = build_monitor_with_layout(backend)
    warnings: list[str] = []
    monitor.warning.connect(warnings.append)

    devices = monitor.refresh_devices()
    assert [device.product_guid for device in devices] == ["guid-left"]

    first = monitor.poll_once()
    backend.failure = RuntimeError("pygame failure")
    second = monitor.poll_once()

    assert [event.slot_name for event in first] == ["button3"]
    assert second == []
    assert warnings == ["pygame failure"]

    backend.failure = None
    backend.snapshots = [
        {0: DeviceSnapshot(buttons=(False, False, True), hats=((0, 0),), axes=(0.0,) * 8)},
        {0: DeviceSnapshot(buttons=(False, False, False), hats=((0, 0),), axes=(0.0,) * 8)},
    ]

    assert monitor.poll_once() == []
    assert [(event.slot_name, event.active) for event in monitor.poll_once()] == [
        ("button3", False)
    ]