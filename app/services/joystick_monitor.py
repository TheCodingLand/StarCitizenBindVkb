from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Literal

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.models.joystick_layout_support import SUPPORTED_LAYOUTS, SupportedJoystickLayout
from app.utils.devices import DeviceSnapshot, PygameJoystickBackend


@dataclass(frozen=True)
class DetectedJoystickDevice:
    display_name: str
    product_name: str
    product_guid: str
    pygame_index: int
    saved_instance: int
    num_axes: int
    num_buttons: int
    layout_key: str | None = None


@dataclass(frozen=True)
class JoystickActivityEvent:
    product_guid: str
    pygame_index: int
    saved_instance: int
    slot_name: str
    input_kind: Literal["button", "hat", "trigger"]
    active: bool
    value: float
    timestamp: float


def list_detected_devices(
    backend: PygameJoystickBackend,
    supported_layouts: tuple[SupportedJoystickLayout, ...] = SUPPORTED_LAYOUTS,
) -> list[DetectedJoystickDevice]:
    devices: list[DetectedJoystickDevice] = []
    for raw_device in backend.list_devices():
        layout = next(
            (item for item in supported_layouts if item.matches(raw_device.product_name)),
            None,
        )
        devices.append(
            DetectedJoystickDevice(
                display_name=layout.display_name if layout is not None else raw_device.product_name,
                product_name=raw_device.product_name,
                product_guid=raw_device.product_guid,
                pygame_index=raw_device.pygame_index,
                saved_instance=raw_device.pygame_index + 1,
                num_axes=raw_device.num_axes,
                num_buttons=raw_device.num_buttons,
                layout_key=layout.key if layout is not None else None,
            )
        )
    return devices


