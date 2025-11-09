"""Core domain data structures for joystick binding management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence, Tuple


@dataclass(frozen=True)
class ActionIdentifier:
    """Uniquely identifies an action within Star Citizen."""

    name: str
    main_category: str
    sub_category: str


@dataclass
class ActionDefinition:
    """Domain representation of a bindable action."""

    identifier: ActionIdentifier
    activation_modes: Tuple[str, ...] = ()
    supports_joystick: bool = True
    default_inputs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class InputSlot:
    """Specific input slot (button or axis) on a device side."""

    device_uid: str
    side: str
    slot_id: str

    def with_modifier(self, modifier_suffix: str) -> "InputSlot":
        return InputSlot(
            device_uid=self.device_uid,
            side=self.side,
            slot_id=f"{self.slot_id}+{modifier_suffix}",
        )


@dataclass
class DeviceLayout:
    """Describes the visual and logical layout of a joystick device."""

    device_uid: str
    side: str
    display_name: str
    slots: dict[str, InputSlot]
    metadata: dict[str, str] = field(default_factory=dict)

    def get_slot(self, slot_id: str) -> Optional[InputSlot]:
        return self.slots.get(slot_id)


@dataclass
class Binding:
    """Mapping between an action and a specific input slot."""

    action: ActionIdentifier
    slot: InputSlot
    modifier: bool = False
    hold: bool = False
    multitap: bool = False
    tags: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        parts = [self.action.name, self.slot.slot_id]
        if self.modifier:
            parts.append("modifier")
        if self.hold:
            parts.append("hold")
        if self.multitap:
            parts.append("multitap")
        return "|".join(parts)


@dataclass
class BindingSet:
    """Collection of bindings for a single physical device side."""

    side: str
    bindings: dict[str, Binding] = field(default_factory=dict)

    def add(self, binding: Binding) -> None:
        self.bindings[binding.key] = binding

    def remove(self, key: str) -> None:
        self.bindings.pop(key, None)

    def find_by_action(self, action_name: str) -> list[Binding]:
        return [b for b in self.bindings.values() if b.action.name == action_name]


@dataclass
class ControlProfile:
    """Aggregates bindings and metadata for an exported profile."""

    profile_name: str
    left: BindingSet
    right: BindingSet
    metadata: dict[str, str] = field(default_factory=dict)

    def iter_bindings(self) -> Iterable[Binding]:
        yield from self.left.bindings.values()
        yield from self.right.bindings.values()


@dataclass
class ValidationIssue:
    """Represents a discrepancy encountered during planning or export."""

    level: str
    message: str
    action: Optional[ActionIdentifier] = None
    slot: Optional[InputSlot] = None


@dataclass
class ValidationReport:
    """Summarises validation issues discovered while planning bindings."""

    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues.extend(issues)

    @property
    def has_errors(self) -> bool:
        return any(issue.level.lower() == "error" for issue in self.issues)


@dataclass
class BindingPlan:
    """Represents a staged set of binding mutations to be applied."""

    to_add: list[Binding] = field(default_factory=list)
    to_remove: list[Binding] = field(default_factory=list)
    validation: ValidationReport = field(default_factory=ValidationReport)

    def record_add(self, binding: Binding) -> None:
        self.to_add.append(binding)

    def record_remove(self, binding: Binding) -> None:
        self.to_remove.append(binding)

    def merge(self, other: "BindingPlan") -> None:
        self.to_add.extend(other.to_add)
        self.to_remove.extend(other.to_remove)
        self.validation.extend(other.validation.issues)
