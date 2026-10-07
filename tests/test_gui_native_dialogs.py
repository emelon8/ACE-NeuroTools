"""Native dialog cancellation, availability, path validation and safe folder opening."""

from types import SimpleNamespace

import pytest
from gui.csv_projects import ProjectError
from gui.native_dialogs import NativeDialogs


@pytest.fixture
def native(monkeypatch):
    monkeypatch.setattr("gui.native_dialogs.desktop_environment", lambda: {"WAYLAND_DISPLAY": "wayland-test"})
    monkeypatch.setattr("gui.native_dialogs.shutil.which", lambda name: "/usr/bin/zenity" if name == "zenity" else None)
    return NativeDialogs()


def respond(monkeypatch, stdout="", code=0, stderr=""):
    monkeypatch.setattr(
        "gui.native_dialogs.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr),
    )


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

    monkeypatch.setattr("gui.native_dialogs.subprocess.run", run)
    assert native.open_folder(folder)["opened"]
    assert calls == [["xdg-open", str(folder)]]
    respond(monkeypatch, code=1)
    with pytest.raises(ProjectError, match="could not open"):
        native.open_folder(folder)
    with pytest.raises(ProjectError, match="does not exist"):
        native.open_folder(folder / "missing")


def test_no_desktop_falls_back_without_launching_a_process(native, monkeypatch):
    monkeypatch.setattr("gui.native_dialogs.desktop_environment", lambda: {})
    monkeypatch.setattr(
        "gui.native_dialogs.subprocess.run",
        lambda *args, **kwargs: pytest.fail("No display: should not launch a dialog"),
    )
    assert native.pick({}) == {"available": False, "paths": []}
