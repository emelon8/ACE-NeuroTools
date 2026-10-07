#!/usr/bin/env python3
"""Start or reopen ACE Experiments without activating a Conda environment."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def running(port):
    try:
        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1) as response:
            return json.load(response).get("application") == "ACE Experiments"
    except (OSError, URLError, ValueError):
        return False


def find_python():
    candidates = [
        os.environ.get("ACE_GUI_PYTHON"),
        Path.home() / ".conda/envs/caiman/bin/python",
        Path.home() / "miniforge3/envs/caiman/bin/python",
        Path.home() / "miniconda3/envs/caiman/bin/python",
        sys.executable,
    ]
    for candidate in dict.fromkeys(str(item) for item in candidates if item):
        if not Path(candidate).is_file():
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "import numpy, pandas, cv2, PIL, caiman"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            if result.returncode == 0:
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError(
        "No ACE analysis environment was found. Install or activate the project's CaImAn environment, then launch ACE Experiments again."
    )


def main():
    parser = argparse.ArgumentParser(description="Open ACE Experiments with its existing analysis environment.")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--project", default=str(ROOT / "data") if (ROOT / "data/experiments.csv").exists() else None)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check the analysis environment without starting a server")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Choose a port between 1 and 65535.")
    url = f"http://127.0.0.1:{args.port}/"
    try:
        if not args.check and running(args.port):
            if not args.no_browser:
                webbrowser.open(url)
            print(f"ACE Experiments is already running: {url}")
            return 0
        python = find_python()
        if args.check:
            print(f"Analysis environment ready: {python}")
            return 0
        cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "aceneurotools"
        cache.mkdir(parents=True, exist_ok=True)
        log = cache / "gui.log"
        command = [python, str(ROOT / "scripts/run_gui.py"), "--port", str(args.port), "--no-browser"]
        if args.project:
            command += ["--project", args.project]
        environment = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLCONFIGDIR": str(cache / "matplotlib"),
        }
        with log.open("a") as output:
            process = subprocess.Popen(
                command, cwd=ROOT, env=environment, stdout=output, stderr=output, start_new_session=True
            )
        for _ in range(150):
            if running(args.port):
                if not args.no_browser:
                    webbrowser.open(url)
                print(f"ACE Experiments: {url}")
                return 0
            if process.poll() is not None:
                raise RuntimeError(
                    f"ACE could not start on port {args.port}. Check {log}, or choose another port with --port."
                )
            time.sleep(0.2)
        raise RuntimeError(f"ACE is taking longer to start. Check {log} before trying again.")
    except (OSError, RuntimeError) as exc:
        message = str(exc)
        print(message, file=sys.stderr)
        if shutil.which("notify-send"):
            subprocess.run(["notify-send", "ACE Experiments could not start", message], check=False)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
