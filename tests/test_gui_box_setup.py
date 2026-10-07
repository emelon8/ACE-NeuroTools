"""Verify the wrapper's authentication, access checks, and credential lifecycle."""

import json
import stat
from types import SimpleNamespace as NS

import pytest
from gui.box_setup import BoxSetup, BoxSetupError, folder_id, make_client


class BoxFailure(Exception):
    def __init__(self, status):
        super().__init__("secret-token and client_secret must never reach the browser")
        self.response_info = NS(status_code=status, code="denied")


class FakeBox:
    def __init__(self):
        self.users = self
        self.folders = self
        self.calls = []
        self.fail_account = None
        self.fail_folder = None

    def get_user_me(self, **kwargs):
        if self.fail_account:
            raise BoxFailure(self.fail_account)
        return NS(id="8", name="Researcher", login="lab@example.test")

    def get_folder_by_id(self, number, **kwargs):
        self.calls.append(("folder", number))
        if self.fail_folder:
            raise BoxFailure(self.fail_folder)
        return NS(id=number, name="Recordings", path_collection=NS(entries=[NS(id="0", name="All files")]))

    def get_folder_items(self, number, **kwargs):
        self.calls.append(("items", number, kwargs))
        return NS(
            entries=[NS(id="12", name="Session", type="folder")], next_marker="page2" if not kwargs["marker"] else None
        )


@pytest.fixture
def setup(tmp_path):
    client = FakeBox()
    service = BoxSetup(tmp_path / "settings", client_factory=lambda _: client)
    credentials = {
        "method": "ccg",
        "client_id": "client",
        "client_secret": "secret-ccg-unique-xyz",
        "subject_type": "user",
        "subject_id": "8",
    }
    return service, client, credentials, tmp_path


def finish(service, credentials, path, **options):
    proof = service.check(credentials)["proof"]
    return service.finish({"proof": proof, "folder": "12", "download_path": str(path), **options})


def test_folder_links_and_exact_ids():
    assert folder_id("00123456789012345678") == "00123456789012345678"
    assert folder_id("https://lab.app.box.com/folder/123?view=list") == "123"
    for value in ["https://evil.app.box.com.evil/folder/123", "https://app.box.com/s/shared", "NaN", 123]:
        with pytest.raises(BoxSetupError):
            folder_id(value)


def test_check_verifies_account_without_activating_or_persisting(setup):
    service, client, credentials, path = setup
    checked = service.check(credentials)
    assert checked["account"]["login"] == "lab@example.test"
    assert not service.status()["connected"]
    assert not service.config_path.exists()
    client.fail_account = 401
    with pytest.raises(BoxSetupError, match="rejected or expired") as error:
        service.check(credentials)
    assert "secret" not in str(error.value)


def test_pagination_and_permission_failure_are_real_checks(setup):
    service, client, credentials, path = setup
    proof = service.check(credentials)["proof"]
    first = service.folders({"proof": proof, "folder": "12"})
    assert first["next_marker"] == "page2"
    second = service.folders({"proof": proof, "folder": "12", "marker": first["next_marker"]})
    assert second["next_marker"] is None
    assert client.calls[-1][2]["usemarker"] is True
    client.fail_folder = 404
    with pytest.raises(BoxSetupError, match="share the folder") as error:
        service.folders({"proof": proof, "folder": "404"})
    assert "secret" not in str(error.value)


