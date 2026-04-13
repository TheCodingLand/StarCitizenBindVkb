from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    def __init__(self) -> None:
        self._joysticks: dict[int, Any] = {}

    def _ensure_initialized(self) -> None:
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()

    def _active_joysticks(self) -> dict[int, Any]:
        self._ensure_initialized()

        active_joysticks: dict[int, Any] = {}
        joystick_count = pygame.joystick.get_count()
        for pygame_index in range(joystick_count):
            joystick = self._joysticks.get(pygame_index)
            if joystick is None:
                joystick = pygame.joystick.Joystick(pygame_index)

            is_initialized = False
            get_init = getattr(joystick, "get_init", None)
            if callable(get_init):
                is_initialized = bool(get_init())
            if not is_initialized:
                joystick.init()

            active_joysticks[pygame_index] = joystick

        self._joysticks = active_joysticks
        return active_joysticks

    def list_devices(self) -> list[RawJoystickDevice]:
        devices: list[RawJoystickDevice] = []
        for pygame_index, joystick in self._active_joysticks().items():
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
        for pygame_index, joystick in self._active_joysticks().items():
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


