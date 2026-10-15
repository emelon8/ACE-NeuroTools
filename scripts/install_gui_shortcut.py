#!/usr/bin/env python3
"""Install a user-only application-menu shortcut for the current checkout."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def install(root=ROOT, destination=None):
    folder = (
        Path(destination)
        if destination
        else Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "applications"
    )
    folder.mkdir(parents=True, exist_ok=True)
    executable = (
        str(root / "launch-gui").replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
    )
    path = folder / "ace-experiments.desktop"
    path.write_text(
        f'[Desktop Entry]\nVersion=1.0\nType=Application\nName=ACE Experiments\nComment=Browse experiments, crop recordings, and review neurons\nExec="{executable}"\nIcon=applications-science\nTerminal=false\nCategories=Education;Science;\nStartupNotify=true\n'
    )
    path.chmod(0o755)
    return path


if __name__ == "__main__":
    print(f"Installed ACE Experiments in your application menu: {install()}")
