"""Launcher reuses only ACE and creates a usable, user-local desktop entry."""

import io
import json
from urllib.error import URLError

from scripts import start_gui
from scripts.install_gui_shortcut import install


def test_health_identifies_only_the_ace_server(monkeypatch):
    monkeypatch.setattr(
        start_gui, "urlopen", lambda *a, **k: io.BytesIO(json.dumps({"application": "ACE Experiments"}).encode())
    )
    assert start_gui.running(8780)
    monkeypatch.setattr(start_gui, "urlopen", lambda *a, **k: io.BytesIO(b'{"application":"other"}'))
    assert not start_gui.running(8780)

    def unavailable(*args, **kwargs):
        raise URLError("not running")

    monkeypatch.setattr(start_gui, "urlopen", unavailable)
    assert not start_gui.running(8780)


def test_reopen_does_not_start_a_second_server(monkeypatch):
    opened = []
    monkeypatch.setattr(start_gui.sys, "argv", ["start_gui"])
    monkeypatch.setattr(start_gui, "running", lambda _: True)
    monkeypatch.setattr(start_gui.webbrowser, "open", opened.append)
    monkeypatch.setattr(
        start_gui, "find_python", lambda: (_ for _ in ()).throw(AssertionError("must reuse existing server"))
    )
    assert start_gui.main() == 0 and opened == ["http://127.0.0.1:8780/"]


def test_desktop_shortcut_handles_a_checkout_with_spaces(tmp_path):
    root = tmp_path / "Research tools"
    desktop = install(root, tmp_path / "applications")
    text = desktop.read_text()
    assert f'Exec="{root}/launch-gui"' in text
    assert "Name=ACE Experiments" in text and "Terminal=false" in text
    assert desktop.stat().st_mode & 0o111
