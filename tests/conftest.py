"""Explicit backend selection and a CI rule against silent skips."""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, settings

settings.register_profile("ci", max_examples=100, deadline=None, derandomize=True, print_blob=True)
settings.register_profile(
    "extended",
    max_examples=500,
    deadline=None,
    print_blob=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))


def pytest_addoption(parser):
    parser.addoption(
        "--backend-only", action="store_true", help="Collect core tests, excluding GUI and crop-dialog tests."
    )
    parser.addoption("--fail-on-skip", action="store_true", help="Fail if a selected test is skipped or xfailed.")
    parser.addoption("--without-caiman", action="store_true", help="Exclude the compiled-stack test directory.")


def pytest_ignore_collect(collection_path, config):
    if config.getoption("--without-caiman") and collection_path.name == "compiled_stack":
        return True
    return config.getoption("--backend-only") and (
        collection_path.name.startswith("test_gui_") or collection_path.name == "test_crop_gui.py"
    )


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--fail-on-skip"):
        return
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    if terminal is None:
        return
    untested = terminal.stats.get("skipped", []) + terminal.stats.get("xfailed", [])
    if untested:
        terminal.write_sep("!", "CI requires selected tests to execute; remove the skip or restore its dependency.")
        for report in untested:
            terminal.write_line(report.nodeid)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
