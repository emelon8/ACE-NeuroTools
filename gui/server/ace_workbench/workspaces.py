"""Explicit workspace registration; never scan the user's home directory."""

from __future__ import annotations

import hashlib
import sys
import threading
from pathlib import Path

from aceneurotools.evc.api import ExperimentVersionControl


class WorkspaceRegistry:
    def __init__(
        self,
        roots: list[Path],
        author: str | None = None,
        project: Path | None = None,
        runner_python: Path | None = None,
    ):
        if author and ("\n" in author or "<" not in author or not author.endswith(">")):
            raise ValueError("Author must have the form 'Name <email>'.")
        self.author = author
        self.lock = threading.RLock()
        self.active: set[str] = set()
        self.runner_python = str(runner_python or sys.executable)
        self.roots: dict[str, Path] = {}
        for root in roots:
            root = root.expanduser().resolve(strict=True)
            ExperimentVersionControl.open(root)
            self.roots[hashlib.sha256(str(root).encode()).hexdigest()[:16]] = root
        if not self.roots and project is None:
            raise ValueError("Supply at least one EVC workspace or use --demo.")
        self.project = (project or next(iter(self.roots.values())).parent).expanduser().resolve()
        self.project.mkdir(parents=True, exist_ok=True)

    def register(self, root: Path) -> dict:
        root = root.resolve(strict=True)
        ExperimentVersionControl.open(root)
        key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
        self.roots[key] = root
        return {"id": key, "name": root.name, "path": str(root)}

    def require_idle(self, workspace: str) -> None:
        if workspace in self.active:
            raise ValueError("A run is active in this experiment. Wait or cancel before changing tracked state.")

    def root(self, workspace: str) -> Path:
        if workspace not in self.roots:
            raise KeyError("Unknown workspace; restart with its explicit --workspace path.")
        return self.roots[workspace]

    def evc(self, workspace: str) -> ExperimentVersionControl:
        return ExperimentVersionControl.open(self.root(workspace))

    def list(self) -> list[dict]:
        return [{"id": key, "name": path.name, "path": str(path)} for key, path in self.roots.items()]


def confined(root: Path, relative: str) -> Path:
    """Refuse traversal, absolute paths, and symlinks at every component."""
    part = Path(relative)
    if part.is_absolute() or not part.parts or ".." in part.parts or "\\" in relative:
        raise ValueError("Expected a relative path inside the workspace.")
    target = root
    for name in part.parts:
        target = target / name
        if target.is_symlink():
            raise ValueError("Symbolic links are not editable through the workbench.")
    target.resolve().relative_to(root.resolve())
    return target


def discover(project: Path) -> list[Path]:
    project = project.expanduser().resolve(strict=True)
    return sorted(
        child for child in project.iterdir() if child.is_dir() and not child.is_symlink() and (child / ".evc").is_dir()
    )
