# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — experiment version control prototype (Comenius F07 / decisions D07–D08)
- New `aceneurotools.evc` subpackage: git-like version control for experiment parameters
  and result manifests, modeled on git's verified internals (Pro Git §10: content-addressed
  `<type> <size>\0<body>` objects, blob/tree/commit model, refs + symbolic HEAD,
  reflog-style journal), with documented deviations: SHA-256 ids (git's own transition
  target), text tree serialization, no index/packfiles/merge in v1. Modular OO layers:
  `objects` → `store` → `refs` → `repository` (plumbing) → `worktree`/`diff`/`remote` →
  `porcelain` (axiomatic commands: `record`, `status`, `history`, `show`, `diff`,
  `restore`, `comment`, `recover`, `push`). Invariants: immutable integrity-checked
  objects; every ref move journaled; `restore` never destroys (dirty state auto-preserved
  as a journal-reachable safety snapshot) and never rewinds refs; comments annotate via a
  notes ref without rewriting history; push is fast-forward-only. CLI:
  `python -m aceneurotools.evc`. Pure standard library. Design doc:
  `docs/design/experiment-version-control.md`; 35 tests in `tests/test_evc_*.py`.

### Changed — package reorganization (pre-refactor cleanup)
- **New `aceneurotools.config` subpackage** for all user-editable configuration loading. `lab_config.py` and `stats_config.py` moved out of `multimodal/`; `config_utils.py` moved out of `shared/`. Update imports: `aceneurotools.multimodal.lab_config` → `aceneurotools.config.lab_config`, `aceneurotools.multimodal.stats_config` → `aceneurotools.config.stats_config`, `aceneurotools.shared.config_utils` → `aceneurotools.config.config_utils`.
- **New `aceneurotools.stats` subpackage** holding the statistical engines and modular toolbox previously in `multimodal/`: `coherence_analysis`, `scatter_analysis`, `signal_utils`, `surrogate`, `wavelets`, `oscillatory_events`, `event_correlograms`, `perievent`, and `stats_loader` (renamed to `stats.loader`). Update imports: `aceneurotools.multimodal.<module>` → `aceneurotools.stats.<module>`; `aceneurotools.multimodal.stats_loader` → `aceneurotools.stats.loader`. The toolbox re-exports moved from `aceneurotools.multimodal` to `aceneurotools.stats` (e.g. `from aceneurotools.stats import permutation_test`).
- **`aceneurotools.multimodal` now contains only cross-modal work**: `alignment` (renamed from `miniscope_ephys_alignment_utils`), `phase_utils`, and `calcium_ephys_visualizer`.
- **`shared/misc_functions.py` dissolved** into purpose-named homes: plot helpers → `shared.plotting` (`prep_axes`, `plot_spectrogram`, `mark_events`; pyplot imported lazily to preserve the `set_backend` contract); `update_csv_cell` / `append_row_csv` → `shared.csv_worker`; `z_score` / `thresh_func` → `shared.signal_processing`; `load_obj` → new `shared.file_io`; FFT movie denoising stack (`denoise_movie` + helpers) → new `miniscope.video_denoising`; `import_video_as_numpy_array` → `miniscope.movie_io`; quaternion → Euler helpers → new `miniscope.head_orientation`; `get_coords_dict_from_analysis_params` → `config.config_utils`; deprecated `spike_trig_avg` → `stats.perievent` (legacy section).
- `MiniscopeDataManager.create()` now registers its built-in subclasses itself (lazy import inside the factory). Previously the registry was only populated as an import side effect of the stats loader, so `create()` failed if that module had not been imported first.
- Personal/one-off scripts moved out of the installed package: `ephys/script.py` → `scripts/ephys_quicklook.py`, `ephys/import_agent_analyzer.py` → `scripts/import_agent_analyzer.py`. Legacy Olympus reference configs moved from `configs/` to `examples/configs/`.

### Removed
- Dead code deleted during the reorganization: `_correct_tCaIm` and the unused TTL label constants in the alignment module (superseded by `UCLADataManager.sync_timestamps`), the `misc_functions` copies of `filter_data` and `_find_file_paths` (canonical implementations live in `shared.signal_processing` / `shared.path_finder`), and the orphan helpers `_calc_num_minus_mean`, `_comp_v_thresh`, `_find_step_index`.

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
