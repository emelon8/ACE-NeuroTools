"""ACE-NeuroTools experiment version control (EVC).

Git-like version control for experiment parameters and result manifests:
immutable content-addressed objects (blob/tree/commit), journaled refs, and a
small set of axiomatic porcelain commands — record, status, history, show,
diff, restore, comment, recover, push.

Design: docs/design/experiment-version-control.md (maps to Comenius F07/#76,
gated by decisions D07 #93 and D08 #94 — this subpackage is Eli's owned
prototype informing those decisions).

Quick start::

    from aceneurotools.evc import ExperimentVersionControl

    evc = ExperimentVersionControl.init("path/to/experiment")
    evc.record("initial parameters")
    evc.restore("HEAD")            # never destroys — see porcelain docstring
"""

from aceneurotools.evc.diff import FileDiff, ParamChange
from aceneurotools.evc.errors import (
    AmbiguousIdError,
    CorruptObjectError,
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
from aceneurotools.evc.objects import Blob, Commit, Tree, TreeEntry, object_id
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
from aceneurotools.evc.remote import LocalDirectoryRemote, PushResult, Remote
from aceneurotools.evc.repository import ExperimentRepository
from aceneurotools.evc.workspace import DEFAULT_IGNORE_PATTERNS, ExperimentWorkspace

__all__ = [
    # porcelain
    "ExperimentVersionControl",
    "RevisionInfo",
    "StatusReport",
    "RestoreResult",
    # plumbing
    "ExperimentRepository",
    "Blob",
    "Tree",
    "TreeEntry",
    "Commit",
    "object_id",
    # workspace contract
    "ExperimentWorkspace",
    "DEFAULT_IGNORE_PATTERNS",
    # pointer manifests
    "ArtifactPointer",
    "ManifestVerification",
    "write_manifest",
    "read_manifest",
    "verify_manifest",
    # remotes
    "Remote",
    "LocalDirectoryRemote",
    "PushResult",
    # diffs
    "FileDiff",
    "ParamChange",
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
]
