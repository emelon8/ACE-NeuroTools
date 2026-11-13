"""Native dialog cancellation, availability, path validation and safe folder opening."""

import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from aceneurotools.gui.csv_projects import ProjectError
from aceneurotools.gui.native_dialogs import NativeDialogs


@pytest.fixture
def native(monkeypatch):
    monkeypatch.setattr(
        "aceneurotools.gui.native_dialogs.desktop_environment", lambda: {"WAYLAND_DISPLAY": "wayland-test"}
    )
    monkeypatch.setattr(
        "aceneurotools.gui.native_dialogs.shutil.which", lambda name: "/usr/bin/zenity" if name == "zenity" else None
    )
    return NativeDialogs()


class FakeDialog:
    """Stands in for a dialog process: records its command and answers once."""

    def __init__(self, command, calls, code, stdout, stderr, hang):
        self.command, self.returncode, self.stdout, self.stderr, self.hang = command, None, stdout, stderr, hang
        self.code, self.killed = code, False
        calls.append(self)

    def communicate(self, timeout=None):
        if self.hang and not self.killed:
            raise subprocess.TimeoutExpired(self.command, timeout)
        self.returncode = -9 if self.killed else self.code
        return self.stdout, self.stderr

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True


def respond(monkeypatch, stdout="", code=0, stderr="", hang=False):
    calls = []
    monkeypatch.setattr(
        "aceneurotools.gui.native_dialogs.subprocess.Popen",
        lambda command, **kwargs: FakeDialog(command, calls, code, stdout, stderr, hang),
    )
    return calls


@pytest.fixture
def mac(monkeypatch):
    monkeypatch.setattr("aceneurotools.gui.native_dialogs.sys.platform", "darwin")
    monkeypatch.setattr("aceneurotools.gui.native_dialogs.desktop_environment", lambda: {})
    monkeypatch.setattr(
        "aceneurotools.gui.native_dialogs.shutil.which",
        lambda name: "/usr/bin/osascript" if name == "osascript" else None,
    )
    return NativeDialogs()


def test_cancel_and_unavailable_are_distinct(native, monkeypatch):
    respond(monkeypatch, code=1)
    assert native.pick({}) == {"available": True, "paths": []}
    respond(monkeypatch, code=1, stderr="Gtk-WARNING: cannot open display")
    assert native.pick({}) == {"available": False, "paths": []}


def test_estimates_and_multi_movie_selection(native, monkeypatch, tmp_path):
    estimates = tmp_path / "neuron estimates.hdf5"
    estimates.touch()
    respond(monkeypatch, str(estimates) + "\n")
    assert native.pick({"kind": "estimates", "initial": str(tmp_path)})["paths"] == [str(estimates)]
    movies = [tmp_path / "movie one.avi", tmp_path / "movie two.avi"]
    for path in movies:
        path.touch()
    respond(monkeypatch, "\n".join(map(str, movies)) + "\n")
    assert native.pick({"kind": "movies", "initial": str(tmp_path)})["paths"] == list(map(str, movies))
    respond(monkeypatch, str(estimates))
    with pytest.raises(ProjectError, match="AVI"):
        native.pick({"kind": "movies"})


def test_invalid_and_missing_selections_leave_files_untouched(native, monkeypatch, tmp_path):
    for kind in ["command", []]:
        with pytest.raises(ProjectError):
            native.pick({"kind": kind})
    respond(monkeypatch, str(tmp_path / "gone.hdf5"))
    with pytest.raises(ProjectError, match="no longer exists"):
        native.pick({"kind": "estimates"})
    assert list(tmp_path.iterdir()) == []


def test_picker_serializes_dialogs(native):
    with native.lock:
        with pytest.raises(ProjectError, match="already open"):
            native.pick({})


def test_folder_open_uses_literal_path_and_reports_failure(native, monkeypatch, tmp_path):
    folder = tmp_path / "outputs ; untouched"
    folder.mkdir()
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert not kwargs.get("shell")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("aceneurotools.gui.native_dialogs.subprocess.run", run)
    assert native.open_folder(folder)["opened"]
    assert calls == [["xdg-open", str(folder)]]
    monkeypatch.setattr(
        "aceneurotools.gui.native_dialogs.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=1)
    )
    with pytest.raises(ProjectError, match="could not open"):
        native.open_folder(folder)
    with pytest.raises(ProjectError, match="does not exist"):
        native.open_folder(folder / "missing")


def test_no_desktop_falls_back_without_launching_a_process(native, monkeypatch):
    monkeypatch.setattr("aceneurotools.gui.native_dialogs.desktop_environment", lambda: {})
    monkeypatch.setattr(
        "aceneurotools.gui.native_dialogs.subprocess.run",
        lambda *args, **kwargs: pytest.fail("No display: should not launch a dialog"),
    )
    assert native.pick({}) == {"available": False, "paths": []}


def test_mac_uses_frontmost_system_chooser_with_literal_arguments(mac, monkeypatch, tmp_path):
    folder = tmp_path / 'project ; "quoted"'
    folder.mkdir()
    calls = respond(monkeypatch, str(folder) + "/\n")
    assert mac.pick({"kind": "folder", "initial": str(folder)}) == {"available": True, "paths": [str(folder)]}
    command = calls[0].command
    assert command[:2] == ["/usr/bin/osascript", "-e"]
    assert "activate" in command[2] and str(folder) not in command[2]
    assert command[3:] == ["Choose a folder", str(folder), "folder"]


def test_mac_multi_movie_selection(mac, monkeypatch, tmp_path):
    movies = [tmp_path / "movie one.avi", tmp_path / "movie two.avi"]
    for path in movies:
        path.touch()
    calls = respond(monkeypatch, "\n".join(map(str, movies)) + "\n")
    assert mac.pick({"kind": "movies", "initial": str(tmp_path)})["paths"] == list(map(str, movies))
    assert calls[0].command[-1] == "movies"


def test_mac_cancel_differs_from_script_failure(mac, monkeypatch):
    respond(monkeypatch, code=1, stderr="execution error: User canceled. (-128)")
    assert mac.pick({}) == {"available": True, "paths": []}
    respond(monkeypatch, code=1, stderr="execution error: Can't get POSIX file. (-1728)")
    assert mac.pick({}) == {"available": False, "paths": []}


def test_mac_without_osascript_falls_back_to_tk(mac, monkeypatch, tmp_path):
    monkeypatch.setattr("aceneurotools.gui.native_dialogs.shutil.which", lambda name: None)
    calls = respond(monkeypatch, f'["{tmp_path}"]')
    assert mac.pick({"initial": str(tmp_path)})["paths"] == [str(tmp_path)]
    assert calls[0].command[:2] == [sys.executable, "-c"]


def test_hung_picker_is_killed_and_reported_unavailable(native, monkeypatch):
    calls = respond(monkeypatch, hang=True)
    assert native.pick({}) == {"available": False, "paths": []}
    assert calls[0].killed
    assert native.process is None
    assert not native.lock.locked()


def test_dismiss_closes_an_open_picker(native):
    assert native.dismiss() == {"dismissed": False}
    result = {}
    worker = threading.Thread(
        target=lambda: result.update(run=native._run([sys.executable, "-c", "import time; time.sleep(30)"], None))
    )
    worker.start()
    deadline = time.monotonic() + 10
    while native.process is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert native.dismiss() == {"dismissed": True}
    worker.join(10)
    assert not worker.is_alive()
    assert result["run"][0] != 0
    assert native.process is None
    assert native.dismiss() == {"dismissed": False}
