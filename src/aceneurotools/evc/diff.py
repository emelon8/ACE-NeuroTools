"""Structured diffs between recorded revisions.

Tree-level diff (added / removed / modified paths) plus a parameter-aware
layer: JSON files are compared key-by-key with dotted paths, because the
question a researcher asks is "which parameter changed?", not "which line".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from aceneurotools.evc.repository import ExperimentRepository


@dataclass(frozen=True)
class ParamChange:
    key: str
    old: object
    new: object


@dataclass(frozen=True)
class FileDiff:
    path: str
    status: str  # "added" | "removed" | "modified"
    param_changes: tuple[ParamChange, ...] = field(default=())


def _flatten_json(value: object, prefix: str = "") -> dict[str, object]:
    flat: dict[str, object] = {}
    if isinstance(value, dict):
        for key in sorted(value):
            flat.update(_flatten_json(value[key], f"{prefix}{key}."))
    else:
        # Lists (and scalars) are compared wholesale; element-level diffs are v2.
        flat[prefix.rstrip(".")] = value
    return flat


def _json_changes(old_data: bytes, new_data: bytes) -> tuple[ParamChange, ...]:
    try:
        old_flat = _flatten_json(json.loads(old_data))
        new_flat = _flatten_json(json.loads(new_data))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ()
    changes = []
    for key in sorted(set(old_flat) | set(new_flat)):
        old_value = old_flat.get(key, "<absent>")
        new_value = new_flat.get(key, "<absent>")
        if old_value != new_value:
            changes.append(ParamChange(key=key, old=old_value, new=new_value))
    return tuple(changes)


def diff_trees(repo: ExperimentRepository, tree_a: str, tree_b: str) -> list[FileDiff]:
    """Compare two trees; JSON files get key-level parameter changes."""
    flat_a = repo.flatten_tree(tree_a)
    flat_b = repo.flatten_tree(tree_b)
    diffs: list[FileDiff] = []
    for path in sorted(set(flat_a) | set(flat_b)):
        oid_a, oid_b = flat_a.get(path), flat_b.get(path)
        if oid_a == oid_b:
            continue
        if oid_a is None:
            diffs.append(FileDiff(path=path, status="added"))
        elif oid_b is None:
            diffs.append(FileDiff(path=path, status="removed"))
        else:
            params: tuple[ParamChange, ...] = ()
            if path.endswith(".json"):
                params = _json_changes(repo.read_blob(oid_a).data, repo.read_blob(oid_b).data)
            diffs.append(FileDiff(path=path, status="modified", param_changes=params))
    return diffs
