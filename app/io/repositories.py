"""Repositories responsible for reading and writing binding data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.domain import BindingSession, ExportResult

from .action_catalog_repository import ActionCatalogRepository
from .layout_repository import DeviceLayoutRepository as HeadlessDeviceLayoutRepository
from .star_citizen_profile_repository import StarCitizenProfileRepository


class ActionMapsRepository:
    """Compatibility wrapper around the headless Star Citizen profile repository."""

    def __init__(
        self,
        root: Path,
        catalog_repo: ActionCatalogRepository | None = None,
        layout_repo: HeadlessDeviceLayoutRepository | None = None,
    ) -> None:
        self.root = root
        self.catalog_repo = catalog_repo
        self.layout_repo = layout_repo

    def load_control_profile(self, path: Path, imported_role_map: dict[str, str]) -> BindingSession:
        return self._delegate().load_profile(path, imported_role_map)

    def save_control_profile(self, session: BindingSession, destination: Path | None = None) -> ExportResult:
        return self._delegate().export_profile(session)

    def list_available_maps(self) -> Iterable[Path]:
        """Yield all control-map files under the configured root."""

        if not self.root.exists():
            return []
        return sorted(self.root.glob("*.xml"))

    def _delegate(self) -> StarCitizenProfileRepository:
        if self.catalog_repo is None or self.layout_repo is None:
            raise RuntimeError(
                "ActionMapsRepository compatibility shim requires injected catalog and layout repositories."
            )
        return StarCitizenProfileRepository(
            catalog_repo=self.catalog_repo,
            layout_repo=self.layout_repo,
        )


class DeviceLayoutRepository:
    """Compatibility wrapper around the headless layout repository."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self._delegate = HeadlessDeviceLayoutRepository()

    def load_layout(self, device_name: str, side: str):
        return self._delegate.load_layout(device_name, side)

    def list_layouts(self) -> Iterable[str]:
        return [self._delegate.SUPPORTED_DEVICE]
