from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.domain import BindingReference, PassthroughConflict, TriggerMode
from app.models.joystick import JoystickConfig


class UiCommandOutcome(str, Enum):
    MUTATED = "mutated"
    REJECTED = "rejected"
    NOOP = "noop"


@dataclass(frozen=True)
class SessionCatalogEntry:
    action_name: str
    actionmap_name: str | None
    category: str
    subcategory: str
    display_label: str
    supports_joystick: bool
    supported_trigger_modes: tuple[TriggerMode, ...]


@dataclass(frozen=True)
class ProjectedBindingRow:
    binding_ref: BindingReference
    side: str
    button_name: str
    slot_id: str
    action_name: str
    display_label: str
    modifier: bool
    hold: bool
    multitap: bool


@dataclass(frozen=True)
class UiDiagnosticRow:
    kind: str
    action: str
    detail: str
    side: str
    record_id: str | None = None


@dataclass
class UiExportState:
    document: Any | None = None
    blocked_conflicts: list[PassthroughConflict] = field(default_factory=list)
    validation_diagnostics: list[UiDiagnosticRow] = field(default_factory=list)
    export_enabled: bool = False


@dataclass
class ProjectedSessionView:
    left_config: JoystickConfig = field(
        default_factory=lambda: JoystickConfig(side="left", configured_actions={})
    )
    right_config: JoystickConfig = field(
        default_factory=lambda: JoystickConfig(side="right", configured_actions={})
    )
    binding_rows: list[ProjectedBindingRow] = field(default_factory=list)
    diagnostics: list[UiDiagnosticRow] = field(default_factory=list)
