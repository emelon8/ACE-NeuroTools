"""Prepare Box-linked recordings for unchanged crop and analysis APIs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace

from gui.box_setup import BoxSetupError, folder_id, safe_failure
from gui.csv_projects import ProjectError
from gui.runs import inventory


class DownloadCancelled(Exception):
    """Cooperative cancellation, including an in-progress streamed file."""


def matches(path, item, check=lambda: None):
    if not path.is_file() or path.is_symlink() or path.stat().st_size != item["size"]:
        return False
    if item.get("mtime_ns") == path.stat().st_mtime_ns:
        return True
    if item.get("sha1"):
        digest = hashlib.sha1()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                check()
                digest.update(chunk)
        return digest.hexdigest() == item["sha1"]
    return True


def safe_target(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ProjectError("The recording contains a link outside its folder. Choose another local location.")
    for part in [path, *path.parents]:
        if part == root.parent:
            break
        if part.is_symlink():
            raise ProjectError("Recording downloads cannot replace symbolic links. Choose another local location.")
    return path


class Recordings:
    def __init__(self, box):
        self.box = box
        self.lock = threading.RLock()
        self.jobs = {}
        self.plans = {}
        self.cancellations = {}

    def status(self, project, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job["project"] != project.id:
                raise ProjectError("This recording download is unavailable. Try loading the recording again.")
            return dict(job)

    def _context(self, project, body):
        detail = project.inspect(body["number"])
        if detail["versions"] != body.get("versions"):
            raise ProjectError("Save or reload your experiment before loading its recording.")
        ephys = body.get("kind") == "ephys"
        column = "ephys directory" if ephys else "calcium imaging directory"
        box_column = "Box ephys folder ID" if ephys else "Box Calcium Folder ID"
        label = "Electrophysiology Box folder ID" if ephys else "Calcium Box folder ID"
        value = detail["metadata"].get(column, "").strip()
        if not value or ";" in value:
            raise ProjectError(f"Set one {column} in Data & settings before loading the recording.")
        if PureWindowsPath(value).is_absolute() and not Path(value).is_absolute():
            raise ProjectError(f"The {column} uses a Windows path. Choose its local location in Data & settings.")
        explicit = body.get("data_path")
        if explicit is not None and (not isinstance(explicit, str) or not explicit.strip()):
            raise ProjectError("Choose a local data folder.")
        state = self.box.status()
        # Keep already-local projects working; otherwise use the global download base.
        project_local = Path(project.path) / value
        base = (
            Path(
                explicit
                or (str(project.path) if project_local.is_dir() else state.get("download_path") or str(project.path))
            )
            .expanduser()
            .resolve()
        )
        target = (base / value).resolve()
        if target == Path(target.anchor) or target == Path(project.path).resolve():
            raise ProjectError("Choose a dedicated recording folder, separate from the project CSV folder.")
        local = target.is_dir() and any(
            item["path"].lower().endswith(".avi")
            if not ephys
            else Path(item["path"]).suffix.lower() in {".ncs", ".rhs", ".rhd", ".dat", ".bin", ".raw"}
            for item in inventory(target)
        )
        number = detail["metadata"].get(box_column, "").strip()
        result = {
            "project": project.id,
            "number": body["number"],
            "data_path": str(base),
            "recording_path": str(target),
        }
        return detail, target, number, local, result, label

    def _receipt(self, target, number):
        try:
            saved = json.loads((target / ".ace-box.json").read_text())
            if not isinstance(saved, dict):
                return {}
            if saved.get("folder_id") and saved["folder_id"] != number:
                raise ProjectError(
                    "This local recording folder belongs to another Box folder. Choose a separate recording directory in Data & settings before downloading."
                )
            return saved
        except (OSError, json.JSONDecodeError):
            return {}

    def _existing_job(self, project, body, target):
        with self.lock:
            for job in self.jobs.values():
                if job["recording_path"] == str(target) and job["state"] in {
                    "queued",
                    "downloading",
                    "cancelling",
                    "finalizing",
                }:
                    if job["project"] == project.id and job["number"] == body["number"]:
                        return dict(job)
                    raise ProjectError("Another experiment is downloading to this folder. Wait for it to finish.")
        return None

    def prepare(self, project, body):
        detail, target, number, local, result, label = self._context(project, body)
        active = self._existing_job(project, body, target)
        if active:
            return active
        state = self.box.status()
        if local and (not number or not (state["connected"] or state["saved"])):
            return {**result, "state": "ready"}
        if not number:
            raise ProjectError(
                f"Recording files are missing. Set the {label} in Data & settings, or choose the existing local recording folder. Your global Box connection does not need to be entered again."
            )
        number = folder_id(number)
        saved = self._receipt(target, number)
        selected = saved.get("selection") or [item["path"] for item in saved.get("files", [])]
        by_path = {item["path"]: item for item in saved.get("files", [])}
        if selected and all(path in by_path and matches(safe_target(target, path), by_path[path]) for path in selected):
            return {**result, "state": "ready", "subset": not saved.get("complete", True), "selected_files": selected}
        return self.plan(project, body)

    def plan(self, project, body):
        """List and estimate; never transfer recording bytes before confirmation."""
        detail, target, number, local, result, label = self._context(project, body)
        if not number:
            raise ProjectError(f"Set the {label} in Data & settings to choose files from Box.")
        number = folder_id(number)
        saved = self._receipt(target, number)
        client = self.box.ensure_connection()["client"]
        try:
            files = self._manifest(client, number)
        except ProjectError:
            raise
        except Exception as exc:
            raise BoxSetupError(safe_failure(exc)) from None
        # Matching prior receipt entries avoids hashing large unchanged local files again.
        previous = {item["path"]: item for item in saved.get("files", [])}
        for item in files:
            old = previous.get(item["path"], {})
            recorded = (
                old
                if old.get("id") == item["id"]
                and old.get("size") == item["size"]
                and old.get("sha1") == item.get("sha1")
                else item
            )
            item["local"] = matches(safe_target(target, item["path"]), recorded)
        parent = target.parent
        while not parent.exists():
            parent = parent.parent
        free = shutil.disk_usage(parent).free
        proof = uuid.uuid4().hex
        value = {
            **result,
            "state": "selection_required",
            "plan": proof,
            "files": files,
            "total_bytes": sum(item["size"] for item in files),
            "free_bytes": free,
            "previous_selection": saved.get("selection", []),
            "folder_id": number,
        }
        with self.lock:
            self.plans = {key: item for key, item in self.plans.items() if time.monotonic() - item["time"] < 1800}
            if len(self.plans) >= 32:
                self.plans.pop(next(iter(self.plans)))
            self.plans[proof] = {"value": value, "versions": detail["versions"], "time": time.monotonic()}
        return value

    def start(self, project, body):
        if body.get("confirmed") is not True:
            raise ProjectError("Review the selected files and confirm the download first.")
        with self.lock:
            plan = self.plans.get(body.get("plan")) if isinstance(body.get("plan"), str) else None
            if not plan or time.monotonic() - plan["time"] >= 1800:
                raise ProjectError("The file list expired. Review the recording download again.")
            value = plan["value"]
            if value["project"] != project.id or value["number"] != body.get("number"):
                raise ProjectError("Review files for this experiment first.")
            project.ensure_current()
            if body.get("versions") != plan["versions"] or project.digests != plan["versions"]:
                raise ProjectError("Experiment settings changed. Review the download again.")
            selection = body.get("files")
            available = {item["path"]: item for item in value["files"]}
            if (
                not isinstance(selection, list)
                or not selection
                or len(selection) > len(available)
                or any(not isinstance(path, str) or path not in available for path in selection)
                or len(set(selection)) != len(selection)
            ):
                raise ProjectError("Select one or more files from the recording list.")
            target = Path(value["recording_path"])
            active = self._existing_job(project, body, target)
            if active:
                raise ProjectError(
                    "A download is already active for this recording. Cancel it or wait for it to finish."
                )
            files = [available[path] for path in selection]
            job = {key: value[key] for key in ["project", "number", "data_path", "recording_path"]}
            job.update(
                id=uuid.uuid4().hex,
                state="queued",
                bytes=0,
                total_bytes=sum(item["size"] for item in files if not item["local"]),
                files_done=0,
                total_files=sum(not item["local"] for item in files),
                message="Preparing selected files…",
                selected_files=selection,
                subset=len(selection) < len(available),
            )
            if len(self.jobs) >= 100:
                for key in list(self.jobs):
                    if self.jobs[key]["state"] in {"ready", "cancelled", "failed"}:
                        self.jobs.pop(key)
                        self.cancellations.pop(key, None)
                        break
            self.jobs[job["id"]] = job
            self.cancellations[job["id"]] = threading.Event()
            self.plans.pop(body["plan"])
            threading.Thread(target=self._download, args=(job, target, value["folder_id"], files), daemon=True).start()
            return dict(job)

    def cancel(self, project, body):
        with self.lock:
            job = self.status(project, body.get("job"))
            if job["number"] != body.get("number"):
                raise ProjectError("Choose the experiment owning this download.")
            if job["state"] in {"queued", "downloading", "cancelling"}:
                self.cancellations[job["id"]].set()
                self.jobs[job["id"]].update(
                    state="cancelling", message="Cancelling download and removing temporary files…"
                )
            return self.status(project, job["id"])

    def _check_cancel(self, job):
        if self.cancellations[job["id"]].is_set():
            raise DownloadCancelled("Download cancelled.")

    def _update(self, job, **values):
        with self.lock:
            if job["state"] == "cancelling" and values.get("state") == "downloading":
                return
            job.update(values)

    def _manifest(self, client, number, check=lambda: None):
        files, visited, names = [], set(), set()
        todo = [(number, Path())]
        while todo:
            check()
            folder, prefix = todo.pop()
            if folder in visited or len(visited) > 10000:
                raise ProjectError("Box folder structure repeats or is too large to download safely.")
            visited.add(folder)
            marker, markers = None, set()
            while True:
                check()
                page = client.folders.get_folder_items(
                    folder, fields=["id", "name", "type", "size", "sha1"], usemarker=True, marker=marker, limit=1000
                )
                for item in page.entries:
                    name = item.name
                    if (
                        not isinstance(name, str)
                        or name in {"", ".", ".."}
                        or name.startswith(".ace-")
                        or any(char in name for char in ["/", "\\", "\x00"])
                    ):
                        raise ProjectError("Box contains an unsafe file or folder name. No files were downloaded.")
                    relative = prefix / name
                    if str(relative).casefold() in names:
                        raise ProjectError("Box contains duplicate file names. No files were downloaded.")
                    names.add(str(relative).casefold())
                    kind = str(getattr(item.type, "value", item.type))
                    if kind == "folder":
                        todo.append((item.id, relative))
                    elif kind == "file":
                        size = getattr(item, "size", None)
                        if not isinstance(size, int) or size < 0:
                            raise ProjectError("Box did not provide file sizes. Try loading the recording again.")
                        files.append(
                            {"id": item.id, "path": str(relative), "size": size, "sha1": getattr(item, "sha1", None)}
                        )
                    else:
                        raise ProjectError(
                            "Box contains a web link instead of recording data. Choose a recording folder."
                        )
                    if len(names) > 100000:
                        raise ProjectError("This Box folder has too many items. Choose the specific recording folder.")
                marker = page.next_marker
                if not marker:
                    break
                if marker in markers:
                    raise ProjectError("Box repeated a folder page. Try loading the recording again.")
                markers.add(marker)
        if not files:
            raise ProjectError("This Box folder has no recording files. Check the experiment's Box folder ID.")
        return files

    def _download(self, job, target, number, files):
        try:

            def check():
                self._check_cancel(job)

            check()
            active = self.box.ensure_connection()
            client = active["client"]
            check()
            self._update(job, state="downloading", message="Checking selected recording files…")
            missing = [item for item in files if not matches(safe_target(target, item["path"]), item, check)]
            total = sum(item["size"] for item in missing)
            self._update(job, total_bytes=total, total_files=len(missing))
            target.parent.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(target.parent).free < total + 1024 * 1024:
                raise ProjectError(
                    "There is not enough disk space for this recording. Choose another local download folder in Box settings."
                )
            with tempfile.TemporaryDirectory(prefix=".ace-box-download-", dir=target.parent) as temporary:
                stage = Path(temporary)
                for item in missing:
                    (stage / item["path"]).parent.mkdir(parents=True, exist_ok=True)
                service = self
                transfer_errors = []

                class ProgressStream:
                    def __init__(self, stream):
                        self.stream = stream

                    def write(self, chunk):
                        service._check_cancel(job)
                        written = self.stream.write(chunk)
                        with service.lock:
                            job["bytes"] += written
                        return written

                    def __getattr__(self, name):
                        return getattr(self.stream, name)

                class Transfers:
                    def download_file_to_output_stream(self, file_id, output_stream):
                        item = next(item for item in missing if item["id"] == file_id)
                        service._update(job, message=f"Downloading {item['path']}…")
                        try:
                            client.downloads.download_file_to_output_stream(
                                file_id, output_stream=ProgressStream(output_stream)
                            )
                        except DownloadCancelled:
                            raise
                        except Exception as exc:
                            transfer_errors.append(safe_failure(exc))
                            raise BoxSetupError(transfer_errors[-1]) from None
                        with service.lock:
                            job["files_done"] += 1

                # Reuse the existing byte-transfer implementation. A flattened, fully
                # paginated listing bypasses its recursion and partial-folder pitfalls.
                from aceneurotools.shared.file_downloader import download_file

                adapter = SimpleNamespace(
                    folders=SimpleNamespace(
                        get_folder_items=lambda _: SimpleNamespace(
                            entries=[SimpleNamespace(id=item["id"], name=item["path"], type="file") for item in missing]
                        )
                    ),
                    downloads=Transfers(),
                )
                succeeded = not missing or download_file(adapter, ".", int(number), base_file_path=stage)
                check()
                if not succeeded:
                    raise BoxSetupError(
                        transfer_errors[0]
                        if transfer_errors
                        else "Box download failed. Check access or reconnect in Box settings, then try again."
                    )
                if any(not matches(stage / item["path"], item, check) for item in missing):
                    raise ProjectError(
                        "The downloaded recording is incomplete or does not match Box. No new files were installed; try again."
                    )
                # Cancellation remains available until the short installation step.
                with self.lock:
                    check()
                    job.update(state="finalizing", message="Installing verified recording files…")
                # All transfers have succeeded before any existing files are replaced.
                for item in missing:
                    destination = safe_target(target, item["path"])
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        if not destination.is_file():
                            raise ProjectError(
                                "A folder occupies a recording file's location. Choose another local directory."
                            )
                        backup = target / ".ace-box-backups" / job["id"] / item["path"]
                        backup.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(destination, backup)
                    os.replace(stage / item["path"], destination)
                target.mkdir(parents=True, exist_ok=True)
                if any(not matches(safe_target(target, item["path"]), item) for item in files):
                    raise ProjectError("Recording files changed during download. Try loading the recording again.")
                previous = self._receipt(target, number)
                retained = {item["path"]: item for item in previous.get("files", [])}
                retained.update(
                    {item["path"]: {**item, "mtime_ns": (target / item["path"]).stat().st_mtime_ns} for item in files}
                )
                receipt = stage / "receipt.json"
                receipt.write_text(
                    json.dumps(
                        {
                            "folder_id": number,
                            "files": list(retained.values()),
                            "selection": job["selected_files"],
                            "complete": not job["subset"],
                        }
                    )
                )
                os.replace(receipt, target / ".ace-box.json")
            self._update(job, state="ready", message="Recording ready.")
        except DownloadCancelled:
            self._update(
                job, state="cancelled", message="Download cancelled. Temporary files removed; existing files retained."
            )
        except (BoxSetupError, ProjectError) as exc:
            self._update(job, state="failed", error=str(exc))
        except OSError:
            self._update(
                job,
                state="failed",
                error="Could not write the recording files. Check the local folder's permissions and disk space, then try again.",
            )
        except Exception as exc:
            self._update(job, state="failed", error=safe_failure(exc))
