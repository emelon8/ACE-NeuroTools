"""LFS-style pointer manifests for large result artifacts.

Implements Phase 2 of ``docs/design/evc-implementation-plan.md``: results
(``meanFluorescence_*.npz``, ``estimates.hdf5``, figures) must be *provable*
without being *stored* in history (design doc ``experiment-version-control.md``
§7, deviation 6 — the Git LFS pointer-file pattern). A run's output directory
gets one small ``manifest.json`` describing every artifact as a pointer —
plain SHA-256 of the file bytes (git-lfs ``oid sha256:...`` convention, no
object header), size, and path — which is versioned in place of the bytes.

``verify_manifest`` re-hashes the artifacts and names exactly which files are
missing or modified: the F06 provenance primitive.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from aceneurotools.evc.errors import ManifestError

POINTER_SCHEMA = "evc-pointer-v1"
MANIFEST_SCHEMA = "evc-manifest-v1"
MANIFEST_NAME = "manifest.json"

_HASH_CHUNK_BYTES = 1024 * 1024  # stream large artifacts; never load them whole
_SKIP_NAMES = frozenset({".DS_Store"})


def hash_artifact(path: str | Path) -> str:
    """Streamed SHA-256 of a file's raw bytes (no git object header)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ArtifactPointer:
    """One versioned pointer to an unversioned artifact (plan §Phase 2 schema)."""

    sha256: str
    size: int
    relpath: str
    created: str
    producer: dict[str, str | None] | None = None

    def to_dict(self) -> dict:
        return {
            "schema": POINTER_SCHEMA,
            "sha256": self.sha256,
            "size": self.size,
            "relpath": self.relpath,
            "created": self.created,
            "producer": self.producer,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ArtifactPointer:
        if data.get("schema") != POINTER_SCHEMA:
            raise ManifestError(f"unsupported pointer schema: {data.get('schema')!r}")
        try:
            return cls(
                sha256=str(data["sha256"]),
                size=int(data["size"]),
                relpath=str(data["relpath"]),
                created=str(data.get("created", "")),
                producer=data.get("producer"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(f"malformed artifact pointer: {data!r}") from exc


@dataclass(frozen=True)
class ManifestVerification:
    """Outcome of re-hashing a run's artifacts against its manifest."""

    manifest_path: str
    verified: tuple[str, ...]
    missing: tuple[str, ...]
    modified: tuple[str, ...]

    @property
    def clean(self) -> bool:
        return not (self.missing or self.modified)


def _iter_artifact_relpaths(run_dir: Path, skip_manifest: bool, exclude: frozenset[Path]) -> list[str]:
    """Sorted artifact paths relative to ``run_dir`` (posix separators)."""
    found: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.is_symlink() or path.name in _SKIP_NAMES:
            continue
        if path.resolve() in exclude:
            continue
        rel = path.relative_to(run_dir).as_posix()
        if skip_manifest and rel == MANIFEST_NAME:
            continue
        found.append(rel)
    return found


def write_manifest(
    run_dir: str | Path,
    pipeline: str | None = None,
    revision: str | None = None,
    manifest_dir: str | Path | None = None,
    exclude: Sequence[str | Path] = (),
) -> Path:
    """Hash every artifact in a run's output directory into one manifest.

    The manifest is written to ``<run_dir>/manifest.json`` by default. Pass
    ``manifest_dir`` to write it elsewhere (Phase 3 mirrors manifests into the
    workspace's versioned ``results/<run-id>/``); the manifest then records the
    run directory as ``base_dir`` relative to its own location so ``verify``
    still finds the artifacts. ``exclude`` lists files inside ``run_dir`` that
    are run *metadata* rather than results (e.g. ``run_log.json``, which the
    Phase 3 recorder mutates when linking revision ids — hashing it would
    leave the manifest permanently stale). Returns the manifest path.
    """
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        raise ManifestError(f"run directory not found: {run_dir}")
    manifest_dir = run_dir if manifest_dir is None else Path(manifest_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    if manifest_dir.resolve() == run_dir.resolve():
        base_dir = "."
    else:
        try:
            base_dir = Path(os.path.relpath(run_dir, manifest_dir)).as_posix()
        except ValueError:  # e.g. different drives on Windows
            base_dir = str(run_dir)

    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    producer = {"pipeline": pipeline, "revision": revision} if pipeline is not None or revision is not None else None
    excluded = frozenset(Path(p).resolve() for p in exclude)
    pointers = [
        ArtifactPointer(
            sha256=hash_artifact(run_dir / rel),
            size=(run_dir / rel).stat().st_size,
            relpath=rel,
            created=created,
            producer=producer,
        )
        for rel in _iter_artifact_relpaths(run_dir, skip_manifest=base_dir == ".", exclude=excluded)
    ]

    payload = {
        "schema": MANIFEST_SCHEMA,
        "base_dir": base_dir,
        "artifacts": [pointer.to_dict() for pointer in pointers],
    }
    manifest_path = manifest_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return manifest_path


def _load_manifest(manifest_dir: Path) -> tuple[dict, Path]:
    manifest_path = manifest_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ManifestError(f"no {MANIFEST_NAME} in {manifest_dir}")
    try:
        payload = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{manifest_path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema") != MANIFEST_SCHEMA:
        raise ManifestError(
            f"unsupported manifest schema in {manifest_path}: "
            f"{payload.get('schema') if isinstance(payload, dict) else payload!r}"
        )
    return payload, manifest_path


def read_manifest(run_dir: str | Path) -> tuple[ArtifactPointer, ...]:
    """Return the pointers recorded in a directory's manifest."""
    payload, _ = _load_manifest(Path(run_dir))
    return tuple(ArtifactPointer.from_dict(entry) for entry in payload["artifacts"])


def verify_manifest(run_dir: str | Path) -> ManifestVerification:
    """Re-hash a run's artifacts; report exactly what is missing or modified.

    ``run_dir`` is the directory containing ``manifest.json``; artifacts are
    resolved against the manifest's recorded ``base_dir`` (``.`` for the
    default in-place layout).
    """
    manifest_dir = Path(run_dir)
    payload, manifest_path = _load_manifest(manifest_dir)
    base = manifest_dir / payload.get("base_dir", ".")

    verified: list[str] = []
    missing: list[str] = []
    modified: list[str] = []
    for entry in payload["artifacts"]:
        pointer = ArtifactPointer.from_dict(entry)
        target = base / pointer.relpath
        if not target.is_file():
            missing.append(pointer.relpath)
        elif target.stat().st_size != pointer.size or hash_artifact(target) != pointer.sha256:
            modified.append(pointer.relpath)
        else:
            verified.append(pointer.relpath)
    return ManifestVerification(
        manifest_path=str(manifest_path),
        verified=tuple(verified),
        missing=tuple(missing),
        modified=tuple(modified),
    )
