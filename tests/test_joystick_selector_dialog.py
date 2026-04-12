from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any, Iterator

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal

import app.config as app_config
from app.components.settings_dialog import SettingsDialog
from app.config import Config
from app.services import DetectedJoystickDevice, JoystickActivityEvent


@pytest.fixture(autouse=True)
def override_config_path(tmp_path: Path) -> Iterator[None]:
    original_path = app_config.get_config_path()
    app_config.set_config_path(tmp_path / "config.json")
    yield
    app_config.set_config_path(original_path)


def detected_device(
    product_guid: str,
    product_name: str,
    pygame_index: int,
    layout_key: str | None,
) -> DetectedJoystickDevice:
    return DetectedJoystickDevice(
        display_name=product_name,
        product_name=product_name,
        product_guid=product_guid,
        pygame_index=pygame_index,
        saved_instance=pygame_index + 1,
        num_axes=8,
        num_buttons=32,
        layout_key=layout_key,
    )


class FakeJoystickMonitor(QObject):
    activity = pyqtSignal(object)
    warning = pyqtSignal(str)

    def __init__(self, devices: list[DetectedJoystickDevice]) -> None:
        super().__init__()
        self._devices = devices

    def refresh_devices(self) -> list[DetectedJoystickDevice]:
        return list(self._devices)

    def set_devices(self, devices: list[DetectedJoystickDevice]) -> None:
        self._devices = list(devices)

    def emit_activity(self, event: JoystickActivityEvent) -> None:
        self.activity.emit(event)


def require_attr(instance: object, name: str) -> Any:
    value = getattr(instance, name, None)
    assert value is not None, f"{type(instance).__name__} missing attribute {name}"
    return value


def selector_dialog_class() -> type[Any]:
    spec = importlib.util.find_spec("app.components.joystick_selector_dialog")
    assert spec is not None, "app.components.joystick_selector_dialog must exist"
    module = importlib.import_module("app.components.joystick_selector_dialog")
    dialog_class = getattr(module, "JoystickSelectorDialog", None)
    assert dialog_class is not None, "JoystickSelectorDialog must exist"
    return dialog_class


def activity_event(
    product_guid: str = "guid-left",
    pygame_index: int = 0,
    slot_name: str = "button3",
    active: bool = True,
    timestamp: float = 1000.0,
) -> JoystickActivityEvent:
    return JoystickActivityEvent(
        product_guid=product_guid,
        pygame_index=pygame_index,
        saved_instance=1,
        slot_name=slot_name,
        input_kind="button",
        active=active,
        value=1.0 if active else 0.0,
        timestamp=timestamp,
    )


