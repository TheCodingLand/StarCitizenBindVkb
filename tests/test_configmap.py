from pathlib import Path
from typing import List, TypeVar

from pydantic import BaseModel, Field

from models.actions import get_all_defined_game_actions
from app.models.configmap import ActionMapsFile, get_action_maps_file, Action


SC = "LIVE"
SC_VERSION = "sc-alpha-3.24.2-9381373"
sc_actionmaps_path = Path(__file__).parent.parent / 'data' / SC_VERSION / f"actionmap.json"
data_folder= Path(__file__).parent.parent  / "data"
def test_actionmap():
        
    possible_actions = get_all_defined_game_actions()
    action_maps_file_souce = data_folder / "actionmaps.xml"

    x = get_action_maps_file(action_maps_file_souce)
    name_action_mapping = { action.name: action for action in possible_actions.values()}
    x = ActionMapsFile(**x)

    TItem = TypeVar("TItem")

    def always_list(item: TItem | List[TItem]) -> List[TItem]:
        if isinstance(item, list):
            return item #type: ignore
        return [item]

    for actions in x.action_profiles[0].actionmap:
        for action in actions.action:
            for item in always_list(action):
                if isinstance(action, Action):
                    if action.rebinding is not None:
                        pass
                            
                            # defined keys
