"""ExperimentWorkspace — the experiment directory contract (what gets versioned).

Implements Phase 1 of ``docs/design/evc-implementation-plan.md``: real
experiments mix tracked state (parameters, configs, result manifests) with
untracked bulk (raw recordings, memmaps, ``saved_movies/``), so the workspace
defines a layout that separates the two and a declarative ignore policy that
keeps bulk out of the object store (design doc
``experiment-version-control.md`` §7, deviation 6).

Layout — provisional until Comenius decision D06 (data layout); this class is
the single place the layout is encoded::

    <experiment>/
        .evc/               the repository + declarative ``ignore`` policy file
        parameters/         versioned: parameter/config JSON files
        results/<run-id>/   versioned: one manifest.json per run (Phase 2)
        artifacts/          never versioned: bulk outputs

The ignore policy lives in ``.evc/ignore`` (one name or glob per line — see
:class:`~aceneurotools.evc.worktree.IgnoreRules` for the matching rules),
created by ``ExperimentVersionControl.init`` with the safe defaults in
:data:`DEFAULT_IGNORE_PATTERNS`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aceneurotools.evc.errors import EVCError
from aceneurotools.evc.worktree import IGNORE_FILE

PARAMETERS_DIR = "parameters"
RESULTS_DIR = "results"
ARTIFACTS_DIR = "artifacts"

#: Safe-default ignore globs written to ``.evc/ignore`` at ``init``
#: (plan §Phase 1): bulk recordings and derived binaries never enter history.
DEFAULT_IGNORE_PATTERNS = (
    f"{ARTIFACTS_DIR}/",
    "*.avi",
    "*.hdf5",
    "*.raw",
    "*.mmap",
    "*.ncs",
    "*.nev",
    "saved_movies/",
)

_IGNORE_HEADER = """\
# Experiment version control ignore policy (.evc/ignore).
# One file/directory name or glob pattern per line; '#' starts a comment.
#   - a trailing '/' restricts the pattern to directories
#   - patterns without '/' match names at any depth
#   - patterns containing '/' match paths relative to the experiment root
"""


def write_default_ignore(evc_dir: str | Path) -> Path:
    """Write the safe-default ``.evc/ignore`` file; return its path.

    An existing ignore file is left untouched — the researcher's edited
    policy is authoritative over the shipped defaults.
    """
    path = Path(evc_dir) / IGNORE_FILE
    if not path.exists():
        path.write_text(_IGNORE_HEADER + "\n".join(DEFAULT_IGNORE_PATTERNS) + "\n")
    return path


@dataclass(frozen=True)
class ExperimentWorkspace:
    """Owns one experiment directory and its versioned/unversioned layout."""

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    # -- layout -------------------------------------------------------------

    @property
    def parameters_dir(self) -> Path:
        """Versioned: the experiment's live parameter/config files."""
        return self.root / PARAMETERS_DIR

    @property
    def results_dir(self) -> Path:
        """Versioned: one subdirectory per run holding its manifest (Phase 2)."""
        return self.root / RESULTS_DIR

    @property
    def artifacts_dir(self) -> Path:
        """Never versioned: bulk outputs (ignored via ``.evc/ignore``)."""
        return self.root / ARTIFACTS_DIR

    def run_dir(self, run_id: str) -> Path:
        """The results directory for one run: ``results/<run-id>/``."""
        if (
            not run_id
            or run_id in (".", "..")
            or any(ch in run_id for ch in ("/", "\\", "\0"))
        ):
            raise EVCError(f"illegal run id: {run_id!r}")
        return self.results_dir / run_id

    # -- lifecycle ----------------------------------------------------------

    @classmethod
    def scaffold(cls, root: str | Path) -> ExperimentWorkspace:
        """Create the standard layout inside an experiment directory."""
        workspace = cls(Path(root))
        for directory in (
            workspace.parameters_dir,
            workspace.results_dir,
            workspace.artifacts_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return workspace
