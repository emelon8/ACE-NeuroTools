"""Select CI jobs and regression groups from the complete Git change range.

Only known independent boundaries are narrowed. Unknown files and shared code
use the full suite. This script needs only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ("test_gui_*.py", "test_calcium_imaging_names.py")
INTEGRATION = (
    *GUI,
    "test_cli_config.py",
    "test_setup_wizard.py",
    "test_pipeline_defaults.py",
    "test_shared_import_surface.py",
    "test_modular_stats.py",
    "test_stats_*.py",
    "test_miniscope_ephys_alignment.py",
)
GROUPS = {
    "gui": GUI,
    "imaging": (*INTEGRATION, "test_miniscope_filtering.py", "test_onix_data_manager.py", "test_backend_*.py"),
    "ephys": (*INTEGRATION, "test_rhs2116_data_manager.py", "test_block_processor_artifacts.py", "test_backend_*.py"),
    "multimodal": (
        *INTEGRATION,
        "test_backend_*.py",
        "test_event_correlograms.py",
        "test_mutual_information.py",
        "test_oscillatory_events.py",
        "test_perievent.py",
        "test_signal_utils_extensions.py",
        "test_surrogate.py",
        "test_wavelets.py",
    ),
}
# These are exercised by the full-suite fallback for shared code. Other new test
# files are included in every focused code run until explicitly classified.
SHARED_TESTS = (
    "test_banner.py",
    "test_csv_worker.py",
    "test_experiments_csv_compat.py",
    "test_spike_trig_avg_deprecation.py",
    "test_installed_smoke.py",
    "test_ci_plan.py",
)
NATIVE_ENTRY_POINTS = {
    "src/aceneurotools/__init__.py",
    "src/aceneurotools/cli.py",
    "src/aceneurotools/gui/server.py",
    "src/aceneurotools/gui/native_dialogs.py",
}
DOC_TOOLS = {"scripts/check_docs_links.py", "scripts/sync_notebooks_for_docs.sh"}


def plan_changes(paths: list[str], *, force_full: bool = False, root: Path = ROOT) -> dict:
    """Return job flags and explicit pytest paths; unions preserve mixed changes."""
    docs = package = conda = False
    full = force_full
    groups: set[str] = set()
    direct_tests: set[str] = set()
    for name in paths:
        path = Path(name)
        if path.suffix.lower() in {".md", ".rst"} or name.startswith(("docs/", "notebooks/", "overrides/")):
            docs = True
        elif name in {"mkdocs.yml", ".readthedocs.yaml"} or name in DOC_TOOLS:
            docs = True
        elif name.startswith("tests/"):
            if path.name.startswith("test_") and path.suffix == ".py" and (root / name).is_file():
                direct_tests.add(name)
                if path.name.startswith("test_gui_"):
                    groups.add("gui")  # GUI tests import fixtures from each other.
            else:
                full = True  # Helpers, fixtures, deletions, and renamed test sources.
        elif name.startswith("src/aceneurotools/"):
            package = True
            docs |= path.suffix == ".py"  # API pages inspect Python sources.
            conda |= name in NATIVE_ENTRY_POINTS
            if name.startswith("src/aceneurotools/gui/"):
                if path.suffix in {".py", ".js", ".html"}:
                    groups.add("gui")
                elif path.suffix not in {".css", ".woff2", ".png", ".svg", ".ico", ".txt"}:
                    full = True
            elif path.suffix != ".py":
                full = True
            elif name.startswith(("src/aceneurotools/calcium_imaging/", "src/aceneurotools/miniscope/")):
                groups.add("imaging")
            elif name.startswith("src/aceneurotools/ephys/"):
                groups.add("ephys")
            elif name.startswith("src/aceneurotools/multimodal/"):
                groups.add("multimodal")
            else:
                full = True  # Shared utilities, pipeline orchestration, and new areas.
        else:
            full = True  # Dependencies, recipes, workflows, scripts, or unknown paths.

    if full:
        return {
            "docs": True,
            "tests": True,
            "package": True,
            "conda": True,
            "test_paths": ["tests/"],
            "groups": ["full"],
        }

    def matches(patterns):
        return {str(p.relative_to(root)) for pattern in patterns for p in (root / "tests").glob(pattern)}

    selected = set(direct_tests)
    for group in groups:
        selected.update(matches(GROUPS[group]))
    if groups:
        classified = matches((*SHARED_TESTS, *(pattern for patterns in GROUPS.values() for pattern in patterns)))
        selected.update(
            str(p.relative_to(root))
            for p in (root / "tests").rglob("test_*.py")
            if str(p.relative_to(root)) not in classified
        )
    return {
        "docs": docs,
        "tests": bool(selected),
        "package": package,
        "conda": conda,
        "test_paths": sorted(selected),
        "groups": sorted(groups) or (["changed tests"] if direct_tests else []),
    }


def changed_paths(event: dict, event_name: str, ref: str) -> list[str] | None:
    """Use PR merge-base or the entire push, including both sides of renames.

    None means the range is unavailable/unsupported: never silently skip checks.
    """
    if event_name == "pull_request":
        base = event["pull_request"]["base"]["sha"]
        head = event["pull_request"]["head"]["sha"]
        revision_range = f"{base}...{head}"
    elif event_name == "push" and not ref.startswith("refs/tags/"):
        base, head = event.get("before"), event.get("after")
        if not base or not head or set(base) == {"0"}:
            return None
        revision_range = f"{base}..{head}"
    else:
        return None
    try:
        output = subprocess.check_output(
            ["git", "diff", "--no-renames", "--name-only", "-z", revision_range, "--"], cwd=ROOT
        )
    except subprocess.CalledProcessError:
        return None
    return [name.decode("utf-8", errors="surrogateescape") for name in output.split(b"\0") if name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-tests", action="store_true", help="Run the pytest paths in CI_TEST_PATHS")
    args = parser.parse_args()
    if args.run_tests:
        paths = json.loads(os.environ["CI_TEST_PATHS"])
        if (
            not isinstance(paths, list)
            or not paths
            or not all(isinstance(path, str) and path.startswith("tests/") for path in paths)
        ):
            parser.error("CI_TEST_PATHS must be a nonempty JSON list of test paths")
        raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", *paths, "-m", "not slow"], cwd=ROOT))
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    paths = changed_paths(event, os.environ["GITHUB_EVENT_NAME"], os.environ["GITHUB_REF"])
    plan = plan_changes(paths or [], force_full=paths is None)
    print(json.dumps(plan, indent=2))
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        for key in ("docs", "tests", "package", "conda"):
            output.write(f"{key}={str(plan[key]).lower()}\n")
        output.write(f"test_paths={json.dumps(plan['test_paths'])}\n")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
        summary.write("## Checks selected for this change\n\n")
        for key in ("docs", "tests", "package", "conda"):
            summary.write(f"- {key}: {'run' if plan[key] else 'skip'}\n")
        summary.write(f"\nTest groups: {', '.join(plan['groups']) or 'none'}\n\n")
        summary.write("```json\n" + json.dumps(plan["test_paths"], indent=2) + "\n```\n")


if __name__ == "__main__":
    main()