def test_finish_stores_private_ccg_outside_project_and_reconnects(setup):
    service, client, credentials, path = setup
    status = finish(service, credentials, path, remember=True)
    assert status["connected"] and status["saved"]
    assert "credentials" not in status and "secret-ccg-unique-xyz" not in json.dumps(status)
    assert stat.S_IMODE(service.config_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(service.config_path.parent.stat().st_mode) == 0o700
    assert json.loads(service.config_path.read_text())["credentials"] == credentials
    fresh = BoxSetup(service.config_path.parent, client_factory=lambda _: client)
    assert not fresh.status()["connected"]
    checked = fresh.check({"use_saved": True})
    assert checked["folder_id"] == "12" and checked["download_path"] == str(path)
    assert "secret-ccg-unique-xyz" not in json.dumps(checked)
    fresh.finish({"proof": checked["proof"], "folder": "12", "download_path": str(path)})
    assert fresh.status()["connected"]


def test_token_is_never_written_and_proof_is_consumed(setup):
    service, client, credentials, path = setup
    credentials = {"method": "token", "token": "private-token"}
    proof = service.check(credentials)["proof"]
    body = {"proof": proof, "folder": "12", "download_path": str(path), "remember": True}
    with pytest.raises(BoxSetupError, match="session only"):
        service.finish(body)
    body["remember"] = False
    assert service.finish(body)["connected"]
    assert not service.config_path.exists()
    with pytest.raises(BoxSetupError, match="expired"):
        service.finish(body)


def test_failed_new_setup_preserves_active_and_saved_connection(setup):
    service, client, credentials, path = setup
    finish(service, credentials, path, remember=True)
    original = service.config_path.read_bytes()
    proof = service.check(credentials)["proof"]
    client.fail_folder = 403
    with pytest.raises(BoxSetupError, match="administrator approval"):
        service.finish({"proof": proof, "folder": "12", "download_path": str(path), "remember": True})
    assert service.status()["connected"]
    assert service.config_path.read_bytes() == original


def test_invalid_download_path_and_expired_proof(setup):
    service, client, credentials, path = setup
    proof = service.check(credentials)["proof"]
    with pytest.raises(BoxSetupError, match="does not exist"):
        service.finish({"proof": proof, "folder": "12", "download_path": str(path / "absent")})
    assert not service.status()["connected"]
    service.pending[proof]["time"] -= 1801
    with pytest.raises(BoxSetupError, match="expired"):
        service.folders({"proof": proof})


def test_failed_settings_write_does_not_activate(setup, monkeypatch):
    service, client, credentials, path = setup

    def fail(*args):
        raise BoxSetupError("Could not save")

    monkeypatch.setattr(service, "_write", fail)
    with pytest.raises(BoxSetupError):
        finish(service, credentials, path, remember=True)
    assert not service.status()["connected"]


def test_disconnect_and_forget(setup):
    service, client, credentials, path = setup
    finish(service, credentials, path, remember=True)
    assert not service.disconnect({})["connected"]
    assert service.config_path.exists()
    service.disconnect({"forget": True})
    assert not service.config_path.exists()


def test_actual_sdk_constructs_both_auth_modes_without_network():
    pytest.importorskip("box_sdk_gen")
    for credentials in [
        {"method": "token", "token": "unused"},
        {"method": "ccg", "client_id": "unused", "client_secret": "unused", "subject_type": "user", "subject_id": "8"},
        {
            "method": "ccg",
            "client_id": "unused",
            "client_secret": "unused",
            "subject_type": "enterprise",
            "subject_id": "8",
        },
    ]:
        assert make_client(credentials).users is not None


def test_lab_setup_is_remembered_by_default_and_reused_globally(setup):
    service, client, credentials, path = setup
    finish(service, credentials, path)
    assert service.status()["saved"], "Lab setup must persist without a per-experiment opt-in"
    fresh = BoxSetup(service.config_path.parent, client_factory=lambda _: client)
    assert fresh.status()["download_path"] == str(path)
    assert fresh.ensure_connection()["client"] is client
    assert fresh.ensure_connection()["client"] is client
    assert fresh.status()["connected"]


def test_global_setup_does_not_require_a_recording_folder(setup):
    service, client, credentials, path = setup
    proof = service.check(credentials)["proof"]
    result = service.finish({"proof": proof, "download_path": str(path)})
    assert result["connected"] and result["saved"]
    assert not client.calls, "Global authentication must not require experiment folder access"


def test_global_download_location_updates_survive_restart(setup):
    service, client, credentials, path = setup
    finish(service, credentials, path)
    new_path = path / "data"
    new_path.mkdir()
    service.location({"download_path": str(new_path)})
    fresh = BoxSetup(service.config_path.parent, client_factory=lambda _: client)
    assert fresh.ensure_connection()["download_path"] == str(new_path)
    service.disconnect({})
    with pytest.raises(BoxSetupError, match="disconnected"):
        service.ensure_connection()
    assert service.connect({})["connected"]
