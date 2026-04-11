from __future__ import annotations

from app.domain import DeviceLayoutDescriptor, LayoutSlot
from app.models.joystick import JoyStickButton, get_joystick_buttons


def build_layout(
    device_name: str,
    side: str,
    buttons: dict[str, JoyStickButton],
) -> DeviceLayoutDescriptor:
    return DeviceLayoutDescriptor(
        device_name=device_name,
        side=side,
        slots={
            button.sc_config_name: LayoutSlot(
                slot_id=button.sc_config_name,
                display_name=button.name,
                sc_input_name=button.sc_config_name,
            )
            for button in buttons.values()
        },
    )


class DeviceLayoutRepository:
    SUPPORTED_DEVICE = "VKB Default"

    def load_layout(self, device_name: str, side: str) -> DeviceLayoutDescriptor | None:
        if device_name != self.SUPPORTED_DEVICE:
            return None
        try:
            buttons = get_joystick_buttons(self.SUPPORTED_DEVICE)
        except ValueError:
            return None
        return build_layout(device_name=self.SUPPORTED_DEVICE, side=side, buttons=buttons)