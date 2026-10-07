"""RunRecorder — the pipeline lifecycle observer (the surgical integration).

Implements Phase 3 of ``docs/design/evc-implementation-plan.md``: revisions
happen at the two moments that matter — run approval and run completion —
without entangling pipelines with version control. Pipelines receive an
optional ``RunRecorder`` by dependency injection and only ever call its three
lifecycle methods; with ``recorder=None`` (the default everywhere) pipeline
behaviour is byte-identical to a build without EVC. Pipelines never import
plumbing.

Provenance chain per run (plan §1): pre-run revision → exact parameter tree →
run record (``run_log.json`` carries both revision ids) → post-run revision →
result manifest with artifact checksums.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from aceneurotools.evc.errors import NothingToRecordError
from aceneurotools.evc.pointers import write_manifest
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.refs import ZERO_OID
from aceneurotools.evc.workspace import ExperimentWorkspace

#: Where the effective (post-precedence) parameters of an approved run are
#: serialized inside the workspace, ready for the pre-run snapshot.
EFFECTIVE_PARAMS_NAME = "effective_run_params.json"

#: Keys written into ``run_log.json`` linking the run to its revisions.
PRE_REVISION_KEY = "evc_pre_revision"
POST_REVISION_KEY = "evc_post_revision"


class RunRecorder:
    """Records pre/post-run revisions for one pipeline run.

    Lifecycle (exactly three methods, called by the wired pipelines):

    1. :meth:`on_run_approved` — pre-run revision of the effective parameters.
    2. :meth:`on_run_completed` — result manifest + post-run revision; both
       revision ids are linked into the run's ``run_log.json``.
    3. :meth:`on_run_failed` — journal entry only: failed runs are visible in
       ``recover``, never in ``history``.
    """

    def __init__(
        self,
        experiment_dir: str | Path,
        pipeline: str,
        line: int | str | Sequence[int] | None = None,
        author: str | None = None,
    ) -> None:
        self.evc = ExperimentVersionControl.open(experiment_dir)
        self.workspace = ExperimentWorkspace(Path(experiment_dir))
        self.pipeline = pipeline
        if line is None or isinstance(line, (int, str)):
            self.line = None if line is None else str(line)
        else:
            self.line = " ".join(str(n) for n in line)
        self.author = author
        self.pre_revision: str | None = None
        self.post_revision: str | None = None

    def _label(self) -> str:
        return f"{self.pipeline} line {self.line}" if self.line else self.pipeline

    def _record(self, message: str) -> str:
        """Record a revision; an identical re-run reuses the current head
        (the head already *is* this state — no empty revision is fabricated)."""
        try:
            return self.evc.record(message, author=self.author)
        except NothingToRecordError:
            head = self.evc.repo.refs.head_oid()
            assert head is not None  # NothingToRecordError implies a head exists
            return head

    # -- lifecycle ----------------------------------------------------------

    def on_run_approved(self, params: dict, config_paths: Sequence[str | Path] = ()) -> str:
        """Serialize the effective parameters; record the pre-run revision.

        ``params`` must be the post-precedence dict the pipeline will actually
        use. ``config_paths`` are recorded verbatim for traceability; hashing
        them and snapshotting the environment (package versions) is the
        D08-gated extension point — the hook exists, the policy is pending.
        """
        params_path = self.workspace.parameters_dir / EFFECTIVE_PARAMS_NAME
        params_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "evc-run-params-v1",
            "pipeline": self.pipeline,
            "params": params,
            "config_paths": [str(p) for p in config_paths],
        }
        params_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
        self.pre_revision = self._record(f"run approved: {self._label()}")
        return self.pre_revision

    def on_run_completed(
        self,
        run_dir: str | Path,
        run_log: str | Path | None = None,
        run_id: str | None = None,
    ) -> str:
        """Manifest the run's artifacts; record the post-run revision.

        The manifest lands in the versioned ``results/<run-id>/`` of the
        workspace (mirrored via the Phase 2 ``base_dir`` mechanism when
        ``run_dir`` lives elsewhere). When ``run_log`` is given, both revision
        ids are written into it (keys ``evc_pre_revision``,
        ``evc_post_revision``); the pre id lands before the post-run snapshot
        so the recorded tree links back to its approving revision.
        """
        run_dir = Path(run_dir)
        run_id = run_id if run_id is not None else run_dir.name
        write_manifest(
            run_dir,
            pipeline=self.pipeline,
            revision=self.pre_revision,
            manifest_dir=self.workspace.run_dir(run_id),
            # the run log is run metadata mutated below, not a result artifact
            exclude=() if run_log is None else (run_log,),
        )
        if run_log is not None and self.pre_revision is not None:
            self._link_run_log(Path(run_log), {PRE_REVISION_KEY: self.pre_revision})
        self.post_revision = self._record(f"run completed: {self._label()} (run {run_id})")
        if run_log is not None:
            self._link_run_log(Path(run_log), {POST_REVISION_KEY: self.post_revision})
        return self.post_revision

    def on_run_failed(self, error: BaseException) -> None:
        """Journal the failure — no revision, no ref movement (axiom-safe):
        a failed run never notarises state, but stays visible in ``recover``."""
        head = self.evc.repo.refs.head_oid() or ZERO_OID
        self.evc.repo.refs.append_journal(
            ref="(none)",
            old=head,
            new=head,
            op="run-failed",
            message=f"{self._label()}: {type(error).__name__}: {error}",
        )

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _link_run_log(run_log_path: Path, keys: dict[str, str]) -> None:
        payload = json.loads(run_log_path.read_text()) if run_log_path.is_file() else {}
        payload.update(keys)
        run_log_path.parent.mkdir(parents=True, exist_ok=True)
        run_log_path.write_text(json.dumps(payload, indent=2))
