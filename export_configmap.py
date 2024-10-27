from scdatatools.sc import StarCitizen
import json
sc = StarCitizen('F:/Star Citizen')

actionmap = sc.default_profile.actionmap()
with open("actionmap.json", "w") as f:
    f.write(json.dumps(actionmap, indent=4))
