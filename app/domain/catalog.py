from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models import ActionDefinition, ActionIdentifier
from app.models.full_game_control_options import DeviceActivation, GameAction


@dataclass(frozen=True)
class GameCatalogVersion:
    key: str


@dataclass
class GameCatalog:
    version: GameCatalogVersion
    actions_by_name: dict[str, list[ActionDefinition]] = field(default_factory=dict)
    actionmap_by_name: dict[str, str] = field(default_factory=dict)

    @property
    def version_key(self) -> str:
        return self.version.key

    @classmethod
    def from_game_actions(
        cls,
        version_key: str,
        actions: dict[str, list[GameAction]],
    ) -> "GameCatalog":
        catalog = cls(version=GameCatalogVersion(key=version_key))
        for action_name, variants in actions.items():
            catalog.actions_by_name[action_name] = [build_action_definition(item) for item in variants]
            for item in variants:
                actionmap_name = item.main_category or item.sub_category or ""
                if actionmap_name:
                    catalog.actionmap_by_name[action_name] = actionmap_name
                    break
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

    return ActionDefinition(
        identifier=ActionIdentifier(
            name=item.name,
            main_category=item.main_category or "",
            sub_category=item.sub_category or "",
        ),
        activation_modes=tuple(activation_modes),
        supports_joystick=_supports_joystick(item),
    )


def _supports_joystick(item: GameAction) -> bool:
    joystick = item.joystick
    if joystick is None:
        return False
    if isinstance(joystick, str):
        return joystick.strip() != ""
    return (joystick.input or "").strip() != "" or bool(joystick.inputdata)