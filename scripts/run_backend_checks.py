"""Run the local equivalent of the blocking backend CI checks with one command."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extended", action="store_true", help="Generate 500 cases per property test.")
    args = parser.parse_args()
    env = {
        **os.environ,
        "MPLBACKEND": "Agg",
        "HYPOTHESIS_PROFILE": "extended" if args.extended else "ci",
        "PYTHONHASHSEED": "0",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
    commands = [
        [sys.executable, "scripts/ci_environment.py", "reports/environment.json"],
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "--backend-only",
            "--fail-on-skip",
            "-m",
            "not slow",
            "--junitxml=reports/junit.xml",
            "--durations=15",
            "--cov=aceneurotools",
            "--cov-branch",
            "--cov-report=json:reports/coverage.json",
            "--cov-report=xml:reports/coverage.xml",
            "--cov-report=html:reports/coverage-html",
            "--cov-report=term:skip-covered",
        ],
        [sys.executable, "scripts/check_coverage.py", "reports/coverage.json"],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT, env=env)
        if result.returncode:
            print("Backend checks failed. See the failure above and reports/ for details.", file=sys.stderr)
            return result.returncode
    print("Backend integrity checks passed. Audit reports are in reports/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
