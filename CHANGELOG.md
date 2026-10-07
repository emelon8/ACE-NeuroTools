# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Olympus edition** capabilities merged from `ace-neurotools-olympus-edition`: master CLI (`ace-neuro` console script), `python -m aceneurotools.init` project bootstrap, compute and stats pipelines (`pipelines.compute`, `pipelines.stats`), miniscope pipeline results and projections helpers, multimodal stats stack (lab config, stats config/loader, coherence, scatter, signal utilities), ephys loader, shared plotting and signal-processing helpers, and example `configs/*.json` plus `run_stats.bat` for Windows stats runs.

### Changed
- Updated repository links to `emelon8/ACE-NeuroTools`, clarified the README workflow and alpha status, and added contributor instructions.
- Standardized Python and notebook formatting, cleared the Ruff backlog, and made lint and formatting required CI checks.
- Corrected the jitter-bound regression test to assert on the function result and made the Box authentication template test independent of string quote style.
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