class JoystickMonitorService(QObject):
    devices_changed = pyqtSignal(object)
    activity = pyqtSignal(object)
    warning = pyqtSignal(str)

    def __init__(self, backend: PygameJoystickBackend | None = None, interval_ms: int = 16) -> None:
        super().__init__()
        self.backend = backend or PygameJoystickBackend()
        self.interval_ms = interval_ms
        self._supported_layouts = SUPPORTED_LAYOUTS
        self._layout_by_key = {layout.key: layout for layout in self._supported_layouts}
        self._devices: list[DetectedJoystickDevice] = []
        self._device_by_index: dict[int, DetectedJoystickDevice] = {}
        self._layout_by_index: dict[int, SupportedJoystickLayout] = {}
        self._previous_snapshots: dict[int, DeviceSnapshot] = {}
        self._active_triggers: dict[tuple[int, int], bool] = {}

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll_timer_tick)

    def refresh_devices(self) -> list[DetectedJoystickDevice]:
        try:
            devices = list_detected_devices(self.backend)
        except Exception as exc:
            self.warning.emit(str(exc))
            return []

        self._devices = devices
        self._device_by_index = {device.pygame_index: device for device in devices}
        self._layout_by_index = {
            device.pygame_index: self._layout_by_key[device.layout_key]
            for device in devices
            if device.layout_key is not None and device.layout_key in self._layout_by_key
        }
        active_indices = {device.pygame_index for device in devices}
        self._previous_snapshots = {
            index: snapshot
            for index, snapshot in self._previous_snapshots.items()
            if index in active_indices
        }
        self._active_triggers = {
            key: is_active
            for key, is_active in self._active_triggers.items()
            if key[0] in active_indices and is_active
        }
        self.devices_changed.emit(list(devices))
        return list(devices)

    def poll_once(self, device_states: dict[int, DeviceSnapshot] | None = None) -> list[JoystickActivityEvent]:
        try:
            current = device_states if device_states is not None else self.backend.read_snapshots()
        except Exception as exc:
            self.warning.emit(str(exc))
            return []

        events: list[JoystickActivityEvent] = []
        timestamp = time.monotonic() * 1000
        for pygame_index, snapshot in current.items():
            device = self._device_by_index.get(pygame_index)
            layout = self._layout_by_index.get(pygame_index)
            if device is None or layout is None:
                continue

            previous = self._previous_snapshots.get(pygame_index)
            events.extend(self._diff_buttons(device, layout, previous, snapshot, timestamp))
            events.extend(self._diff_hats(device, layout, previous, snapshot, timestamp))
            events.extend(self._diff_triggers(device, layout, previous, snapshot, timestamp))

        merged_snapshots = dict(self._previous_snapshots)
        merged_snapshots.update(current)
        active_indices = set(self._device_by_index)
        self._previous_snapshots = {
            index: snapshot for index, snapshot in merged_snapshots.items() if index in active_indices
        }

        for event in events:
            self.activity.emit(event)
        return events

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()

    def _poll_timer_tick(self) -> None:
        self.poll_once()

    def _diff_buttons(
        self,
        device: DetectedJoystickDevice,
        layout: SupportedJoystickLayout,
        previous: DeviceSnapshot | None,
        current: DeviceSnapshot,
        timestamp: float,
    ) -> list[JoystickActivityEvent]:
        events: list[JoystickActivityEvent] = []
        for button_index, slot_name in layout.button_slots.items():
            previous_pressed = self._button_value(previous, button_index)
            current_pressed = self._button_value(current, button_index)
            if current_pressed == previous_pressed:
                continue
            events.append(
                self._build_event(
                    device=device,
                    slot_name=slot_name,
                    input_kind="button",
                    active=current_pressed,
                    value=1.0 if current_pressed else 0.0,
                    timestamp=timestamp,
                )
            )
        return events

    def _diff_hats(
        self,
        device: DetectedJoystickDevice,
        layout: SupportedJoystickLayout,
        previous: DeviceSnapshot | None,
        current: DeviceSnapshot,
        timestamp: float,
    ) -> list[JoystickActivityEvent]:
        previous_hat = self._hat_value(previous)
        current_hat = self._hat_value(current)
        if previous_hat == current_hat:
            return []

        events: list[JoystickActivityEvent] = []
        previous_slot = layout.hat_slots.get(previous_hat)
        current_slot = layout.hat_slots.get(current_hat)
        if previous_slot is not None:
            events.append(
                self._build_event(
                    device=device,
                    slot_name=previous_slot,
                    input_kind="hat",
                    active=False,
                    value=0.0,
                    timestamp=timestamp,
                )
            )
        if current_slot is not None:
            events.append(
                self._build_event(
                    device=device,
                    slot_name=current_slot,
                    input_kind="hat",
                    active=True,
                    value=1.0,
                    timestamp=timestamp,
                )
            )
        return events

    def _diff_triggers(
        self,
        device: DetectedJoystickDevice,
        layout: SupportedJoystickLayout,
        previous: DeviceSnapshot | None,
        current: DeviceSnapshot,
        timestamp: float,
    ) -> list[JoystickActivityEvent]:
        del previous

        events: list[JoystickActivityEvent] = []
        for mapping in layout.trigger_axes:
            trigger_key = (device.pygame_index, mapping.axis_index)
            current_value = self._axis_value(current, mapping.axis_index)
            was_active = self._active_triggers.get(trigger_key, False)

            if not was_active and current_value >= mapping.activate_at:
                self._active_triggers[trigger_key] = True
                events.append(
                    self._build_event(
                        device=device,
                        slot_name=mapping.slot_name,
                        input_kind="trigger",
                        active=True,
                        value=current_value,
                        timestamp=timestamp,
                    )
                )
                continue

            if was_active and current_value < mapping.clear_below:
                self._active_triggers.pop(trigger_key, None)
                events.append(
                    self._build_event(
                        device=device,
                        slot_name=mapping.slot_name,
                        input_kind="trigger",
                        active=False,
                        value=current_value,
                        timestamp=timestamp,
                    )
                )
        return events

    def _build_event(
        self,
        *,
        device: DetectedJoystickDevice,
        slot_name: str,
        input_kind: Literal["button", "hat", "trigger"],
        active: bool,
        value: float,
        timestamp: float,
    ) -> JoystickActivityEvent:
        return JoystickActivityEvent(
            product_guid=device.product_guid,
            pygame_index=device.pygame_index,
            saved_instance=device.saved_instance,
            slot_name=slot_name,
            input_kind=input_kind,
            active=active,
            value=value,
            timestamp=timestamp,
        )

    @staticmethod
    def _button_value(snapshot: DeviceSnapshot | None, index: int) -> bool:
        if snapshot is None or index >= len(snapshot.buttons):
            return False
        return snapshot.buttons[index]

    @staticmethod
    def _hat_value(snapshot: DeviceSnapshot | None) -> tuple[int, int]:
        if snapshot is None or not snapshot.hats:
            return (0, 0)
        return snapshot.hats[0]

    @staticmethod
    def _axis_value(snapshot: DeviceSnapshot | None, index: int) -> float:
        if snapshot is None or index >= len(snapshot.axes):
            return 0.0
        return snapshot.axes[index]