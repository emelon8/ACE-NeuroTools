# Working on ACE-NeuroTools

Guidance for coding agents and contributors. ACE-NeuroTools is a public,
open-source project: everything committed here is visible to everyone.

## What counts as core

Core is the scientific processing logic. Do not edit it directly without explicit permission:

- `src/aceneurotools/pipelines/` — calcium_imaging, ephys, multimodal, compute,
  stats, postprocess_estimates
- `src/aceneurotools/calcium_imaging/` — preprocessing, motion correction,
  CNMF-E, postprocessing
- `src/aceneurotools/ephys/` — data managers, channel processing, spectrograms,
  visualizer
- `src/aceneurotools/miniscope/` — acquisition readers (UCLA, ONIX)
- `src/aceneurotools/multimodal/` — alignment, coherence/scatter statistics,
  lab and stats configuration, peri-event and related analyses

Not core; these may change more fluidly with normal review:

- `src/aceneurotools/gui/` — the `ace-gui` workbench
- Non-scientific helpers in `src/aceneurotools/shared/` (pipeline_defaults,
  config_utils, csv_worker, cli_utils, calcium_imaging_names)
- `src/aceneurotools/init.py`, `src/aceneurotools/cli.py`
- `tests/`, `docs/`, `scripts/`

## Rules

1. **Core changes need maintainer approval.** Suggesting improvements to core
   code is welcome, but never apply them directly without comprehensive review. Write a proposal as an ADR in
   `docs/adr/` with `status: proposed`, containing:
   - context, with `file:line` evidence
   - the exact diff
   - the effect on CLI and Python callers, including whether numerical results
     change
   - the tests to add
   - risks and alternatives
2. **The GUI wraps the core library.** It must not re-implement or change
   scientific behavior. It calls the public pipeline APIs, the CLI entry points
   and the shared defaults
   ([ADR 0001](docs/adr/0001-shared-gui-cli-capabilities.md)). If GUI code must
   copy a small piece of core logic, add a test that fails when the copy drifts
   from the original.
3. **CSVs are the settings source of truth**
   ([ADR 0002](docs/adr/0002-json-parameter-documents.md)): `experiments.csv`
   and `analysis_parameters.csv`. Project-wide statistics settings live in
   `lab_config.json` and `stats_config.json`. GUI edits to those files must:
   - validate with `LabConfig.from_json` / `StatsConfig.from_json`
   - preserve unknown keys
   - keep backups and reject conflicting saves, as the CSV editor does
4. **No lab-specific details in the repository.** Code, defaults, templates,
   tests and docs must not contain cluster or partition names, accounts,
   hostnames, local paths or environment names. Ask for site details where they
   are used (for example, cluster job values when exporting) and keep them out
   of the repository.
5. **Verify before reporting.** Check suspected bugs against the code and look
   for duplicate issues before filing. Report test results exactly as they are,
   including failures and anything that was skipped.
6. **Git workflow.**
   - Each workstream gets its own branch (a separate worktree is preferred) and
     one PR against `main`.
   - Maintainers merge.
   - Ask before pushing, opening PRs or filing issues.

## GUI conventions

See [src/aceneurotools/gui/README.md](src/aceneurotools/gui/README.md).

- **New screens are features.** Each one needs:
  - a `gui/<feature>.py` module defining `FEATURE = Feature(...)` (see
    `gui/routes.py`)
  - one line in `ENABLED` in `gui/features.py`
  - browser scripts that register through `aceFeatures` in `gui/features.js`
    (`addWorkspaceView`, `addPage`, `addUnsaved`, `fragment`)
- **Anything that runs or exports analyses builds on `gui/run_plan.py`.** Build
  plans only from reviewed runs (`Runs.review`), through
  `POST /api/run-plan/preview`.
- **Some analyses have no CLI equivalent.** The compute CLI requires
  `--lab-config`, but the GUI runs mean fluorescence without one, and crop and
  preprocess has no CLI. For those analyses, offer the Python call only and say
  why.

## Verification

Use a conda environment built from `conda-lock.yml`, as CI does (CaImAn is
conda-only). With micromamba/miniforge:

```sh
micromamba create -n aceneurotools -f conda-lock.yml
python -m pip install --no-deps -e .
```

Run the suite the way CI does:

```sh
MPLBACKEND=Agg QT_QPA_PLATFORM=offscreen python -m pytest tests -m "not slow" -q
```

In a git worktree, set `PYTHONPATH=<worktree>/src` so tests import the
worktree's code rather than the editable install. Check changed browser scripts
with `node --check src/aceneurotools/gui/<file>.js`.

A change is done when:

- new behavior has unit or HTTP-route tests
- parity tests cover any place the GUI reproduces a CLI or pipeline call
- the full suite passes

Representative recording validation is handled separately by the lab.
