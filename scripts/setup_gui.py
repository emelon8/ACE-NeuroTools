"""Set up a dedicated analysis environment and a launch file for lab users."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def platform_key(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    choices = {
        ("Windows", "amd64"): "win-64",
        ("Windows", "x86_64"): "win-64",
        ("Darwin", "arm64"): "osx-arm64",
        ("Darwin", "aarch64"): "osx-arm64",
        ("Darwin", "x86_64"): "osx-64",
        ("Linux", "x86_64"): "linux-64",
    }
    if (system, machine) not in choices:
        raise RuntimeError(f"This setup does not support {system} ({machine}). Use a 64-bit Intel/AMD PC or a Mac.")
    return choices[system, machine]


def conda_python():
    candidates = [os.environ.get("CONDA_PYTHON_EXE"), sys.executable]
    for name in ("miniforge3", "Miniforge3"):
        base = Path.home() / name
        candidates.append(str(base / ("python.exe" if sys.platform == "win32" else "bin/python")))
    for candidate in dict.fromkeys(value for value in candidates if value):
        if not Path(candidate).is_file():
            continue
        result = subprocess.run([candidate, "-m", "conda", "--version"], capture_output=True, timeout=30)
        if result.returncode == 0:
            return str(Path(candidate).resolve())
    raise RuntimeError(
        "Miniforge was not found. Follow docs/gui_installation.md, open Miniforge Prompt (Windows) "
        "or Terminal (Mac), and run setup again."
    )


def environment_command(base_python, prefix, *arguments):
    return [base_python, "-m", "conda", "run", "--no-capture-output", "--prefix", str(prefix), *arguments]


def write_launcher(root, base_python, prefix, system=None):
    system = system or platform.system()
    command = environment_command(base_python, prefix, "python", str(root / "scripts/start_gui.py"))
    if system == "Windows":
        # Batch files expand percent signs even in quoted arguments.
        if any('"' in value or "\n" in value or "\r" in value for value in command):
            raise RuntimeError("Install ACE in a folder without quotes or newline characters in its name.")
        quoted = " ".join('"' + value.replace("%", "%%") + '"' for value in command)
        target = root / "Open ACE Experiments.cmd"
        source = f"@echo off\r\nsetlocal DisableDelayedExpansion\r\n{quoted} %*\r\nif errorlevel 1 pause\r\n"
    else:
        target = root / ("Open ACE Experiments.command" if system == "Darwin" else "Open ACE Experiments.sh")
        source = (
            "#!/bin/bash\n"
            + shlex.join(command)
            + ' "$@"'
            + '\nstatus=$?\nif [ "$status" -ne 0 ]; then\n'
            + '  echo "ACE could not open. See the message above and docs/gui_installation.md."\n'
            + '  read -r -p "Press Return to close this window."\nfi\nexit "$status"\n'
        )
    target.write_text(source, encoding="utf-8", newline="")
    if system != "Windows":
        target.chmod(0o755)
    return target


def execute(command, log, environment):
    with subprocess.Popen(
        command,
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    ) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        if process.wait():
            raise RuntimeError("A setup step failed. Keep setup.log and send it to your lab's ACE maintainer.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".ace-neurotools/gui-env")
    parser.add_argument("--no-launcher", action="store_true", help="For automated installation checks.")
    args = parser.parse_args()
    log_path = ROOT / "setup.log"
    try:
        key = platform_key()
        specification = ROOT / "installer" / key / "environment.yml"
        if not specification.is_file():
            raise RuntimeError(f"The download lacks {specification.name}. Extract the entire ACE ZIP and try again.")
        base_python = conda_python()
        prefix = args.prefix.expanduser().resolve()
        if prefix.exists() and not (prefix / "conda-meta/history").is_file():
            raise RuntimeError(f"{prefix} exists but is not a Conda environment. Choose a different --prefix folder.")
        action = "update" if prefix.exists() else "create"
        environment = {
            **os.environ,
            "PYTHONUNBUFFERED": "1",
            "MPLBACKEND": "Agg",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "CONDA_ALWAYS_YES": "true",
        }
        with log_path.open("w", encoding="utf-8") as log:
            print(f"Setting up ACE for {key}. Keep this window open; the first download can take a while.")
            execute(
                [base_python, "-m", "conda", "env", action, "--prefix", str(prefix), "--file", str(specification)],
                log,
                environment,
            )
            print("Installing ACE into its analysis environment...")
            execute(
                environment_command(
                    base_python, prefix, "python", "-m", "pip", "install", "--no-deps", "-e", str(ROOT)
                ),
                log,
                environment,
            )
            execute(environment_command(base_python, prefix, "python", "-m", "pip", "check"), log, environment)
            print("Checking movie reading and the local GUI server...")
            execute(
                environment_command(base_python, prefix, "python", str(ROOT / "scripts/check_gui_install.py")),
                log,
                environment,
            )
        (ROOT / ".ace-gui-install.json").write_text(
            json.dumps({"conda_python": base_python, "prefix": str(prefix)}, indent=2), encoding="utf-8"
        )
        if not args.no_launcher:
            launcher = write_launcher(ROOT, base_python, prefix)
            print(f"\nACE setup complete. Double-click: {launcher}")
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"\nSetup did not finish: {exc}\nSetup log: {log_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
