"""Optional desktop dialogs and folder opening; no scientific dependencies added."""

import json
import os
import shutil
import stat
import subprocess
import sys
import threading
from pathlib import Path

from gui.csv_projects import ProjectError

TK_PICKER = """
import json, sys, tkinter as tk
from tkinter import filedialog
options = json.loads(sys.argv[1])
root = tk.Tk(); root.withdraw()
root.attributes('-topmost', True)
kwargs = dict(title=options['title'], initialdir=options['initial'])
if options['kind'] == 'folder':
    value = filedialog.askdirectory(**kwargs, mustexist=True)
elif options['multiple']:
    value = filedialog.askopenfilenames(**kwargs, filetypes=options['types'])
else:
    value = filedialog.askopenfilename(**kwargs, filetypes=options['types'])
print(json.dumps(list(value) if isinstance(value, tuple) else [value] if value else []))
root.destroy()
"""


def desktop_environment():
    environment = dict(os.environ)
    # A detached launcher may lack display variables. Reuse this user's Wayland
    # socket without inspecting unrelated processes or account settings.
    if sys.platform.startswith("linux") and not (environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY")):
        runtime = Path(environment.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        try:
            sockets = sorted(path for path in runtime.glob("wayland-*") if stat.S_ISSOCK(path.stat().st_mode))
            if sockets:
                environment.update(XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY=sockets[0].name)
                if (runtime / "bus").exists():
                    environment.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime / 'bus'}")
        except OSError:
            pass
    return environment


class NativeDialogs:
    def __init__(self):
        self.lock = threading.Lock()

    def pick(self, body):
        kind = body.get("kind", "folder")
        if not isinstance(kind, str) or kind not in {"folder", "estimates", "file", "movies"}:
            raise ProjectError("Choose a supported file or folder picker.")
        initial = body.get("initial") or str(Path.home())
        if not isinstance(initial, str):
            raise ProjectError("Choose a valid starting location.")
        initial = Path(initial).expanduser()
        if not initial.is_absolute():
            initial = Path.home() / initial
        while not initial.is_dir() and initial != initial.parent:
            initial = initial.parent
        title = {
            "folder": "Choose a folder",
            "estimates": "Choose CNMF-E estimates",
            "movies": "Choose recording movies",
            "file": "Choose a file",
        }[kind]
        types = {
            "estimates": [("CNMF estimates", "*.hdf5 *.h5 *.HDF5 *.H5")],
            "movies": [("AVI movies", "*.avi *.AVI")],
            "file": [("All files", "*")],
            "folder": [],
        }[kind]
        environment = desktop_environment()
        if sys.platform.startswith("linux") and not (environment.get("DISPLAY") or environment.get("WAYLAND_DISPLAY")):
            return {"available": False, "paths": []}
        if not self.lock.acquire(blocking=False):
            raise ProjectError("A system file picker is already open. Choose a location or cancel it first.")
        try:
            zenity, kdialog = shutil.which("zenity"), shutil.which("kdialog")
            if sys.platform.startswith("linux") and zenity:
                command = [zenity, "--file-selection", f"--title={title}", f"--filename={initial}{os.sep}"]
                if kind == "folder":
                    command.append("--directory")
                if kind == "movies":
                    command.extend(["--multiple", "--separator=\n"])
                for label, pattern in types:
                    command.append(f"--file-filter={label} | {pattern}")
            elif sys.platform.startswith("linux") and kdialog:
                command = [kdialog, "--getexistingdirectory" if kind == "folder" else "--getopenfilename", str(initial)]
                if kind != "folder":
                    command.append("*.hdf5 *.h5" if kind == "estimates" else "*.avi" if kind == "movies" else "*")
                command.extend(["--title", title])
                if kind == "movies":
                    command.extend(["--multiple", "--separate-output"])
            else:
                command = [
                    sys.executable,
                    "-c",
                    TK_PICKER,
                    json.dumps(
                        dict(kind=kind, title=title, initial=str(initial), types=types, multiple=kind == "movies")
                    ),
                ]
            result = subprocess.run(command, capture_output=True, text=True, env=environment, timeout=300, check=False)
            if result.returncode == 1:  # Native chooser cancellation.
                return {
                    "available": "-c" not in command and "cannot open display" not in result.stderr.lower(),
                    "paths": [],
                }
            if result.returncode != 0:
                return {"available": False, "paths": []}
            paths = json.loads(result.stdout) if "-c" in command else result.stdout.rstrip("\n").split("\n")
            paths = [str(Path(value).expanduser().resolve()) for value in paths if value]
            if len(paths) > 1 and kind != "movies":
                raise ProjectError("Choose one file or folder.")
            for value in paths:
                path = Path(value)
                if not (path.is_dir() if kind == "folder" else path.is_file()):
                    raise ProjectError("The selected file or folder no longer exists.")
                if kind in {"estimates", "movies"} and path.suffix.lower() not in (
                    {".hdf5", ".h5"} if kind == "estimates" else {".avi"}
                ):
                    raise ProjectError(
                        "Choose an estimates HDF5 file." if kind == "estimates" else "Choose AVI movie files."
                    )
            return {"available": True, "paths": paths}
        except ProjectError:
            raise
        except (OSError, subprocess.TimeoutExpired, ValueError):
            return {"available": False, "paths": []}
        finally:
            self.lock.release()

    def open_folder(self, path):
        path = Path(path).expanduser().resolve()
        if not path.is_dir():
            raise ProjectError("This output folder does not exist yet. Start the run first.")
        environment = desktop_environment()
        try:
            if sys.platform == "win32":
                os.startfile(str(path))
            else:
                command = ["open", str(path)] if sys.platform == "darwin" else ["xdg-open", str(path)]
                result = subprocess.run(command, capture_output=True, env=environment, timeout=10, check=False)
                if result.returncode:
                    raise OSError()
        except (OSError, subprocess.TimeoutExpired):
            raise ProjectError(
                "The system file manager could not open this folder. Its location is shown in Results."
            ) from None
        return {"opened": True, "path": str(path)}
