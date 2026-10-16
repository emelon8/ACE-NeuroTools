"""Stopping reports success only after a real worker has exited."""

import json
import signal
import subprocess
import sys

import pytest

from aceneurotools.gui.csv_projects import Project
from aceneurotools.gui.runs import Runs, atomic_json


@pytest.fixture
def run(tmp_path):
    (tmp_path / "experiments.csv").write_text("line number,id\n1,A\n")
    project = Project.open(tmp_path)
    directory = tmp_path / ".ace-runs/20261016T100000-aaaaaaaa"
    directory.mkdir(parents=True)
    atomic_json(
        directory / "run.json",
        {
            "state": "running",
            "id": directory.name,
            "kind": "compute",
            "number": "1",
            "parameters": {},
            "started": "2026-10-16",
            "finished": None,
        },
    )
    service = Runs()
    # Stop's state transition is inspected directly; output formatting is tested elsewhere.
    service.inspect = lambda project, run_id: json.loads((directory / "run.json").read_text())
    return project, directory, service


@pytest.mark.parametrize("already_exited", [False, True])
def test_stop_waits_for_exit_and_accepts_an_already_exited_worker(run, already_exited):
    project, directory, service = run
    process = subprocess.Popen(
        [sys.executable, "-c", "pass" if already_exited else "import time; time.sleep(60)"], start_new_session=True
    )
    service.processes[str(directory)] = process
    if already_exited:
        process.wait(timeout=10)
    try:
        detail = service.stop(project, directory.name)
        assert process.poll() is not None
        assert detail["state"] == "stopped" and detail["exit_code"] == process.returncode
        assert service.stop(project, directory.name)["state"] == "stopped"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process-group termination")
def test_worker_ignoring_terminate_is_force_killed_before_stopped(run):
    project, directory, service = run
    code = "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print('ready',flush=True); time.sleep(60)"
    process = subprocess.Popen([sys.executable, "-c", code], start_new_session=True, stdout=subprocess.PIPE, text=True)
    assert process.stdout.readline().strip() == "ready"
    service.processes[str(directory)] = process
    try:
        detail = service.stop(project, directory.name)
        assert process.returncode == -signal.SIGKILL
        assert detail["state"] == "stopped"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        process.stdout.close()
