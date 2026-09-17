"""Headless worker protocol. Callable from any explicitly configured Python runtime."""

from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import shutil
import sys
import traceback
from pathlib import Path

from .common import atomic_json, file_hash, read_json
from .runners.calcium import CalciumRunner
from .runners.ephys import EphysRunner
from .runners.tables import InventoryRunner, TraceRunner

RUNNERS = {
    "inventory": InventoryRunner,
    "trace-summary": TraceRunner,
    "cnmfe": CalciumRunner,
    "ephys-export": EphysRunner,
}


def verify_inputs(root: Path, configuration: dict) -> None:
    for item in configuration["inputs"]:
        path = root / item["path"]
        if not path.is_file() or path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root):
            raise ValueError(f"Input is missing or became a symbolic link: {item['path']}")
        if path.stat().st_size != item["size"] or file_hash(path) != item["sha256"]:
            raise ValueError(f"Input changed after import: {item['path']}. Import its new version explicitly.")


def environment() -> dict:
    packages = {}
    for name in ("aceneurotools", "caiman", "numpy", "scipy", "neo", "opencv-python", "h5py"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": packages,
    }


def run(spec_path: Path, check_only: bool) -> None:
    spec = read_json(spec_path)
    configuration = spec["configuration"]
    root, destination = Path(spec["input_root"]), Path(spec["output"])
    runner = RUNNERS[configuration["pipeline"]]()
    print("Verifying approved input hashes", flush=True)
    verify_inputs(root, configuration)
    if check_only:
        report = runner.check(root, configuration)
        report["environment"] = environment()
        atomic_json(destination, {"ok": True, **report})
        return
    output = destination / "outputs"
    output.mkdir(exist_ok=False)
    # Copy to a private run directory before scientific code can create sidecars.
    snapshot = destination / "inputs"
    snapshot.mkdir(exist_ok=False)
    print("Creating immutable run input snapshot", flush=True)
    for item in configuration["inputs"]:
        target = snapshot / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / item["path"], target)
    verify_inputs(snapshot, configuration)
    checked = runner.check(snapshot, configuration)
    if environment() != spec["environment"]:
        raise ValueError("Scientific runtime changed after preflight; review a new run plan.")
    atomic_json(
        output / "provenance.json",
        {
            "configuration": configuration,
            "environment": environment(),
            "preflight": checked,
            "approved_plan": spec["plan"],
            "pre_revision": spec["pre_revision"],
        },
    )
    print(f"Running {configuration['pipeline']}", flush=True)
    os.chdir(destination)
    runner.run(snapshot, configuration, output)
    # Detect any reader that wrote into its isolated input copy before reporting success.
    verify_inputs(snapshot, configuration)
    print("Processing finished; registering output provenance", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        run(args.spec, args.check)
        return 0
    except Exception as exc:
        traceback.print_exc()
        if args.check:
            spec = read_json(args.spec)
            atomic_json(Path(spec["output"]), {"ok": False, "error": str(exc), "environment": environment()})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
