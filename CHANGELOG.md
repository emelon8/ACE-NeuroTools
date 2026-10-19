# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Align bundled CSV example rows with their headers and allow local recording
  checks when optional Box columns are absent.
- Report a missing explicit CLI configuration as an error without launching setup.
- Apply statistics frequency overrides consistently without modifying caller
  settings; preserve condition labels in summaries and report output failures.
- Treat zero or invalid spectral power as missing in dB averages and plots,
  instead of reporting a fabricated -300 dB floor.

- Correct per-bin peri-event SEM, eigenvalue multitaper normalization, circular
  phase averages and aligned downsampling of every channel field.
- Exclude long scatter gaps and adjacent filter margins before normalization and
  regression; extend leading NaNs from the first acquired value.
- Read multimodal crops from the calcium recording; wait for workers to exit
  before reporting a successful stop, with force-kill fallback.
- Preserve CSV quoting, multiline fields, BOM and line endings when editing or
  adding columns; retain backups after rollback.

### Added

- Installed `ace-gui` workbench with per-launch API authentication and shared
  CLI/GUI defaults. CSVs remain the settings source of truth.
- A noarch conda recipe, menuinst shortcuts and native package smoke checks for
  Windows, Intel Mac, Apple silicon and Linux.
- Git-tag-derived versions and lab-first conda publishing. EVC, the Box setup
  wizard and cluster export remain separate follow-ups.

Representative recording validation is deferred by request. No pilot has been
published yet; a lab channel and scoped publishing credential must be configured.

### Added
- **Olympus edition** capabilities merged from `ace-neurotools-olympus-edition`: master CLI (`ace-neuro` console script), `python -m aceneurotools.init` project bootstrap, compute and stats pipelines (`pipelines.compute`, `pipelines.stats`), miniscope pipeline results and projections helpers, multimodal stats stack (lab config, stats config/loader, coherence, scatter, signal utilities), ephys loader, shared plotting and signal-processing helpers, and example `configs/*.json` plus `run_stats.bat` for Windows stats runs.

### Changed
- Renamed project and Python module from `ace-neuro` / `ace_neuro` to **ACE-NeuroTools** (display) and `aceneurotools` (Python module / distribution name). Source tree moved from `src/ace_neuro/` to `src/aceneurotools/`; all imports, CLI entry points (e.g. `python -m aceneurotools.pipelines.miniscope`), docs, and tutorial notebooks updated.
- Renamed the optional path-fallback environment variable from `ACE_NEURO_DATA` to `ACE_NEUROTOOLS_DATA` (hard cutover, no backward-compat shim). HPC submit scripts, shell profiles, and CI configuration that previously exported `ACE_NEURO_DATA` must be updated.
- Resolved env-var docstring contradiction in `src/aceneurotools/shared/paths.py` and `src/aceneurotools/shared/experiment_data_manager.py`: both now correctly document `ACE_NEUROTOOLS_DATA` as a last-resort default for HPC submit scripts (no `.env` lookup).
- Documentation cleanup: consistent install instructions, license/authorship placeholders, reduced duplicate README content, new `examples/` and `scripts/` helpers, expanded API reference (multimodal, ephys processors, config helpers).

## [0.1.0] - 2024-03-16

### Added
- Modern `pyproject.toml` with full dependency specification.
- `src` layout for better package isolation.
- `ace_neuro` package name.
- Integrated pipelines for Miniscope, Ephys, and Multimodal analysis.
- MkDocs documentation site.
- Automated CI for Python 3.10.

### Changed
- Reorganized source tree from `src2/` to `src/ace_neuro/`.
- Updated all internal imports to use the new package name.
- Simplified path management (removing explicit `.env` dependency).

### Removed
- Obsolete `src/` directory.
- Legacy `setup.py`.
- Stale root scripts and temporary README files.
