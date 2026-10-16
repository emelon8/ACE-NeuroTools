"""Install a built wheel in isolation, then exercise import, CLI and GUI HTTP.

Run `python scripts/smoke_installed_package.py --wheel dist/<wheel>.whl`.
Use `--installed` when CI has already installed the conda package.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import venv
from importlib.metadata import distribution
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def check_installed():
    from importlib.resources import files

    import aceneurotools

    metadata = distribution("aceneurotools")
    assert metadata.version == aceneurotools.__version__
    root = files("aceneurotools.gui")
    for name in ("index.html", "app.js", "style.css"):
        assert root.joinpath(name).read_bytes(), name
    entries = {entry.name: entry for entry in metadata.entry_points}
    assert {"ace-neuro", "ace-gui"} <= entries.keys()
    bindir = Path(sys.executable).parent
    suffix = ".exe" if os.name == "nt" else ""
    subprocess.run([str(bindir / ("ace-neuro" + suffix)), "--help"], check=True, capture_output=True, timeout=30)
    process = subprocess.Popen(
        [str(bindir / ("ace-gui" + suffix)), "--port", "0", "--no-browser"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines = queue.Queue()

    def read_output():
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    try:
        line = lines.get(timeout=30)
        assert line and line.startswith("Experiment application: "), line
        url = line.split(": ", 1)[1].strip()
        parsed = urlsplit(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        headers = {"Authorization": f"Bearer {parsed.fragment.removeprefix('token=')}"} if parsed.fragment else {}
        for path in ("/", "/app.js", "/style.css", "/api/health"):
            with urlopen(Request(base + path, headers=headers), timeout=10) as response:
                body = response.read()
                assert response.status == 200 and body
                if path == "/api/health":
                    assert json.loads(body)["application"] == "ACE Experiments"
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        process.stdout.close()
    print(f"Installed {metadata.version}: import, CLI, GUI assets and HTTP passed.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--wheel", type=Path)
    mode.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="ace-installed-smoke-") as directory:
        clean_env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME"}}
        if args.wheel:
            wheel = args.wheel.resolve(strict=True)
            prefix = Path(directory) / "environment"
            venv.EnvBuilder(with_pip=True).create(prefix)
            python = prefix / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            subprocess.run(
                [str(python), "-m", "pip", "install", "--no-deps", str(wheel)], check=True, env=clean_env, cwd=directory
            )
            subprocess.run(
                [str(python), str(Path(__file__).resolve()), "--installed"],
                check=True,
                env=clean_env,
                cwd=directory,
                timeout=90,
            )
        else:
            os.chdir(directory)
            check_installed()


if __name__ == "__main__":
    main()
