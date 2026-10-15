"""Check the installed launch file, detached server startup, and reopening."""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

import psutil

ROOT = Path(__file__).resolve().parents[1]


def launch(launcher, arguments, directory):
    if sys.platform == "win32":
        # The CI checkout path and these fixed flags are controlled by this test.
        command = '"' + str(launcher) + '" ' + " ".join(arguments)
        return subprocess.run(command, shell=True, cwd=directory, capture_output=True, text=True, timeout=120)
    return subprocess.run([str(launcher), *arguments], cwd=directory, capture_output=True, text=True, timeout=120)


def main():
    suffix = ".cmd" if sys.platform == "win32" else ".command" if sys.platform == "darwin" else ".sh"
    launcher = ROOT / ("Open ACE Experiments" + suffix)
    assert launcher.is_file(), "Setup did not create the launch file"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = str(probe.getsockname()[1])
    try:
        with tempfile.TemporaryDirectory(prefix="ace-launch-check-") as directory:
            checked = launch(launcher, ["--check"], directory)
            expected = Path(sys.prefix) / ("python.exe" if sys.platform == "win32" else "bin/python")
            assert checked.returncode == 0 and str(expected) in checked.stdout, checked.stdout + checked.stderr
            arguments = ["--no-browser", "--port", port]
            first = launch(launcher, arguments, directory)
            assert first.returncode == 0, first.stdout + first.stderr
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=10) as response:
                assert json.load(response)["application"] == "ACE Experiments"
            reopened = launch(launcher, arguments, directory)
            assert reopened.returncode == 0 and "already running" in reopened.stdout, reopened.stdout + reopened.stderr
    finally:
        # macOS restricts system-wide connection enumeration. Match only our
        # server's exact script and randomly allocated port, never another ACE.
        for process in psutil.process_iter(["pid", "cmdline"]):
            try:
                command = process.info.get("cmdline") or []
                if str(ROOT / "scripts/run_gui.py") in command and "--port" in command:
                    if command[command.index("--port") + 1] == port:
                        process.terminate()
                        process.wait(timeout=15)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    print("Launch file starts and reopens ACE from outside its checkout using the installed environment.")


if __name__ == "__main__":
    main()
