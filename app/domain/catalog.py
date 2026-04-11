from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import ActionDefinition, ActionIdentifier
from app.domain.session import TriggerMode
from app.models.full_game_control_options import DeviceActivation, GameAction


@dataclass(frozen=True)
class GameCatalogVersion:
    key: str


@dataclass
class GameCatalog:
    version: GameCatalogVersion
    actions_by_name: dict[str, list[ActionDefinition]] = field(default_factory=dict)
    entries_by_key: dict[tuple[str, str], ActionDefinition] = field(default_factory=dict)
    actionmaps_by_name: dict[str, tuple[str, ...]] = field(default_factory=dict)
    actionmap_by_name: dict[str, str] = field(default_factory=dict)

    @property
    def version_key(self) -> str:
        return self.version.key

    def entry_for(self, action_name: str, actionmap_name: str | None) -> ActionDefinition | None:
        if actionmap_name is not None:
            return self.entries_by_key.get((action_name, actionmap_name))

        entries = self.actions_by_name.get(action_name, [])
        if not entries:
            return None

        entries_by_actionmap = {entry.actionmap_name: entry for entry in entries}
        if len(entries_by_actionmap) == 1:
            return next(iter(entries_by_actionmap.values()))
        return None

    @classmethod
    def from_game_actions(
        cls,
        version_key: str,
        actions: dict[str, list[GameAction]],
    ) -> "GameCatalog":
        catalog = cls(version=GameCatalogVersion(key=version_key))
        for action_name, variants in actions.items():
            entries = [build_action_definition(item) for item in variants]
            catalog.actions_by_name[action_name] = entries
            for entry in entries:
                catalog.entries_by_key[(entry.action_name, entry.actionmap_name)] = entry
            actionmaps = tuple(
                dict.fromkeys(
                    entry.actionmap_name
                    for entry in entries
                actionmap_metadata: Mapping[str, tuple[str | None, str | None]] | None = None,
                    if entry.actionmap_name
                )
            )
            catalog.actionmaps_by_name[action_name] = actionmaps
                    catalog.actions_by_name[action_name] = entries
                    for entry in entries:
                        catalog.entries_by_key[(entry.action_name, entry.actionmap_name)] = entry
                    actionmaps = tuple(
                        dict.fromkeys(
                            entry.actionmap_name
                            for entry in entries
                            if entry.actionmap_name
                        )
                    )
                    catalog.actionmaps_by_name[action_name] = actionmaps
                    if actionmaps:
                        catalog.actionmap_by_name[action_name] = actionmaps[0]
                catalog.actionmap_by_name[action_name] = actionmaps[0]
        return catalog


def build_action_definition(item: GameAction) -> ActionDefinition:
    activation_modes: list[str] = []
    for value in (
        item.activation_mode,
        item.on_press,
        item.on_hold,
        item.on_release,
        item.joystick.activationmode if isinstance(item.joystick, DeviceActivation) else None,
    ):
        normalized = (value or "").strip()
        if normalized and normalized not in activation_modes:
            activation_modes.append(normalized)

    supports_joystick = _supports_joystick(item)

    return ActionDefinition(
        identifier=ActionIdentifier(
            name=item.name,
            main_category=item.main_category or "",
                actionmap_name=item.sub_category or item.main_category or "",
                category=actionmap_category or item.ui_category or item.category or item.main_category or actionmap_name,
                subcategory=actionmap_label or actionmap_name,
        ),
        action_name=item.name,
        actionmap_name=item.sub_category or item.main_category or "",
        category=item.category or item.main_category or "",
        subcategory=item.sub_category or item.main_category or "",
        display_label=item.ui_label or item.name,
        supported_trigger_modes=_supported_trigger_modes(supports_joystick),
        activation_modes=tuple(activation_modes),
        supports_joystick=supports_joystick,
        default_inputs=_default_inputs(item),
    )


def _supports_joystick(item: GameAction) -> bool:
    joystick = item.joystick
    return joystick is not None


def _supported_trigger_modes(supports_joystick: bool) -> tuple[TriggerMode, ...]:
    if not supports_joystick:
        return ()
    return (
        TriggerMode.PLAIN,
        TriggerMode.MODIFIER,
        TriggerMode.HOLD,
        TriggerMode.MULTITAP,
    )


def _default_inputs(item: GameAction) -> tuple[str, ...]:
    joystick = item.joystick
    if isinstance(joystick, str):
        normalized = joystick.strip()
        return (normalized,) if normalized else ()
    if isinstance(joystick, DeviceActivation):
        inputs = []
        if joystick.input:
            normalized = joystick.input.strip()
            if normalized:
                inputs.append(normalized)
        for input_item in joystick.inputdata or []:
            normalized = input_item.input.strip()
            if normalized and normalized not in inputs:
                inputs.append(normalized)
        return tuple(inputs)
    return ()