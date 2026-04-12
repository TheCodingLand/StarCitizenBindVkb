from __future__ import annotations

from dataclasses import dataclass

import pygame
from pydantic import BaseModel


@dataclass(frozen=True)
class RawJoystickDevice:
    pygame_index: int
    product_name: str
    product_guid: str
    num_axes: int
    num_buttons: int


@dataclass(frozen=True)
class DeviceSnapshot:
    buttons: tuple[bool, ...]
    hats: tuple[tuple[int, int], ...]
    axes: tuple[float, ...]


class PygameJoystickBackend:
    def _ensure_initialized(self) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()

    def list_devices(self) -> list[RawJoystickDevice]:
        self._ensure_initialized()

        devices: list[RawJoystickDevice] = []
        joystick_count = pygame.joystick.get_count()
        for pygame_index in range(joystick_count):
            joystick = pygame.joystick.Joystick(pygame_index)
            joystick.init()
            devices.append(
                RawJoystickDevice(
                    pygame_index=pygame_index,
                    product_name=joystick.get_name(),
                    product_guid=joystick.get_guid(),
                    num_axes=joystick.get_numaxes(),
                    num_buttons=joystick.get_numbuttons(),
                )
            )
        return devices

    def read_snapshots(self) -> dict[int, DeviceSnapshot]:
        self._ensure_initialized()
        pygame.event.pump()

        snapshots: dict[int, DeviceSnapshot] = {}
        joystick_count = pygame.joystick.get_count()
        for pygame_index in range(joystick_count):
            joystick = pygame.joystick.Joystick(pygame_index)
            joystick.init()
            snapshots[pygame_index] = DeviceSnapshot(
                buttons=tuple(bool(joystick.get_button(index)) for index in range(joystick.get_numbuttons())),
                hats=tuple(joystick.get_hat(index) for index in range(joystick.get_numhats())),
                axes=tuple(float(joystick.get_axis(index)) for index in range(joystick.get_numaxes())),
            )
        return snapshots


class SystemDevice(BaseModel):
    name: str
    instance: int
    product_guid: str
    product_name: str
    num_axes: int
    num_buttons: int


def get_controller_devices() -> list[SystemDevice]:
    backend = PygameJoystickBackend()
    return [
        SystemDevice(
            name=device.product_name,
            instance=device.pygame_index,
            product_guid=device.product_guid,
            product_name=device.product_name,
            num_axes=device.num_axes,
            num_buttons=device.num_buttons,
        )
        for device in backend.list_devices()
    ]


