from fnmatch import fnmatch
from importlib import import_module
from pathlib import Path
import tomllib


def test_console_script_targets_packaged_callable() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    script_target = pyproject["project"]["scripts"]["citizenbindvkb"]
    module_name, callable_name = script_target.split(":", maxsplit=1)
    include_patterns = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert any(fnmatch(module_name, pattern) for pattern in include_patterns)

    module = import_module(module_name)
    assert callable(getattr(module, callable_name))