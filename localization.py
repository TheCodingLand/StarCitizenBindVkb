
from pathlib import Path
from typing import Annotated, Dict

from pydantic import BaseModel

def key_startswith_at(key: str) -> str:
    if not key.startswith('@'):
        raise ValueError(f"Key '{key}' must start with '@'")
    return key

LocalizationString = Annotated[str, key_startswith_at]
localization_strings : Dict[LocalizationString, str] = {}


class LocalizationFile(BaseModel):
    localization_strings: Dict[LocalizationString, str] = {}

    @staticmethod
    def preprocess_localization_string_key(value: str) -> str:
        if value.endswith(',P'):
            value = value[:-2]
        return value.lower()
    
    @classmethod
    def from_file(cls, file: Path) -> 'LocalizationFile':
        localization_strings: Dict[LocalizationString, str] = {}
        for line in file.read_text(encoding='ISO-8859-1').splitlines():
            if len(line.split('=')) == 2:
                key, value =  line.split('=')
                localization_strings[cls.preprocess_localization_string_key(key)] = value
            elif len(line.split('=')) > 2:
                # concatenate the values after the first equal sign
                key, value =  line.split('=', 1)
                localization_strings[cls.preprocess_localization_string_key(key)] = '='.join(value)
            else:
                pass
        return cls(localization_strings=localization_strings)
    
    def get_localization_string(self, key: str) -> str:
        if key[1:] not in self.localization_strings:
            return key
        return self.localization_strings[key[1:]]
    



