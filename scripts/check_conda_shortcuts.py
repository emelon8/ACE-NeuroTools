"""Verify standard menuinst metadata and an installed native shortcut."""

import json
import os
import sys
from pathlib import Path

prefix = Path(sys.prefix)
metadata = json.loads((prefix / "Menu/ace-neurotools.json").read_text())
item = metadata["menu_items"][0]
assert item["command"] == ["{{ PYTHON }}", "-m", "aceneurotools.gui.server"]
assert {"linux", "osx", "win"} <= item["platforms"].keys()
if sys.platform == "win32":
    roots = [
        Path(os.environ[key]) / "Microsoft/Windows/Start Menu/Programs"
        for key in ("APPDATA", "PROGRAMDATA")
        if key in os.environ
    ]
    matches = [path for root in roots if root.exists() for path in root.rglob("ACE NeuroTools*.lnk")]
    desktop = [Path.home() / "Desktop", Path(os.environ.get("PUBLIC", str(Path.home()))) / "Desktop"]
    assert any(list(root.glob("ACE NeuroTools*.lnk")) for root in desktop if root.exists()), "Desktop shortcut missing"
elif sys.platform == "darwin":
    roots = [Path.home() / "Applications", Path("/Applications")]
    matches = [path for root in roots for path in root.glob("ACE NeuroTools*.app")]
else:
    roots = [
        Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "applications",
        Path("/usr/local/share/applications"),
        Path("/usr/share/applications"),
    ]
    matches = [
        path
        for root in roots
        for path in root.glob("*.desktop")
        if "ACE NeuroTools" in path.read_text(errors="replace")
    ]
assert matches, "menuinst did not create the native application shortcut"
print("Installed menuinst metadata and native application shortcut verified.")
