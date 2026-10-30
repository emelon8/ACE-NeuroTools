"""GUI-owned Box authentication; no credential modules or scientific code changes."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit


class BoxSetupError(ValueError):
    """An actionable message safe to return to the browser."""


def folder_id(value):
    if not isinstance(value, str):
        raise BoxSetupError("Choose a Box folder or paste its folder link.")
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        return value
    link = urlsplit(value)
    if link.scheme == "https" and (link.hostname == "app.box.com" or (link.hostname or "").endswith(".app.box.com")):
        match = re.fullmatch(r"/folder/([0-9]+)/?", link.path)
        if match:
            return match[1]
    raise BoxSetupError(
        "Use a Box folder ID or a link like https://app.box.com/folder/123. Shared-file links are not folder links."
    )


def credentials_from(body):
    if not isinstance(body, dict):
        raise BoxSetupError("Enter your Box connection details.")
    method = body.get("method")
    keys = ["token"] if method == "token" else ["client_id", "client_secret", "subject_id"]
    if not isinstance(method, str) or method not in {"ccg", "token"}:
        raise BoxSetupError("Choose a lab connection or a temporary developer token.")
    values = {key: body.get(key, "") for key in keys}
    if any(not isinstance(value, str) or not value.strip() for value in values.values()):
        raise BoxSetupError("Complete all connection fields before checking Box.")
    result = {"method": method, **{key: value.strip() for key, value in values.items()}}
    if method == "ccg":
        if not isinstance(body.get("subject_type"), str) or body["subject_type"] not in {"user", "enterprise"}:
            raise BoxSetupError("Choose a Box user or the app's service account.")
        if not re.fullmatch(r"[0-9]+", result["subject_id"]):
            raise BoxSetupError("The Box user or enterprise ID must contain digits only.")
        result["subject_type"] = body["subject_type"]
    return result


def make_client(credentials):
    try:
        import requests
        from box_sdk_gen import BoxCCGAuth, BoxClient, BoxDeveloperTokenAuth, CCGConfig, NetworkSession
        from box_sdk_gen.networking.box_network_client import BoxNetworkClient
        from box_sdk_gen.networking.retries import BoxRetryStrategy
    except ImportError:
        raise BoxSetupError(
            "Box support is missing from this Python environment. Launch the GUI in your ACE analysis environment with box-sdk-gen installed."
        ) from None

    class BoundedSession(requests.Session):
        def request(self, *args, **kwargs):
            kwargs["timeout"] = (5, 20)
            return super().request(*args, **kwargs)

    session = NetworkSession(
        network_client=BoxNetworkClient(BoundedSession()),
        retry_strategy=BoxRetryStrategy(max_attempts=1, max_retries_on_exception=0),
    )
    if credentials["method"] == "token":
        auth = BoxDeveloperTokenAuth(credentials["token"])
    else:
        config = CCGConfig(
            credentials["client_id"],
            credentials["client_secret"],
            **{f"{credentials['subject_type']}_id": credentials["subject_id"]},
        )
        auth = BoxCCGAuth(config)
    return BoxClient(auth, network_session=session)


def safe_failure(exc):
    # SDK error text may contain the token request. Never forward it or log it.
    info = getattr(exc, "response_info", None)
    status = getattr(info, "status_code", None)
    code = getattr(info, "code", None)
    if status == 404:
        return "Box cannot find this folder for the connected account. Check the link and share the folder with this account."
    if status == 401:
        return "Box rejected or expired this access. Replace the token or check the lab app credentials and try again."
    if status in {400, 403} or code == "invalid_grant":
        return "Box denied access. Check the app credentials, account ID, administrator approval, and app permissions. Managed users need App + Enterprise Access and Generate User Access Tokens."
    if status == 429:
        return "Box is limiting requests. Wait a moment, then try again."
    return "Could not reach or verify Box. Check your internet connection and Box app configuration, then try again."


class BoxSetup:
    def __init__(self, settings_directory=None, client_factory=make_client):
        root = (
            Path(settings_directory)
            if settings_directory
            else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "aceneurotools" / "gui"
        )
        self.config_path = root / "box.json"
        self.factory = client_factory
        self.lock = threading.RLock()
        self.pending = {}
        self.active = None
        self.auto_reconnect = True

    def _saved(self):
        try:
            data = json.loads(self.config_path.read_text())
            credentials = credentials_from(data["credentials"])
            if credentials["method"] != "ccg":
                raise ValueError()
            return {**data, "credentials": credentials}
        except FileNotFoundError:
            raise BoxSetupError("No saved Box connection. Enter your connection details first.") from None
        except (OSError, ValueError, KeyError, TypeError):
            raise BoxSetupError(
                "The saved Box connection could not be read. Re-enter your connection details and save again."
            ) from None

    def status(self):
        with self.lock:
            saved = self.config_path.exists()
            return {
                "sdk_available": importlib.util.find_spec("box_sdk_gen") is not None,
                "saved": saved,
                "auto_reconnect": self.auto_reconnect,
                "connected": self.active is not None,
                **(
                    {key: self.active[key] for key in ["account", "folder", "download_path"]}
                    if self.active
                    else self._saved_status()
                ),
            }

    def _saved_status(self):
        if not self.config_path.exists():
            return {}
        try:
            saved = self._saved()
            return {"download_path": saved.get("download_path", ""), "account": saved.get("account")}
        except BoxSetupError:
            return {}

    def ensure_connection(self):
        """Reuse one verified connection across all projects, including after restart."""
        with self.lock:
            if self.active:
                return self.active
            if not self.auto_reconnect:
                raise BoxSetupError("Box is disconnected. Use the saved connection in Box settings to reconnect.")
            saved = self._saved()
            checked = self.check({"use_saved": True})
            candidate = self._candidate(checked["proof"])
            self.active = {
                **candidate,
                "folder": {"id": saved.get("folder_id", "0"), "name": "All files"},
                "download_path": saved.get("download_path", ""),
            }
            self.pending.pop(checked["proof"], None)
            return self.active

    def connect(self, body):
        with self.lock:
            self.auto_reconnect = True
            self.ensure_connection()
            return self.status()

    def location(self, body):
        with self.lock:
            active = self.ensure_connection()
            path = self._download_path(body.get("download_path"))
            if self.config_path.exists() and active["credentials"]["method"] == "ccg":
                self._write(
                    {
                        "credentials": active["credentials"],
                        "folder_id": active["folder"]["id"],
                        "download_path": str(path),
                        "account": active["account"],
                    }
                )
            self.active = {**active, "download_path": str(path)}
            return self.status()

    @staticmethod
    def _download_path(value):
        if not isinstance(value, str) or not value.strip():
            raise BoxSetupError("Choose a local folder for recording downloads.")
        path = Path(value).expanduser().resolve()
        if not path.is_dir():
            raise BoxSetupError("The download folder does not exist. Choose an existing local folder.")
        try:
            with tempfile.TemporaryFile(dir=path):
                pass
        except OSError:
            raise BoxSetupError("The download folder is not writable. Choose another local folder.") from None
        return path

    def check(self, body):
        saved = self._saved() if body.get("use_saved") is True else None
        credentials = saved["credentials"] if saved else credentials_from(body)
        try:
            client = self.factory(credentials)
            account = client.users.get_user_me(fields=["id", "name", "login"])
        except BoxSetupError:
            raise
        except Exception as exc:
            raise BoxSetupError(safe_failure(exc)) from None
        proof = uuid.uuid4().hex
        candidate = {
            "client": client,
            "credentials": credentials,
            "time": time.monotonic(),
            "account": {"id": account.id, "name": account.name, "login": account.login},
        }
        with self.lock:
            self.pending = {
                key: value for key, value in self.pending.items() if time.monotonic() - value["time"] < 1800
            }
            if len(self.pending) >= 8:
                self.pending.pop(next(iter(self.pending)))
            self.pending[proof] = candidate
        return {
            "proof": proof,
            "account": candidate["account"],
            "method": credentials["method"],
            "folder_id": saved.get("folder_id", "0") if saved else "0",
            "download_path": saved.get("download_path", "") if saved else "",
        }

    def _candidate(self, proof):
        with self.lock:
            candidate = self.pending.get(proof) if isinstance(proof, str) else None
            if not candidate or time.monotonic() - candidate["time"] >= 1800:
                raise BoxSetupError("Check your Box connection again before continuing; the setup check has expired.")
            return candidate

    def folders(self, body):
        candidate = self._candidate(body.get("proof")) if body.get("proof") else self.ensure_connection()
        number = folder_id(body.get("folder", "0"))
        marker = body.get("marker")
        if marker is not None and not isinstance(marker, str):
            raise BoxSetupError("Invalid Box folder page. Open the folder again.")
        try:
            client = candidate["client"]
            folder = client.folders.get_folder_by_id(number, fields=["id", "name", "path_collection"])
            listing = client.folders.get_folder_items(
                number, fields=["id", "name", "type"], usemarker=True, marker=marker, limit=100
            )
            crumbs = getattr(getattr(folder, "path_collection", None), "entries", []) or []
            return {
                "id": folder.id,
                "name": folder.name,
                "breadcrumbs": [{"id": item.id, "name": item.name} for item in crumbs],
                "entries": [
                    {"id": item.id, "name": item.name, "type": str(getattr(item.type, "value", item.type))}
                    for item in listing.entries
                ],
                "next_marker": listing.next_marker,
            }
        except Exception as exc:
            raise BoxSetupError(safe_failure(exc)) from None

    def finish(self, body):
        candidate = self._candidate(body.get("proof"))
        number = folder_id(body.get("folder", "0"))
        remember = body.get("remember", candidate["credentials"]["method"] == "ccg")
        if not isinstance(remember, bool):
            raise BoxSetupError("Choose whether to remember this connection.")
        if remember and candidate["credentials"]["method"] == "token":
            raise BoxSetupError("Temporary developer tokens are used for this session only.")
        path = self._download_path(body.get("download_path"))
        selected = {"id": "0", "name": "All files"}
        if number != "0":
            try:
                folder = candidate["client"].folders.get_folder_by_id(number, fields=["id", "name"])
                selected = {"id": folder.id, "name": folder.name}
            except Exception as exc:
                raise BoxSetupError(safe_failure(exc)) from None
        active = {**candidate, "folder": selected, "download_path": str(path)}
        with self.lock:
            if remember:
                self._write(
                    {
                        "credentials": candidate["credentials"],
                        "folder_id": number,
                        "download_path": str(path),
                        "account": candidate["account"],
                    }
                )
            # A session-only replacement must not resurrect old saved credentials.
            if not remember:
                self.config_path.unlink(missing_ok=True)
            self.auto_reconnect = True
            self.active = active
            self.pending.pop(body["proof"], None)
        return self.status()

    def _write(self, data):
        temp = None
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temp = tempfile.mkstemp(prefix=".box-", dir=self.config_path.parent)
            with os.fdopen(fd, "w") as handle:
                json.dump(data, handle)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temp, 0o600)
            os.replace(temp, self.config_path)
        except OSError:
            raise BoxSetupError(
                "Could not save the Box connection in your user settings. Try session-only access or check folder permissions."
            ) from None
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)

    def disconnect(self, body):
        with self.lock:
            if body.get("forget") is True:
                try:
                    self.config_path.unlink(missing_ok=True)
                except OSError:
                    raise BoxSetupError(
                        "Could not remove the saved Box connection. Check your user settings permissions."
                    ) from None
            self.active = None
            self.auto_reconnect = False
            self.pending.clear()
        return self.status()
