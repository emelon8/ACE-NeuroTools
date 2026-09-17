#!/usr/bin/env python3
"""Launch the installed workbench from any current working directory."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.is_file() or not (root / "dist/index.html").is_file():
    raise SystemExit("Workbench setup is incomplete. Follow gui/README.md, then run this launcher again.")
os.execv(str(python), [str(python), "-m", "ace_workbench", *sys.argv[1:]])
