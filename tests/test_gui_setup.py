"""Installation selects native packages and preserves usable launcher arguments."""

import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from gui.csv_projects import ProjectError
from gui.runs import Runs
from scripts import setup_gui, start_gui


@pytest.mark.parametrize(
    "system,machine,expected",
    [("Windows", "AMD64", "win-64"), ("Darwin", "arm64", "osx-arm64"), ("Darwin", "x86_64", "osx-64")],
)
def test_native_platform_selection(system, machine, expected):
    assert setup_gui.platform_key(system, machine) == expected


def test_windows_arm_does_not_install_intel_packages():
    with pytest.raises(RuntimeError, match="does not support"):
        setup_gui.platform_key("Windows", "ARM64")


def test_mac_launcher_preserves_paths_with_spaces_and_shell_characters(tmp_path):
    root = tmp_path / "Lab's ACE $work"
    root.mkdir()
    base_python = str(tmp_path / "Miniforge 3/bin/python")
    prefix = tmp_path / "analysis env"
    launcher = setup_gui.write_launcher(root, base_python, prefix, "Darwin")
    assert shlex.split(launcher.read_text().splitlines()[1])[:-1] == setup_gui.environment_command(
        base_python, prefix, "python", str(root / "scripts/start_gui.py")
    )
    assert launcher.stat().st_mode & 0o111
    subprocess.run(["bash", "-n", str(launcher)], check=True)


def test_windows_launcher_quotes_paths_and_disables_delayed_expansion(tmp_path):
    root = tmp_path / "Lab ACE 10% !"
    root.mkdir()
    launcher = setup_gui.write_launcher(root, "C:\\Miniforge 3\\python.exe", tmp_path / "analysis env", "Windows")
    text = launcher.read_text()
    assert '"C:\\Miniforge 3\\python.exe"' in text
    assert "10%% !" in text
    assert "DisableDelayedExpansion" in text
    assert "if errorlevel 1 pause" in text


def test_failed_setup_does_not_publish_registration_or_launcher(tmp_path, monkeypatch):
    specification = tmp_path / "installer/win-64/environment.yml"
    specification.parent.mkdir(parents=True)
    specification.write_text("name: test\n")
    monkeypatch.setattr(setup_gui, "ROOT", tmp_path)
    monkeypatch.setattr(setup_gui, "platform_key", lambda: "win-64")
    monkeypatch.setattr(setup_gui, "conda_python", lambda: sys.executable)
    monkeypatch.setattr(sys, "argv", ["setup", "--prefix", str(tmp_path / "env")])

    def fail(*args):
        raise RuntimeError("download failed")

    monkeypatch.setattr(setup_gui, "execute", fail)
    assert setup_gui.main() == 1
    assert not (tmp_path / ".ace-gui-install.json").exists()
    assert not list(tmp_path.glob("Open ACE*"))


def test_setup_registers_only_after_movie_and_server_checks(tmp_path, monkeypatch):
    specification = tmp_path / "installer/osx-arm64/environment.yml"
    specification.parent.mkdir(parents=True)
    specification.write_text("name: test\n")
    prefix = tmp_path / "env"
    commands = []
    monkeypatch.setattr(setup_gui, "ROOT", tmp_path)
    monkeypatch.setattr(setup_gui, "platform_key", lambda: "osx-arm64")
    monkeypatch.setattr(setup_gui, "conda_python", lambda: sys.executable)
    monkeypatch.setattr(sys, "argv", ["setup", "--prefix", str(prefix), "--no-launcher"])
    monkeypatch.setattr(setup_gui, "execute", lambda command, *args: commands.append(command))
    assert setup_gui.main() == 0
    assert commands[0][3:5] == ["env", "create"]
    assert "--yes" not in commands[0]  # env update has no such flag.
    assert commands[-1][-1] == str(tmp_path / "scripts/check_gui_install.py")
    saved = json.loads((tmp_path / ".ace-gui-install.json").read_text())
    assert saved == {"conda_python": sys.executable, "prefix": str(prefix)}


def test_registered_launcher_reenters_conda_and_retains_arguments(tmp_path, monkeypatch):
    prefix = tmp_path / "env"
    prefix.mkdir()
    (tmp_path / ".ace-gui-install.json").write_text(json.dumps({"conda_python": sys.executable, "prefix": str(prefix)}))
    monkeypatch.setattr(start_gui, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["launcher", "--check", "--project", "Lab project"])
    command = start_gui.registered_command()
    assert command[:3] == [sys.executable, "-m", "conda"]
    assert command[-3:] == ["--check", "--project", "Lab project"]
    monkeypatch.setattr(sys, "prefix", str(prefix))
    assert start_gui.registered_command() is None


@pytest.mark.parametrize("value", ["{broken", "[]", '{"prefix": 3}'])
def test_corrupt_registration_has_actionable_recovery(tmp_path, monkeypatch, value):
    (tmp_path / ".ace-gui-install.json").write_text(value)
    monkeypatch.setattr(start_gui, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="Run setup again"):
        start_gui.registered_command()


@pytest.mark.parametrize("returncode", [0, 1])
def test_windows_stop_terminates_worker_tree_and_does_not_record_false_success(tmp_path, monkeypatch, returncode):
    run_id = "20261013T120000-12345678"
    directory = tmp_path / ".ace-runs" / run_id
    directory.mkdir(parents=True)
    value = dict(
        id=run_id,
        number="1",
        kind="compute",
        label="test",
        state="running",
        started="now",
        finished=None,
        parameters={},
    )
    (directory / "run.json").write_text(json.dumps(value))
    service = Runs()
    service.processes[str(directory)] = SimpleNamespace(pid=12345, poll=lambda: None)
    commands = []
    monkeypatch.setattr(sys, "platform", "win32")

    def taskkill(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=returncode)

    monkeypatch.setattr(subprocess, "run", taskkill)
    project = SimpleNamespace(path=tmp_path)
    if returncode:
        with pytest.raises(ProjectError, match="still active"):
            service.stop(project, run_id)
        assert json.loads((directory / "run.json").read_text())["state"] == "running"
    else:
        assert service.stop(project, run_id)["state"] == "stopped"
    assert commands == [["taskkill", "/PID", "12345", "/T", "/F"]]


@pytest.mark.parametrize("key", ["win-64", "osx-64", "osx-arm64", "linux-64"])
def test_install_specs_are_pinned_native_and_include_gui_dependencies(key):
    specification = yaml.safe_load((Path(setup_gui.ROOT) / "installer" / key / "environment.yml").read_text())
    packages = {item.split("=", 1)[0]: item for item in specification["dependencies"] if isinstance(item, str)}
    assert all(value.count("=") >= 2 for value in packages.values())
    for name in ("caiman", "opencv", "cython", "moviepy", "numpydoc", "yapf"):
        assert name in packages
    assert "qt" in packages["opencv"] and "headless" not in packages["opencv"]
    pip = next(item["pip"] for item in specification["dependencies"] if isinstance(item, dict))
    assert any(item.split("==", 1)[0].strip().lower() == "box-sdk-gen" for item in pip)
