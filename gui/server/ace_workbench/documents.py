"""Validated JSON edits with optimistic concurrency and atomic replacement."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from aceneurotools.evc.api import load_schema

from .workspaces import WorkspaceRegistry, confined

MAX_DOCUMENT = 2 * 1024 * 1024
SCHEMAS = {"experiment.json": "experiment.v1", "analysis.cnmfe.json": "analysis.cnmfe.v1"}


class ConflictError(ValueError):
    """The caller is editing an obsolete version."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_path(root: Path, path: str) -> Path:
    target = confined(root, path)
    if Path(path).parts[0] != "parameters" or target.suffix != ".json":
        raise ValueError("Only parameters/*.json documents can be edited.")
    return target


def read_document(registry: WorkspaceRegistry, workspace: str, path: str, revision: str | None = None) -> dict:
    target = document_path(registry.root(workspace), path)
    if revision:
        evc = registry.evc(workspace)
        info = evc.show(revision)
        files = evc.repo.flatten_tree(info.tree)
        if path not in files:
            raise FileNotFoundError("Document does not exist at this revision.")
        data = evc.repo.read_blob(files[path]).data
    else:
        if target.stat().st_size > MAX_DOCUMENT:
            raise ValueError("Document exceeds the 2 MiB editor limit.")
        data = target.read_bytes()
    if len(data) > MAX_DOCUMENT:
        raise ValueError("Document exceeds the 2 MiB editor limit.")
    return {"path": path, "text": data.decode("utf-8"), "etag": digest(data), "revision": revision}


def parse_document(path: str, text: str) -> dict:
    if len(text.encode()) > MAX_DOCUMENT:
        raise ValueError("Document exceeds the 2 MiB editor limit.")

    def reject_constant(value: str):
        raise ValueError(f"Non-finite JSON number: {value}")

    value = json.loads(text, parse_constant=reject_constant)
    if not isinstance(value, dict):
        raise ValueError("A parameter document must be a JSON object.")
    schema = SCHEMAS.get(Path(path).name)
    if schema:
        errors = sorted(Draft202012Validator(load_schema(schema)).iter_errors(value), key=lambda e: str(e.path))
        if errors:
            raise ValueError("; ".join(f"{'.'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors[:20]))
    return value


def save_document(registry: WorkspaceRegistry, workspace: str, path: str, text: str, etag: str) -> dict:
    value = parse_document(path, text)
    target = document_path(registry.root(workspace), path)
    with registry.lock:
        current = read_document(registry, workspace, path)
        if current["etag"] != etag:
            raise ConflictError("This file changed on disk. Reload it before saving; your editor buffer is preserved.")
        previous = json.loads(current["text"])
        if previous.get("_csv") != value.get("_csv"):
            raise ValueError("CSV provenance (_csv) is preserved; edit parameter fields instead.")
        fd, temporary = tempfile.mkstemp(prefix=".ace-", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, target.stat().st_mode & 0o777)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return read_document(registry, workspace, path)


def list_documents(registry: WorkspaceRegistry, workspace: str) -> list[str]:
    root = registry.root(workspace)
    directory = confined(root, "parameters")
    return sorted(
        str(path.relative_to(root))
        for path in directory.rglob("*.json")
        if not path.is_symlink()
        and path.is_file()
        and not any(parent.is_symlink() for parent in path.parents if parent != root)
    )
