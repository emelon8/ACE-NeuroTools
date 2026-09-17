"""Transport helpers over the EVC history contract."""

from dataclasses import asdict

from .documents import ConflictError, digest
from .workspaces import WorkspaceRegistry


def state(registry: WorkspaceRegistry, workspace: str) -> dict:
    evc = registry.evc(workspace)
    report = asdict(evc.status())
    # Includes every tracked byte, including changes made by a CLI since refresh.
    report["version"] = digest((str(report["head"]) + evc.worktree.snapshot()).encode())
    return report


def require_version(registry: WorkspaceRegistry, workspace: str, version: str) -> None:
    if state(registry, workspace)["version"] != version:
        raise ConflictError("Experiment changed since review. Refresh and review the current changes.")


def record(registry: WorkspaceRegistry, workspace: str, message: str, version: str) -> dict:
    with registry.lock:
        registry.require_idle(workspace)
        require_version(registry, workspace, version)
        revision = registry.evc(workspace).record(message, author=registry.author)
        return {"revision": revision}


def restore(registry: WorkspaceRegistry, workspace: str, revision: str, version: str) -> dict:
    with registry.lock:
        registry.require_idle(workspace)
        require_version(registry, workspace, version)
        return asdict(registry.evc(workspace).restore(revision, author=registry.author))
