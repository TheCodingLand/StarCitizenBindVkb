from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.domain.catalog import GameCatalog, GameCatalogVersion


class TriggerMode(str, Enum):
    PLAIN = "plain"
    MODIFIER = "modifier"
    HOLD = "hold"
    MULTITAP = "multitap"


@dataclass
class Diagnostic:
    code: str
    level: str
    message: str
    record_id: str | None = None


@dataclass
class BindingEdit:
    role: str
    slot_id: str
    action_name: str
    trigger_mode: TriggerMode
    modifier_token: str | None = None
    source_record_id: str | None = None
    source_actionmap_name: str | None = None
    replaced_passthrough_record_id: str | None = None


@dataclass(frozen=True)
class BindingReference:
    role: str
    slot_id: str
    action_name: str
    trigger_mode: TriggerMode
    modifier_token: str | None = None
    source_record_id: str | None = None
    source_actionmap_name: str | None = None
    replaced_passthrough_record_id: str | None = None


@dataclass
class BindingInput:
    role: str
    slot_id: str
    action_name: str
    trigger_mode: TriggerMode
    modifier_token: str | None = None


@dataclass
class PassthroughRecord:
    record_id: str
    action_name: str
    device_token: str
    slot_token: str
    trigger_token: str
    raw_payload: dict[str, Any]


@dataclass
class UnresolvedBinding:
    record_id: str
    action_name: str
    device_token: str
    slot_token: str
    reason: str


@dataclass
class WorkingProfile:
    profile_name: str
    bindings: list[BindingEdit] = field(default_factory=list)
    passthrough_records: list[PassthroughRecord] = field(default_factory=list)
    unresolved_bindings: list[UnresolvedBinding] = field(default_factory=list)
    role_device_tokens: dict[str, str] = field(default_factory=dict)
    editable_source_record_ids: set[str] = field(default_factory=set)
    source_path: Path | None = None
    source_document: Any | None = None


@dataclass
class PassthroughConflict:
    conflict_id: str
    record_id: str
    device_token: str
    slot_token: str
    trigger_token: str
    action_name: str


@dataclass
class ExportResult:
    changed_bindings: list[BindingEdit] = field(default_factory=list)
    preserved_passthrough_count: int = 0
    blocked_conflicts: list[PassthroughConflict] = field(default_factory=list)
    document: Any | None = None


@dataclass(frozen=True)
class SessionCatalogSnapshot:
    version: GameCatalogVersion
    catalog: GameCatalog


@dataclass
class BindingSession:
    profile: WorkingProfile
    diagnostics: list[Diagnostic] = field(default_factory=list)
    catalog_snapshot: SessionCatalogSnapshot | None = None