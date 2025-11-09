"""Repositories responsible for reading and writing binding data."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from app.domain import ControlProfile, DeviceLayout


class ActionMapsRepository:
    """Loads and persists control maps from Star Citizen export files."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load_control_profile(self, path: Path) -> ControlProfile:
        """Parse an exported XML file into a ControlProfile.

        Placeholder implementation; this will be replaced with real parsing
        logic that leverages ``app.models.exported_configmap_xml``.
        """

        raise NotImplementedError("Control profile loading is not implemented yet.")

    def save_control_profile(self, profile: ControlProfile, destination: Path) -> None:
        """Write a ControlProfile to disk in Star Citizen's XML format."""

        raise NotImplementedError("Control profile persistence is not implemented yet.")

    def list_available_maps(self) -> Iterable[Path]:
        """Yield all control-map files under the configured root."""

        if not self.root.exists():
            return []
        return sorted(self.root.glob("*.xml"))


class DeviceLayoutRepository:
    """Provides access to device button layouts and metadata."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def load_layout(self, device_name: str, side: str) -> Optional[DeviceLayout]:
        """Load a DeviceLayout by key; returns None when not found."""

        raise NotImplementedError("Device layout loading is not implemented yet.")

    def list_layouts(self) -> Iterable[str]:
        """Return the identifiers for all known layouts."""

        raise NotImplementedError("Listing layouts is not implemented yet.")
