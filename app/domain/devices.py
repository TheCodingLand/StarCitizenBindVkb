from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DeviceRole(str, Enum):
    LEFT_STICK = "left_stick"
    RIGHT_STICK = "right_stick"
    THROTTLE = "throttle"
    AUX = "aux"


@dataclass(frozen=True)
class ImportedDeviceToken:
    device_token: str
    role: str


@dataclass(frozen=True)
class LayoutSlot:
    slot_id: str
    display_name: str
    sc_input_name: str


@dataclass
class DeviceLayoutDescriptor:
    device_name: str
    side: str
    slots: dict[str, LayoutSlot] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)