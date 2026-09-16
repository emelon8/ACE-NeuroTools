"""evc.api — the frozen API contract for GUI, CLI, and pipeline consumers.

Implements Phase 7 of ``docs/design/evc-implementation-plan.md`` (GUI
hand-off): every name re-exported here, together with the return types of the
porcelain commands, IS the contract — the GUI (Comenius decision D03) builds
its screens from ``docs/api/evc.md`` and this module alone, per the
shared-backend rule (ADR 0001: the GUI is an API over the same backend the
CLI uses).

Contract rules:

* Porcelain commands return frozen, typed dataclasses (``RevisionInfo``,
  ``StatusReport``, ``RestoreResult``, ``PushResult``, ``FileDiff``,
  ``ParamChange``, ``JournalEntry``, ``ManifestVerification``) — never bare
  dicts or tuples.
* Failures raise typed :class:`~aceneurotools.evc.errors.EVCError`
  subclasses — no command communicates failure through return values.
* Additions are allowed; renames/removals/behaviour changes of the names
  below require a plan revision (they would break GUI screens).

Everything here is importable without caiman or any third-party package —
the EVC subpackage is pure standard library.
"""

from aceneurotools.evc.csv_bridge import (
    ImportResult,
    extract,
    import_experiment,
    load_schema,
    validate_document,
    writeback,
)
from aceneurotools.evc.diff import FileDiff, ParamChange
from aceneurotools.evc.errors import (
    AmbiguousIdError,
    CorruptObjectError,
    CSVBridgeError,
    EVCError,
    InvalidObjectError,
    ManifestError,
    NothingToRecordError,
    ObjectNotFoundError,
    PushRejectedError,
    RefConflictError,
    RepositoryExistsError,
    RepositoryNotFoundError,
    UnknownRevisionError,
)
from aceneurotools.evc.hooks import RunRecorder
from aceneurotools.evc.pointers import (
    ArtifactPointer,
    ManifestVerification,
    read_manifest,
    verify_manifest,
    write_manifest,
)
from aceneurotools.evc.porcelain import (
    ExperimentVersionControl,
    RestoreResult,
    RevisionInfo,
    StatusReport,
)
from aceneurotools.evc.refs import JournalEntry
from aceneurotools.evc.remote import LocalDirectoryRemote, PushResult, Remote
from aceneurotools.evc.workspace import DEFAULT_IGNORE_PATTERNS, ExperimentWorkspace

__all__ = [
    # entry point (the porcelain facade)
    "ExperimentVersionControl",
    # frozen return types
    "RevisionInfo",
    "StatusReport",
    "RestoreResult",
    "FileDiff",
    "ParamChange",
    "JournalEntry",
    "PushResult",
    "ManifestVerification",
    "ArtifactPointer",
    # workspace contract
    "ExperimentWorkspace",
    "DEFAULT_IGNORE_PATTERNS",
    # result manifests
    "write_manifest",
    "read_manifest",
    "verify_manifest",
    # pipeline hooks
    "RunRecorder",
    # csv bridge (D05 migration: import, edit-as-JSON, write back)
    "extract",
    "writeback",
    "import_experiment",
    "ImportResult",
    "load_schema",
    "validate_document",
    # remotes
    "Remote",
    "LocalDirectoryRemote",
    # errors
    "EVCError",
    "RepositoryNotFoundError",
    "RepositoryExistsError",
    "ObjectNotFoundError",
    "AmbiguousIdError",
    "CorruptObjectError",
    "InvalidObjectError",
    "RefConflictError",
    "UnknownRevisionError",
    "NothingToRecordError",
    "PushRejectedError",
    "ManifestError",
    "CSVBridgeError",
]
