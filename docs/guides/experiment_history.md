# Experiment History

ACE-NeuroTools can keep a **git-like history of your experiments**: every
change to an experiment's parameters and result manifests can be recorded as
a *revision* you can inspect, compare, comment on, restore, and share. It
exists to solve a familiar problem — you edit a settings file, run something,
and later can't recover the configuration that produced a result.

The guarantees (see the
[design document](../design/experiment-version-control.md) for the full
axioms):

- **Nothing is ever lost.** There is no destructive command: `restore` first
  preserves your current state as a recoverable safety snapshot, revisions are
  immutable, and every change of state is journaled.
- **History only moves forward.** Restoring an old revision never rewrites
  history; keeping a restored state just records a new revision.
- **Results are provable, not stored.** Bulk artifacts (movies, `.hdf5`,
  memmaps) never enter history — each run gets a small *manifest* of SHA-256
  checksums instead, and `verify` can prove artifacts are intact.

## Setting up an experiment

Initialise version control inside an experiment directory (the `--workspace`
flag also scaffolds the standard layout):

```bash
cd /path/to/experiment
ace-neuro history init --workspace
```

This creates:

```
<experiment>/
    .evc/            the history itself (never edit by hand)
    .evc/ignore      what stays out of history (globs, editable)
    parameters/      versioned: parameter/config files
    results/         versioned: one manifest.json per run
    artifacts/       never versioned: bulk outputs
```

Raw recordings are excluded by default (`*.avi`, `*.hdf5`, `*.raw`, `*.mmap`,
`saved_movies/`, `artifacts/`) — recording a snapshot next to a 100 GB movie
is instant and stores none of the movie's bytes. Edit `.evc/ignore` (one name
or glob per line) to adjust the policy.

## Everyday commands

All commands work identically as `ace-neuro history <command>` and
`python -m aceneurotools.evc <command>`; both are thin shells over the same
backend the future GUI will use.

```bash
ace-neuro history record -m "lowered min_corr for noisy session"
ace-neuro history status                 # clean, or what changed vs HEAD
ace-neuro history log                    # revisions, newest first
ace-neuro history show <rev>             # one revision: metadata + files
ace-neuro history diff <rev-a> [rev-b]   # per-parameter old -> new changes
ace-neuro history comment <rev> -m "QC passed; baseline for figure 2"
ace-neuro history comments <rev>
ace-neuro history restore <rev>          # never destroys; see below
ace-neuro history recover                # journal incl. safety snapshots
ace-neuro history push /lab/share/exp42  # publish (fast-forward only)
ace-neuro history verify <run-id>        # re-hash a run's artifacts
```

`<rev>` may be `HEAD`, a branch name, or any unique revision-id prefix of at
least 4 characters. JSON parameter files are diffed **key by key** — `diff`
answers "which parameter changed", not "which line".

Operate on a specific directory with `--dir`, or resolve an experiment from
your project's `experiments.csv` by line number:

```bash
ace-neuro history --dir /path/to/experiment log
ace-neuro history --experiment 97 --project-path /my/project log
```

(Place `--dir`/`--experiment` *before* the command name.)

### Restore never destroys

If your working state is dirty when you `restore`, the dirty state is first
recorded as a *safety snapshot* reachable through `recover` — so restoring is
always safe to try:

```bash
ace-neuro history restore 65761b0e            # oops, I had unsaved edits?
ace-neuro history recover                     # find the safety snapshot id
ace-neuro history restore <safety-snapshot>   # get them back
```

Branch refs never move backwards. To keep a restored state, `record` it — a
new revision whose content equals the old one, fully auditable.

## Recording pipeline runs automatically

With history enabled, pipeline runs record themselves at the two moments that
matter — approval and completion. Opt in per project in `lab_config.json`:

```json
"run": { "history": true }
```

and initialise the project directory once (`ace-neuro history init
--workspace` in the directory containing `experiments.csv`). Then each
compute/stats run:

1. records a **pre-run revision** of the exact effective parameters
   (`parameters/effective_run_params.json`),
2. writes a **result manifest** (`results/<run-id>/manifest.json`) with the
   SHA-256 checksum of every output artifact,
3. records a **post-run revision**, and links both revision ids into the
   run's `run_log.json` (`evc_pre_revision`, `evc_post_revision`).

Any figure can then be traced back to the parameters that produced it, and

```bash
ace-neuro history verify stats-20260916T092748
```

proves the run's outputs are still byte-identical to what the pipeline wrote.
A failed run records **no** revision — it appears in `recover` (op
`run-failed`), never in `history`.

With `"history"` absent or `false` (the default), pipelines behave exactly as
they always have — participation is opt-in per experiment.

## Sharing

`push` publishes history to a shared directory (a lab NAS folder, a synced
drive). Publication is append-only and fast-forward-only: if two people's
histories diverge, the second push is rejected loudly for a human to
reconcile — nothing is ever overwritten silently. Comments travel with the
push by default.

## Python API

Everything the CLI does is one call on the shared backend:

```python
from aceneurotools.evc import ExperimentVersionControl

evc = ExperimentVersionControl.open("/path/to/experiment")
evc.record("tuned gSig after reviewing projections")
for rev in evc.history():
    print(rev.oid[:12], rev.message)
report = evc.status()          # typed StatusReport, per-parameter changes
```

See the [EVC design document](../design/experiment-version-control.md) and
[implementation plan](../design/evc-implementation-plan.md) for architecture,
axioms, and roadmap (CSV bridge, Box-backed sharing, and GUI screens are
tracked there).
