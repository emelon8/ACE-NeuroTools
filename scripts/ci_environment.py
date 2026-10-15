"""Save reproducibility evidence without credentials or arbitrary environment variables."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def evidence() -> dict:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    code_paths = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "src",
            "tests",
            "scripts",
            ".github",
            "ci",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    return {
        "commit": commit,
        "tracked_or_untracked_changes": bool(dirty),
        "python": sys.version,
        "platform": platform.platform(),
        "hypothesis_profile": os.environ.get("HYPOTHESIS_PROFILE", "default"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "dependencies": dict(
            sorted((dist.metadata["Name"], dist.version) for dist in importlib.metadata.distributions())
        ),
        "input_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("pyproject.toml", "conda-lock.yml", "ci/requirements-test.txt", "ci/coverage-policy.json")
        },
        # Fingerprint pending local edits too: a dirty checkout cannot be
        # reproduced from its HEAD commit alone. Do not include lab data.
        "code_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in sorted(set(code_paths))
            if name and (ROOT / name).is_file()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
