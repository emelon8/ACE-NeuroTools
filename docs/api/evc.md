# Experiment Version Control API

The frozen contract for building on experiment version control — GUI screens,
CLI commands, and pipeline integrations all sit on the same backend
(ADR 0001). Import everything from one place:

```python
from aceneurotools.evc.api import ExperimentVersionControl
```

**Contract rules.** Porcelain commands return frozen, typed dataclasses
(documented below) — never bare dicts. Failures raise typed `EVCError`
subclasses — no command signals failure through its return value. Names on
this page are stable: additions are fine; renames, removals, or behaviour
changes require a plan revision. The subpackage is pure standard library —
importable without caiman.

Invariants every command preserves (see the
[design document](../design/experiment-version-control.md) §4): objects are
immutable and integrity-checked · nothing is ever lost (every state change is
journaled; `restore` preserves dirty state first) · history only moves
forward (refs never rewind) · comments never rewrite history · publication is
append-only and fast-forward-only.

## Screen → command map

| Screen / control | Call | Returns |
| --- | --- | --- |
| "What changed?" panel | `evc.status()` | `StatusReport` (per-file `FileDiff` with per-parameter `ParamChange`) |
| History list | `evc.history(limit)` | `list[RevisionInfo]`, newest first |
| Revision detail | `evc.show(rev)` | `RevisionInfo` (with file list) |
| Compare two revisions | `evc.diff(a, b)` | `list[FileDiff]` |
| Restore button | `evc.restore(rev)` | `RestoreResult` (`safety_snapshot` set if dirty state was preserved) |
| Recovery browser | `evc.recover()` | `list[JournalEntry]` (any `new` id is restorable; `op == "run-failed"` marks failed runs) |
| Comment thread | `evc.comment(rev, text)` / `evc.comments(rev)` | notes id / accumulated text |
| Record snapshot | `evc.record(message)` | revision id (`str`) |
| Publish | `evc.push(remote)` | `list[PushResult]` (raises `PushRejectedError` on divergence) |
| Results integrity badge | `verify_manifest(run_dir)` | `ManifestVerification` (`clean`, `missing`, `modified`) |

`rev` accepts `HEAD`, a branch name, or a unique id prefix (≥ 4 hex chars).

## Entry point

::: aceneurotools.evc.porcelain.ExperimentVersionControl

## Frozen return types

::: aceneurotools.evc.porcelain.RevisionInfo

::: aceneurotools.evc.porcelain.StatusReport

::: aceneurotools.evc.porcelain.RestoreResult

::: aceneurotools.evc.diff.FileDiff

::: aceneurotools.evc.diff.ParamChange

::: aceneurotools.evc.refs.JournalEntry

::: aceneurotools.evc.remote.PushResult

## Workspace contract

::: aceneurotools.evc.workspace.ExperimentWorkspace

## Result pointer manifests

::: aceneurotools.evc.pointers.write_manifest

::: aceneurotools.evc.pointers.read_manifest

::: aceneurotools.evc.pointers.verify_manifest

::: aceneurotools.evc.pointers.ArtifactPointer

::: aceneurotools.evc.pointers.ManifestVerification

## Pipeline hooks

::: aceneurotools.evc.hooks.RunRecorder

## Remotes

::: aceneurotools.evc.remote.Remote

::: aceneurotools.evc.remote.LocalDirectoryRemote

## Errors

::: aceneurotools.evc.errors
