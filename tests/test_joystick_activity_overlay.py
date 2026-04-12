from __future__ import annotations

import importlib
import importlib.util
from typing import Any

from PyQt6.QtCore import QPoint

from app.services import JoystickActivityEvent


def overlay_class() -> type[Any]:
    spec = importlib.util.find_spec("app.components.joystick_activity_overlay")
    assert spec is not None, "app.components.joystick_activity_overlay must exist"
    module = importlib.import_module("app.components.joystick_activity_overlay")
    overlay_type = getattr(module, "JoystickActivityOverlay", None)
    assert overlay_type is not None, "JoystickActivityOverlay must exist"
    return overlay_type


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


def test_overlay_restarts_existing_pulse_for_same_slot(qtbot: Any) -> None:
    joystick_activity_overlay = overlay_class()
    overlay = joystick_activity_overlay(slot_positions={"button3": QPoint(100, 120)})
    qtbot.addWidget(overlay)

    overlay.record_activity(activity_event(slot_name="button3", active=True, timestamp=1000.0))
    first_started = overlay.active_pulses["button3"].started_at
    overlay.record_activity(activity_event(slot_name="button3", active=True, timestamp=1200.0))

    assert overlay.active_pulses["button3"].started_at > first_started


def test_overlay_expires_stale_pulse_after_timeout(qtbot: Any) -> None:
    joystick_activity_overlay = overlay_class()
    overlay = joystick_activity_overlay(slot_positions={"button3": QPoint(100, 120)})
    qtbot.addWidget(overlay)

    overlay.record_activity(activity_event(slot_name="button3", active=True, timestamp=1000.0))
    overlay._expire_stale_pulses(now_ms=1500.0)

    assert overlay.active_pulses == {}