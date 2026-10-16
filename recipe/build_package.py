"""Build the Python package and install standard menuinst metadata."""

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

import jsonschema

subprocess.run(
    [sys.executable, "-m", "pip", "install", ".", "--no-deps", "--no-build-isolation", "--no-compile"], check=True
)
source = Path("recipe/menu/ace-neurotools.json")
schema = files("menuinst").joinpath("data/menuinst-1-1-3.schema.json")
jsonschema.validate(json.loads(source.read_text()), json.loads(schema.read_text()))
menu = Path(os.environ["PREFIX"]) / "Menu"
menu.mkdir(exist_ok=True)
shutil.copy2(source, menu / source.name)
