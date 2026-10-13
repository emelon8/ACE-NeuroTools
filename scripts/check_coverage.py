"""Fail CI when measured backend branch coverage falls below reviewed floors."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _percentage(summary: dict) -> float:
    total = summary["num_statements"] + summary["num_branches"]
    covered = summary["covered_lines"] + summary["covered_branches"]
    if total <= 0 or covered < 0 or covered > total:
        raise ValueError("Coverage must include executable lines and branches with valid counts.")
    return 100 * covered / total


def check_coverage(report: dict, policy: dict) -> tuple[list[str], list[str]]:
    """Return readable measurements and failures; missing reports fail closed."""
    if report.get("meta", {}).get("branch_coverage") is not True:
        raise ValueError("Branch coverage is required. Run pytest with --cov-branch.")
    files = {name.replace("\\", "/"): details for name, details in report["files"].items()}
    measurements, errors = [], []
    targets = {"TOTAL": policy["minimum_total"], **policy["files"]}
    for name, minimum in targets.items():
        if isinstance(minimum, bool) or not isinstance(minimum, (int, float)) or not math.isfinite(minimum):
            raise ValueError(f"Invalid coverage floor for {name}: {minimum!r}")
        if not 0 <= minimum <= 100:
            raise ValueError(f"Coverage floor must be between 0 and 100: {name}")
        if name == "TOTAL":
            summary = report["totals"]
        elif name in files:
            summary = files[name]["summary"]
        else:
            errors.append(f"{name}: absent from coverage; the module may no longer be exercised.")
            continue
        actual = _percentage(summary)
        measurements.append(f"{name}: {actual:.2f}% (required {minimum:g}%)")
        if actual < minimum:
            errors.append(f"{name}: {actual:.2f}% is below {minimum:g}%; add tests before merging.")
    return measurements, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--policy", type=Path, default=ROOT / "ci/coverage-policy.json")
    args = parser.parse_args()
    try:
        measured, failures = check_coverage(json.loads(args.report.read_text()), json.loads(args.policy.read_text()))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot verify backend coverage: {exc}", file=sys.stderr)
        return 1
    print("\n".join(measured))
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
