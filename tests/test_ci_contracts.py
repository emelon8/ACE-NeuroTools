"""Regression tests for the checks that decide whether a change may merge."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from scripts.check_coverage import check_coverage

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def coverage_data():
    counts = {"num_statements": 10, "num_branches": 10, "covered_lines": 10, "covered_branches": 8}
    return {"meta": {"branch_coverage": True}, "totals": counts, "files": {"src/core.py": {"summary": counts}}}


def test_coverage_gate_counts_branches_and_accepts_exact_threshold(coverage_data):
    measured, failures = check_coverage(coverage_data, {"minimum_total": 90, "files": {"src/core.py": 90}})
    assert failures == []
    assert len(measured) == 2
    _, failures = check_coverage(coverage_data, {"minimum_total": 91, "files": {"src/core.py": 91}})
    assert len(failures) == 2


def test_coverage_gate_refuses_missing_module_and_line_only_report(coverage_data):
    _, failures = check_coverage(coverage_data, {"minimum_total": 80, "files": {"src/missing.py": 80}})
    assert "absent" in failures[0]
    coverage_data["meta"]["branch_coverage"] = False
    with pytest.raises(ValueError, match="Branch coverage"):
        check_coverage(coverage_data, {"minimum_total": 80, "files": {}})


@pytest.mark.parametrize("floor", [float("nan"), float("inf"), -1, 101, True, "80"])
def test_invalid_coverage_policy_cannot_turn_a_failure_green(coverage_data, floor):
    with pytest.raises(ValueError):
        check_coverage(coverage_data, {"minimum_total": floor, "files": {}})


def test_coverage_gate_understands_windows_path_separators(coverage_data):
    report = copy.deepcopy(coverage_data)
    report["files"] = {"src\\core.py": coverage_data["files"]["src/core.py"]}
    _, failures = check_coverage(report, {"minimum_total": 80, "files": {"src/core.py": 80}})
    assert failures == []


def workflow(name):
    # BaseLoader keeps GitHub's YAML key "on" as a string (not YAML 1.1 True).
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


@pytest.mark.parametrize("platform", ["linux-64", "win-64"])
def test_locked_environment_supports_caiman_declared_dependencies_and_movie_cleanup(platform):
    lock = yaml.safe_load((ROOT / "conda-lock.yml").read_text())
    packages = {package["name"]: package for package in lock["package"] if package["platform"] == platform}
    # CaImAn's wheel metadata declares these even though its conda recipe omits them.
    missing = {"cython", "moviepy", "numpydoc", "yapf"} - packages.keys()
    assert not missing, f"{platform}: missing CaImAn requirements: {sorted(missing)}"
    # CaImAn's AVI reader unconditionally calls cv2.destroyAllWindows().
    for name in ("opencv", "libopencv", "py-opencv"):
        assert "headless" not in packages[name]["url"], f"{platform}: {name} cannot clean up movie windows"


def test_ci_covers_feature_branch_pull_requests_manual_runs_and_merge_queue():
    ci = workflow("ci.yml")
    assert "proj-comenius" in ci["on"]["push"]["branches"]
    for trigger in ("pull_request", "workflow_dispatch", "merge_group", "schedule"):
        assert trigger in ci["on"]
    assert "paths" not in ci["on"]["pull_request"]
    assert ci["permissions"] == {"contents": "read"}


def test_release_uses_the_same_checks_as_pull_requests():
    assert workflow("release.yml")["jobs"]["verify"]["uses"] == "./.github/workflows/checks.yml"
    assert workflow("ci.yml")["jobs"]["checks"]["uses"] == "./.github/workflows/checks.yml"


def test_portable_jobs_discover_future_backend_tests_and_cover_claimed_python_versions():
    portable = workflow("checks.yml")["jobs"]["portable"]
    assert set(portable["strategy"]["matrix"]["python"]) == {"3.11", "3.12"}
    command = next(step["run"] for step in portable["steps"] if step.get("name", "").startswith("Test core"))
    assert "pytest tests/ --backend-only --without-caiman" in command
    assert "not requires_caiman" in command
    assert "test_backend_csv_integrity.py" not in command


def test_portable_collection_executes_new_tests_and_excludes_heavy_imports(tmp_path):
    (tmp_path / "conftest.py").write_text((ROOT / "tests/conftest.py").read_text())
    (tmp_path / "test_future_backend.py").write_text("def test_new_contract():\n    assert True\n")
    (tmp_path / "test_gui_probe.py").write_text("raise AssertionError('GUI was collected')\n")
    compiled = tmp_path / "compiled_stack"
    compiled.mkdir()
    (compiled / "test_movie.py").write_text("raise AssertionError('compiled imports were collected')\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--backend-only", "--without-caiman", "--fail-on-skip", str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0 and "1 passed" in result.stdout, result.stdout + result.stderr


def test_release_downloads_the_tested_artifact_instead_of_rebuilding():
    release, checks = workflow("release.yml"), workflow("checks.yml")
    assert (
        checks["on"]["workflow_call"]["outputs"]["distributions-artifact"]["value"]
        == "${{ jobs.package.outputs.artifact-name }}"
    )
    for name in ("publish-pypi", "github-release"):
        job = release["jobs"][name]
        assert set(job["needs"]) == {"verify", "version"}
        download = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/download-artifact"))
        assert download["with"]["name"] == "${{ needs.verify.outputs.distributions-artifact }}"
    assert not any(
        "python -m build" in step.get("run", "") for job in release["jobs"].values() for step in job.get("steps", [])
    )
    assert any(
        step.get("name") == "Smoke-test installed source distribution" for step in checks["jobs"]["package"]["steps"]
    )


def test_quality_gate_cannot_pass_when_a_required_job_fails_or_is_skipped():
    checks = workflow("checks.yml")
    gate = checks["jobs"]["quality-gate"]
    required = {
        name for name, job in checks["jobs"].items() if name != "quality-gate" and not job.get("continue-on-error")
    }
    assert set(gate["needs"]) == required
    assert "always()" in gate["if"]
    command = "\n".join(step.get("run", "") for step in gate["steps"])
    assert 'result != "success"' in command
    assert 'json.loads(os.environ["NEEDS_RESULTS"])' in command


def test_backend_jobs_keep_audit_reports_even_after_failure():
    backend = workflow("checks.yml")["jobs"]["backend"]
    assert set(backend["strategy"]["matrix"]["os"]) == {"ubuntu-latest", "windows-latest"}
    commands = "\n".join(step.get("run", "") for step in backend["steps"])
    assert "--backend-only" in commands and "--fail-on-skip" in commands
    assert "--cov-branch" in commands and "check_coverage.py" in commands
    uploads = [step for step in backend["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert uploads and all("always()" in step.get("if", "") for step in uploads)
    assert int(backend["timeout-minutes"]) <= 45


@pytest.mark.parametrize("outcome", ["success", "failure", "skipped", "cancelled"])
def test_actual_quality_gate_exit_status_for_each_job_outcome(tmp_path, outcome):
    command = workflow("checks.yml")["jobs"]["quality-gate"]["steps"][0]["run"]
    code = "\n".join(command.splitlines()[1:-1])
    summary = tmp_path / "summary.md"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=10,
        env={
            **os.environ,
            "NEEDS_RESULTS": json.dumps({"backend": {"result": outcome}}),
            "GITHUB_STEP_SUMMARY": str(summary),
        },
    )
    assert result.returncode == (0 if outcome == "success" else 1), result.stderr
    assert f"| backend | {outcome} |" in summary.read_text()


@pytest.mark.parametrize("body", ["pass", "pytest.skip('missing scientific dependency')", "pytest.xfail('broken')"])
def test_actual_skip_guard_cannot_report_success_without_execution(tmp_path, body):
    (tmp_path / "conftest.py").write_text((ROOT / "tests/conftest.py").read_text())
    (tmp_path / "test_probe.py").write_text(f"import pytest\ndef test_probe():\n    {body}\n")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--fail-on-skip", str(tmp_path / "test_probe.py")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == (0 if body == "pass" else 1), result.stdout + result.stderr
