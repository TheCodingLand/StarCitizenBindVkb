from __future__ import annotations

from pathlib import Path

from app.domain import GameCatalog
from app.models.full_game_control_options import get_all_defined_game_actions


class ActionCatalogRepository:
    def __init__(self, source_path: Path, version_key: str | None = None) -> None:
        self.source_path = source_path
        self.version_key = version_key
from app.models.full_game_control_options import (
    get_all_defined_game_actions,
    get_all_subcategories_actions,
)

    def load(self) -> GameCatalog:
        if not self.source_path.exists():
            raise FileNotFoundError(self.source_path)

        actionmap_metadata = {
            actionmap.name: (
                actionmap.ui_category or main_category,
                actionmap.ui_label or actionmap.name,
            )
            for main_category, actionmap in get_all_subcategories_actions(self.source_path).root.items()
        }

        return GameCatalog.from_game_actions(
            version_key=self._resolve_version_key(),
            actions=get_all_defined_game_actions(self.source_path),
            actionmap_metadata=actionmap_metadata,
        )

    def _resolve_version_key(self) -> str:
        if self.version_key:
            return self.version_key
        if self.source_path.stem == "actionmap":
            return self.source_path.parent.name
        return self.source_path.stem