from pathlib import Path
from typing import List, TypeVar

from pydantic import BaseModel, Field

from actions import get_all_defined_game_actions
from configmap import ActionMapsFile, get_action_maps_file, Action

SC = "LIVE"
SC_VERSION = "sc-alpha-3.24.2-9381373"
sc_actionmaps_path = Path(__file__).parent / 'data' / SC_VERSION / f"actionmap.json"

possible_actions = get_all_defined_game_actions()


x = get_action_maps_file()
name_action_mapping = { action.name: action for action in possible_actions}
x = ActionMapsFile(**x)

TItem = TypeVar("TItem")

def always_list(item: TItem | List[TItem]) -> List[TItem]:
    if isinstance(item, list):
        return item #type: ignore
    return [item]

for actions in x.action_profiles.actionmap:
    for action in actions.action:
        for item in always_list(action):

            if isinstance(action, Action):
                if action.rebinding is not None:
                    if action.name in name_action_mapping:
                        print(f"{action.name} - {action.rebinding.input}") 
                        # defined keys
            

            #if action.name in name_action_mapping:
            #    print(option.name) 
        #    # defined keys
            
    


"""

for  <options type="joystick" instance="1" Product=" VKBsim Gladiator EVO R    {0200231D-0000-0000-0000-504944564944}">
   <flight_move_yaw invert="1"/>
  </options>
  <options type="joystick" instance="2" Product=" VKBsim Gladiator EVO OT L    {3201231D-0000-0000-0000-504944564944}">
   <flight_move_strafe_vertical invert="1"/>
   <flight_strafe_longitudinal invert="1"/>
  </options>
"""

instance_options = {}
