from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PyQt6.QtCore import QPoint

from app.models.joystick import get_joystick_buttons


@dataclass(frozen=True)
class TriggerAxisMapping:
    axis_index: int
    slot_name: str
    activate_at: float
    clear_below: float


@dataclass(frozen=True)
class AxisSlotMapping:
    axis_index: int
    slot_name: str
    activate_at: float
    clear_below: float


@dataclass(frozen=True)
class SupportedJoystickLayout:
    key: str
    display_name: str
    chart_name: str
    product_name_fragments: tuple[str, ...]
    button_slots: dict[int, str]
    hat_slots: dict[tuple[int, int], str]
    trigger_axes: tuple[TriggerAxisMapping, ...]
    axis_slots: tuple[AxisSlotMapping, ...] = ()

    def matches(self, product_name: str) -> bool:
        normalized = product_name.casefold()
        return all(fragment.casefold() in normalized for fragment in self.product_name_fragments)


VKB_DEFAULT_BUTTON_SLOTS = {index: f"button{index + 1}" for index in range(29)}

VKB_DEFAULT_HAT_SLOTS = {
    (0, 1): "hat1_up",
    (1, 1): "hat1_up_right",
    (-1, 1): "hat1_up_left",
    (-1, 0): "hat1_left",
    (1, 0): "hat1_right",
    (-1, -1): "hat1_down_left",
    (0, -1): "hat1_down",
    (1, -1): "hat1_down_right",
}

VKB_DEFAULT_TRIGGER_AXES = (
)

VKB_DEFAULT_AXIS_SLOTS = (
    AxisSlotMapping(axis_index=0, slot_name="x", activate_at=0.55, clear_below=0.20),
    AxisSlotMapping(axis_index=1, slot_name="y", activate_at=0.55, clear_below=0.20),
    AxisSlotMapping(axis_index=2, slot_name="z", activate_at=0.55, clear_below=0.20),
    AxisSlotMapping(axis_index=3, slot_name="rotx", activate_at=0.55, clear_below=0.20),
    AxisSlotMapping(axis_index=4, slot_name="roty", activate_at=0.55, clear_below=0.20),
    AxisSlotMapping(axis_index=5, slot_name="rotz", activate_at=0.55, clear_below=0.20),
)

SUPPORTED_LAYOUTS = (
    SupportedJoystickLayout(
        key="vkb_default",
        display_name="VKB Default",
        chart_name="VKB Default",
        product_name_fragments=("vkbsim", "gladiator", "evo"),
        button_slots=VKB_DEFAULT_BUTTON_SLOTS,
        hat_slots=VKB_DEFAULT_HAT_SLOTS,
        trigger_axes=VKB_DEFAULT_TRIGGER_AXES,
        axis_slots=VKB_DEFAULT_AXIS_SLOTS,
    ),
)


def slot_positions_for_layout(layout_key: str, side: Literal["left", "right"]) -> dict[str, QPoint]:
    layout = next((item for item in SUPPORTED_LAYOUTS if item.key == layout_key), None)
    if layout is None:
        raise ValueError(f"Unsupported layout key: {layout_key}")

    buttons = get_joystick_buttons(layout.chart_name)
    supported_slot_names = (
        set(layout.button_slots.values())
        | set(layout.hat_slots.values())
        | {mapping.slot_name for mapping in layout.axis_slots}
    )
    positions = {
        slot_name: QPoint(button.coord_x_left[side], button.coord_y_top)
        for slot_name, button in buttons.items()
        if slot_name in supported_slot_names
    }
    positions.update(
        {
            mapping.slot_name: (
                QPoint(1540 if side == "left" else 280, 335)
                if mapping.slot_name == "trigger_left"
                else QPoint(1540 if side == "left" else 280, 190)
            )
            for mapping in layout.trigger_axes
        }
    )
    return positions


__all__ = [
    "AxisSlotMapping",
    "SUPPORTED_LAYOUTS",
    "SupportedJoystickLayout",
    "TriggerAxisMapping",
    "slot_positions_for_layout",
]