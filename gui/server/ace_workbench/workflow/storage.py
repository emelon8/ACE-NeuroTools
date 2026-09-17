"""Bounded, resumable local copies of explicitly selected browser files."""

from __future__ import annotations

import os
import re
import shutil
import threading
import uuid
from pathlib import Path, PurePosixPath

from ..documents import ConflictError
from ..workspaces import confined
from .common import atomic_json, file_hash, read_json
from .models import InputFile

CHUNK_SIZE = 1024 * 1024
MAX_IMPORT = 100 * 1024**3
RESERVE = 64 * 1024**2


def relative_path(value: str) -> str:
    parts = PurePosixPath(value).parts
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if (
        not parts
        or len(parts) > 20
        or value.startswith("/")
        or "\\" in value
        or any(p in {"", ".", ".."} or p.startswith(".") or p.endswith((".", " ")) for p in value.split("/"))
        or any(ord(c) < 32 or c in ':<>"|?*' for c in value)
        or any(p.split(".")[0].upper() in reserved for p in parts)
    ):
        raise ValueError("Use visible files with relative, portable paths; links and traversal are not accepted.")
    return value


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("Invalid workflow identifier.")
    return value


class ImportStore:
    def __init__(self, project: Path):
        self.project = project
        self.root = confined(project, ".ace-workbench/imports")
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def directory(self, key: str) -> Path:
        return confined(self.root, identifier(key))

    def read(self, key: str) -> dict:
        return read_json(confined(self.directory(key), "import.json"))

    def write(self, value: dict) -> None:
        atomic_json(confined(self.directory(value["id"]), "import.json"), value)

    def begin(self, files: list[InputFile]) -> dict:
        with self.lock:
            names = [relative_path(f.path) for f in files]
            lowered = {name.casefold() for name in names}
            if len(lowered) != len(names):
                raise ValueError("Duplicate paths (including case-only differences) are not accepted.")
            if any(
                str(parent).casefold() in lowered
                for name in names
                for parent in PurePosixPath(name).parents
                if str(parent) != "."
            ):
                raise ValueError("A file path is also used as a folder.")
            total = sum(f.size for f in files)
            if total > MAX_IMPORT:
                raise ValueError(
                    "One import is limited to 100 GiB. Split independent recordings into separate imports."
                )
            # Account for other in-flight uploads, not just bytes already written.
            reserved = 0
            for path in self.root.glob("*/import.json"):
                item = read_json(path)
                if item["state"] == "uploading":
                    reserved += sum(f["size"] - f["received"] for f in item["files"])
            if shutil.disk_usage(self.root).free < total + reserved + RESERVE:
                raise ValueError("Insufficient free project disk space for this local copy.")
            key = uuid.uuid4().hex
            directory = self.directory(key)
            (directory / "files").mkdir(parents=True)
            value = {"id": key, "state": "uploading", "files": [{**f.model_dump(), "received": 0} for f in files]}
            for f in files:
                path = confined(directory / "files", f.path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=False)
            self.write(value)
            return value

    def append(self, key: str, index: int, offset: int, data: bytes) -> dict:
        with self.lock:
            value = self.read(key)
            if value["state"] != "uploading":
                raise ConflictError("This import no longer accepts uploads.")
            if not 0 <= index < len(value["files"]):
                raise ValueError("Unknown input file.")
            item = value["files"][index]
            if not data or len(data) > CHUNK_SIZE or offset < 0 or offset + len(data) > item["size"]:
                raise ValueError("Invalid upload chunk size or offset.")
            path = confined(self.directory(key) / "files", item["path"])
            # A repeated request after a lost response is safe only for identical bytes.
            if offset < item["received"]:
                with path.open("rb") as stream:
                    stream.seek(offset)
                    if offset + len(data) <= item["received"] and stream.read(len(data)) == data:
                        return {"received": item["received"]}
                raise ConflictError("Upload retry does not match the stored bytes.")
            if offset != item["received"]:
                raise ConflictError("Upload offset changed. Reopen the import before continuing.")
            if shutil.disk_usage(self.root).free < len(data) + RESERVE:
                raise ValueError("Project disk is full; upload stopped before writing this chunk.")
            with path.open("r+b") as stream:
                stream.seek(offset)
                stream.write(data)
                stream.truncate(offset + len(data))
                stream.flush()
                os.fsync(stream.fileno())
            item["received"] += len(data)
            self.write(value)
            return {"received": item["received"]}

    def finish(self, key: str) -> dict:
        with self.lock:
            value = self.read(key)
            if value["state"] != "uploading":
                return value
            for item in value["files"]:
                path = confined(self.directory(key) / "files", item["path"])
                if item["received"] != item["size"] or path.stat().st_size != item["size"]:
                    raise ConflictError(f"Upload incomplete: {item['path']}")
                item["sha256"] = file_hash(path)
            value["state"] = "inspected"
            self.write(value)
            return value

    def discard(self, key: str) -> None:
        with self.lock:
            value = self.read(key)
            if value["state"] == "attached":
                raise ConflictError("Attached recordings belong to their experiment and cannot be discarded here.")
            shutil.rmtree(self.directory(key))
