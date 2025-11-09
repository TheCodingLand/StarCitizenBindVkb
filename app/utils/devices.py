from typing import List
from pydantic import BaseModel
import pygame

# Initialize Pygame


class SystemDevice(BaseModel):
    name: str
    instance: int
    product_guid: str
    product_name: str
    num_axes: int
    num_buttons: int


def get_controller_devices() -> List[SystemDevice]:
    pygame.init()
    pygame.joystick.init()
    devices: List[SystemDevice] = []
    joystick_count = pygame.joystick.get_count()
    for i in range(joystick_count):
        joystick = pygame.joystick.Joystick(i)
        joystick.init()
        name = joystick.get_name()
        num_axes = joystick.get_numaxes()
        num_buttons = joystick.get_numbuttons()
        guid = joystick.get_guid()
        devices.append(SystemDevice(name=name, instance=i, product_guid=guid, product_name=name, num_axes=num_axes, num_buttons=num_buttons))
    return devices