def test_settings_dialog_opens_selector_window(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(devices=[])
    dialog = SettingsDialog(config, joystick_monitor=monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    selector_button = require_attr(dialog, "joystick_selector_button")
    qtbot.mouseClick(selector_button, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(
        lambda: getattr(dialog, "selector_dialog", None) is not None
        and dialog.selector_dialog.isVisible()
    )
    assert dialog.selector_dialog is not None
    assert dialog.selector_dialog.isVisible()


def test_settings_dialog_reloads_fields_after_selector_save(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
        ]
    )
    dialog = SettingsDialog(config, joystick_monitor=monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.mouseClick(require_attr(dialog, "joystick_selector_button"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(
        lambda: getattr(dialog, "selector_dialog", None) is not None
        and dialog.selector_dialog.isVisible()
    )

    selector_dialog = dialog.selector_dialog
    assert selector_dialog is not None
    require_attr(selector_dialog, "left_selector").setCurrentIndex(1)
    require_attr(selector_dialog, "right_selector").setCurrentIndex(2)
    qtbot.mouseClick(require_attr(selector_dialog, "save_button"), Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not selector_dialog.isVisible())

    assert dialog.joystick_left_name_filter_line_edit.text() == "VKBsim Gladiator EVO L"
    assert dialog.joystick_right_name_filter_line_edit.text() == "VKBsim Gladiator EVO R"
    assert dialog.joystick_type_left_line_edit.text() == "VKBsim Gladiator EVO L"
    assert dialog.joystick_type_right_line_edit.text() == "VKBsim Gladiator EVO R"
    assert dialog.joystick_instance_left_spin_box.value() == 1
    assert dialog.joystick_instance_right_spin_box.value() == 2


def test_selector_blocks_duplicate_left_and_right_assignment(qtbot: Any) -> None:
    joystick_selector_dialog = selector_dialog_class()
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
        ]
    )
    dialog = joystick_selector_dialog(config, monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    require_attr(dialog, "left_selector").setCurrentIndex(1)
    require_attr(dialog, "right_selector").setCurrentIndex(1)
    qtbot.mouseClick(require_attr(dialog, "save_button"), Qt.MouseButton.LeftButton)

    assert "different devices" in require_attr(dialog, "validation_label").text().lower()


def test_selector_renders_detected_devices_and_support_badges(qtbot: Any) -> None:
    joystick_selector_dialog = selector_dialog_class()
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-generic", "Generic USB Joystick", 1, None),
        ]
    )
    dialog = joystick_selector_dialog(config, monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    first_item = require_attr(dialog, "device_list_widget").item(0)
    second_item = require_attr(dialog, "device_list_widget").item(1)

    assert first_item is not None
    assert second_item is not None
    assert first_item.text().endswith("supported")
    assert second_item.text().endswith("preview unavailable")


def test_selector_save_updates_existing_config_keys(qtbot: Any) -> None:
    joystick_selector_dialog = selector_dialog_class()
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
        ]
    )
    dialog = joystick_selector_dialog(config, monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    require_attr(dialog, "left_selector").setCurrentIndex(1)
    require_attr(dialog, "right_selector").setCurrentIndex(2)
    qtbot.mouseClick(require_attr(dialog, "save_button"), Qt.MouseButton.LeftButton)

    assert config.joystick_left_name_filter == "VKBsim Gladiator EVO L"
    assert config.joystick_right_name_filter == "VKBsim Gladiator EVO R"
    assert config.joystick_type_left == "VKBsim Gladiator EVO L"
    assert config.joystick_type_right == "VKBsim Gladiator EVO R"
    assert config.joystick_instance_left == 1
    assert config.joystick_instance_right == 2


def test_selector_marks_unsupported_device_preview_unavailable(qtbot: Any) -> None:
    joystick_selector_dialog = selector_dialog_class()
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[detected_device("guid-generic", "Generic USB Joystick", 0, None)]
    )
    dialog = joystick_selector_dialog(config, monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    require_attr(dialog, "left_selector").setCurrentIndex(1)

    assert "unavailable" in require_attr(dialog, "preview_status_label").text().lower()


def test_selector_preview_tracks_activity_for_selected_supported_device(qtbot: Any) -> None:
    joystick_selector_dialog = selector_dialog_class()
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default")]
    )
    dialog = joystick_selector_dialog(config, monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    require_attr(dialog, "left_selector").setCurrentIndex(1)
    require_attr(dialog, "set_preview_device")(dialog.current_left_device())
    monitor.emit_activity(
        activity_event(
            product_guid="guid-left",
            pygame_index=0,
            slot_name="button3",
            active=True,
        )
    )

    preview_overlay = require_attr(dialog, "preview_overlay")
    assert "button3" in preview_overlay.active_pulses


def test_selector_refresh_rebuilds_state_in_single_sync_pass(qtbot: Any) -> None:
    joystick_selector_dialog = selector_dialog_class()

    class CountingJoystickSelectorDialog(joystick_selector_dialog):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.sync_calls = 0
            super().__init__(*args, **kwargs)

        def _sync_preview_from_selectors(self) -> None:
            self.sync_calls += 1
            super()._sync_preview_from_selectors()

    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
        ]
    )
    dialog = CountingJoystickSelectorDialog(config, monitor)
    qtbot.addWidget(dialog)
    dialog.show()

    require_attr(dialog, "left_selector").setCurrentIndex(1)
    require_attr(dialog, "right_selector").setCurrentIndex(2)

    monitor.set_devices(
        [
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
            detected_device("guid-new", "VKBsim STECS", 2, None),
        ]
    )

    dialog.sync_calls = 0
    dialog.refresh_devices()

    assert dialog.sync_calls == 1
    assert require_attr(dialog, "left_selector").currentData() is None
    assert require_attr(dialog, "right_selector").currentData() == "guid-right"
    assert dialog.selected_preview_device is not None
    assert dialog.selected_preview_device.product_guid == "guid-right"