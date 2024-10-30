import json
from models.configmap import get_action_maps_file
from globals import get_installation

from rich import inspect

install = get_installation("LIVE")


for item in install.exported_control_maps:
    print(item)
    if "configurator" in item:
        print(item)
        break

x = get_action_maps_file(item)

inspect (x)
with open("dump.json", 'w') as f:
    f.write(json.dumps(x,indent=4))
# we need to map items between the action maps and the joystick binds