"""Inspect real result pointers; never silently trust manifest paths."""

import csv
import io
import json
import math
from dataclasses import asdict

from aceneurotools.evc.api import EVCError, read_manifest, verify_manifest

from .workspaces import WorkspaceRegistry, confined


def manifest(registry: WorkspaceRegistry, workspace: str, run: str):
    root = registry.root(workspace)
    directory = confined(root, f"results/{run}")
    path = confined(root, f"results/{run}/manifest.json")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Manifest exceeds the 2 MiB inspection limit.")
    payload = json.loads(path.read_text())
    base = (directory / payload.get("base_dir", ".")).resolve()
    try:
        relative = base.relative_to(root)
    except ValueError as exc:
        raise ValueError("Artifacts are outside this registered workspace; verify them with the EVC CLI.") from exc
    confined(root, str(relative))
    pointers = read_manifest(directory)
    for pointer in pointers:
        confined(base, pointer.relpath)
    return directory, base, pointers


def list_results(registry: WorkspaceRegistry, workspace: str) -> list[dict]:
    root = registry.root(workspace)
    directory = confined(root, "results")
    results = []
    for run in sorted(directory.iterdir()) if directory.is_dir() else []:
        if not run.is_dir() or run.is_symlink() or not (run / "manifest.json").is_file():
            continue
        try:
            _, _, pointers = manifest(registry, workspace, run.name)
            results.append({"id": run.name, "artifacts": [p.to_dict() for p in pointers], "error": None})
        except (ValueError, OSError, KeyError, TypeError, EVCError) as exc:
            results.append({"id": run.name, "artifacts": [], "error": str(exc)})
    return results


def verify(registry: WorkspaceRegistry, workspace: str, run: str) -> dict:
    directory, _, _ = manifest(registry, workspace, run)
    result = verify_manifest(directory)
    return {**asdict(result), "clean": result.clean}


def preview(registry: WorkspaceRegistry, workspace: str, run: str, path: str) -> dict:
    _, base, pointers = manifest(registry, workspace, run)
    if path not in {p.relpath for p in pointers}:
        raise ValueError("Only manifest-listed artifacts can be previewed.")
    target = confined(base, path)
    if target.suffix.lower() not in {".csv", ".tsv", ".txt", ".json"}:
        raise ValueError("Preview supports CSV, TSV, JSON and text artifacts.")
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Artifact exceeds the 2 MiB preview limit.")
    text = target.read_text(encoding="utf-8")
    if target.suffix.lower() in {".csv", ".tsv"}:
        rows = list(csv.reader(io.StringIO(text), delimiter="\t" if target.suffix == ".tsv" else ","))
        columns, data = (rows[0], rows[1:501]) if rows else ([], [])
        numeric = []
        for row in data:
            try:
                numbers = [float(cell) for cell in row]
                if len(numbers) >= 2 and all(math.isfinite(n) for n in numbers):
                    numeric.append(numbers)
            except ValueError:
                pass
        return {"kind": "table", "columns": columns, "rows": data, "numeric": numeric, "truncated": len(rows) > 501}
    return {"kind": "text", "text": text}
