from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Protocol, TypedDict, cast

from scdatatools.sc import StarCitizen  # type: ignore[import]  # requires scdatatools on PYTHONPATH

from app.models.full_game_control_options import GameActionMap


class ProfileJson(TypedDict):
    actionmap: list[Dict[str, Any]]


class ProfileRoot(TypedDict):
    profile: ProfileJson


class Profile(Protocol):
    json: ProfileRoot


class StarCitizenType(Protocol):
    default_profile: Profile
    version_label: str


def gen_actionmap(profile: Profile) -> dict[str, Dict[str, Any]]:
    """Convert the Star Citizen profile action map into a plain dictionary."""

    action_map: dict[str, Dict[str, Any]] = {}
    actionmaps = profile.json["profile"]["actionmap"]

    for entry in actionmaps:
        gam = GameActionMap(**entry)
        action_map[gam.name] = gam.model_dump()

    return action_map


def main() -> None:
    current_folder = Path(__file__).parent.parent
    sc_folder = Path("f:/Star Citizen/StarCitizen")

    for version in ["PTU", "LIVE"]:
        sc = cast(StarCitizenType, StarCitizen(sc_folder / version))
        profile = sc.default_profile
        v_label: str = sc.version_label
        output_folder = current_folder / "data" / version / v_label
        output_folder.mkdir(parents=True, exist_ok=True)

        action_map = gen_actionmap(profile)
        with (output_folder / "actionmap.json").open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(action_map, indent=4))


if __name__ == "__main__":
    main()
