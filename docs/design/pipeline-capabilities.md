# Scientific pipeline capability inventory

Initial source audit: 2026-10-03; integration status updated 2026-10-06. This inventories the checked-out implementation, not features proven to work in the GUI. Source references use GitHub repository links and line anchors; guide links resolve within the documentation site. Pipeline and public scientific API signatures below were initially extracted from Python syntax without importing the scientific stack. CLI, initialization, general project utilities and EVC have a separate audit scope.

## Current integration status

The [experiment GUI](../guides/experiment_gui.md) reads existing metadata and parameter files,
exposes labeled editable fields and Box links, and saves selected rows through the
existing write helpers with backups. It reuses `CSVWorker` for an optional
interpreted view. The earlier prototype and simulated setup/history/run controls
have been removed. October 5 update: global Box account/folder verification and confirmed, cancellable recording downloads with file selection, embedded
crop editing, and reviewed single-experiment compute, movie preprocessing, miniscope,
and single-channel ephys runs are connected through an additive wrapper. Runs keep
private input copies, logs, and outputs. Real compute/preprocessing fixture runs passed;
live account reconnection also passed. Full CNMF-E/ephys runs on researcher recordings
and live Box recording downloads remain unverified.
Embedded neuron selection now loads saved CNMF estimates, autosaves review decisions,
and exports curated copies using CaImAn's existing selection/save APIs. Real fitted
fixture load/select/save and browser controls are verified; researcher estimates
remain to be validated. Finish review can now recompute calcium events from saved
curated estimates, preserving original IDs and source/curation provenance. Worker
exports now have an explicit output inventory, including dictionary-shaped events,
component IDs, unfiltered/filtered signals, sparse footprints, and available quality
diagnostics. Headless execution respects `inline` after an approved source fix.
Automatic downstream continuation after curation, EVC/Git, batch, multimodal, and statistics integration
remain future work. This inventory remains the full parity checklist.

On this audit's default `/usr/sbin/python`, `find_spec` could not locate numpy, scipy, matplotlib, pandas, caiman, cv2, neo, FreeSimpleGUI, h5py or pytest. This is an interpreter-specific check, not evidence that another configured environment is absent. The runner must select and verify the intended environment. Dependencies and Python >=3.10 are declared in [pyproject.toml](https://github.com/emelon8/experiment_analysis/blob/main/pyproject.toml#L1); a [Conda environment](https://github.com/emelon8/experiment_analysis/blob/main/linux_environment.yml#L1) is also provided. Real-data validation remains required.

Parent audit update: an existing Python 3.10 environment was found at
`/home/reedpen/.conda/envs/caiman`, with the above scientific packages discoverable.
Actual scientific imports and small compute/preprocessing recording runs were verified
on October 5. Researcher-data execution still needs verification. The user wants the
first working frontend to read `experiments.csv`, resolve its Box links, read/save
compatible parameters in `analysis_parameters.csv`, and run from those records.
See the [dated roadmap](project-roadmap-2026-10-03.md) for this CSV/Box contract.

## Workflow surfaces and results

| Workflow | Researcher controls | Outputs and caveats |
|---|---|---|
| Miniscope | Choose recording files; crop; detrend; normalize; motion correction; CNMF-E; review components; detect events; phase/filter/spectrogram; stage settings and CaImAn settings | `preprocessing_result`, `processing_result`, `postprocessing_result` and live data manager. Saved preprocessed movie, optional HDF5 estimates and JSON CaImAn options. The GUI explicitly exports numeric signals/projections, events, component IDs/footprints, and available diagnostics; review can create separate curated estimates/events. [Pipeline](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L56), [result types](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L23), [GUI export contract](https://github.com/emelon8/experiment_analysis/blob/main/gui/run_outputs.py). |
| Electrophysiology | One selected channel, multiple selected channels, or all metadata channels; artifact removal; filter; phase; signal, spectrogram and phase views | Loaded/processed channels in `ephys_data_manager`; pipeline does not produce a run artifact manifest. Multi-channel method loads block once. All-channel plotting has separate behavior and must be tested under embedded/headless execution. [Pipeline](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/ephys.py#L40). |
| Multimodal | All ephys/miniscope controls plus TTL removal, gap repair, experiment-event filtering, TTL and calcium-event mapping | Aligned calcium times, low-confidence periods, TTL/ephys/frame mappings, event phases and histograms, plus both subpipelines. `time_range` is accepted but unused inside `run`; do not advertise an effective time-range control here. [Pipeline](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/multimodal.py#L60). |
| Mean fluorescence | Project, raw-data root, subjects, output directory, saved/new crop, verbosity | `{line_num: Path}` and `meanFluorescence_<line>.npz`, key `meanFluorescence`. Existing output is skipped; per-subject failures are printed and skipped. GUI needs explicit existing-output policy and visible skipped reasons; do not claim a force-recompute flag exists. [Compute](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/compute.py#L17). |
| Study statistics | Subject/condition selection, channel pair, frequency range, control/treatment windows, three analysis choices, algorithm config, output paths | `coherence_ephys_calcium`, `coherence_ephys_ephys`, `scatter_correlation`; per-analysis/per-subject output folders; condition-level coherence CSVs, scatter/hexbin/violin/summary figures; run log with completed/skipped subjects. Missing/empty analyses opens a terminal menu, so a GUI must always pass explicit selections. [Statistics](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/stats.py#L25), [coherence](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L67), [scatter](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L833). |

Batch controls are necessary for compute/statistics, not only a single experiment Run button. Ephys and miniscope API defaults differ from their script defaults (see signature appendix and module `__main__` blocks). For example miniscope API defaults `run_CNMFE=False`, motion correction off, 12 workers, median detrending; its module CLI uses extraction on, 6 workers, no detrending and parallel execution. Preserve the selected workflow's effective settings instead of silently treating one default set as universal. [Miniscope API](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L56), [CLI defaults](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L394).

## Current GUI output contract

Supported GUI runs write `output-inventory.json` with the effective parameters
and one entry per declared product. Exported numeric entries identify the file,
NPZ key, shape, and dtype; unavailable products have `status: not_computed` and a
reason. Serialization failures fail the worker instead of reporting success after
silently dropping a computed result. [Exporter](https://github.com/emelon8/experiment_analysis/blob/main/gui/run_outputs.py).

| Miniscope artifact | Content |
| --- | --- |
| `postprocessing.npz` | Component traces `C`, optional `S`/`F_dff`/`YrA` and background arrays, zero-based `neuron_ids`, final/original/filtered temporal projections, spatial projections, frame rate/timing, phases, and spectra when available |
| `calcium-events.json` | Dictionary-shaped event indices, component IDs, derivative/threshold settings, frame rate, trace source, and index convention |
| `components.npz` | Sparse CSC footprint arrays `A_data`, `A_indices`, `A_indptr`, `A_shape` |
| `diagnostics.npz` | Available CaImAn quality/selection/noise/AR arrays, including `SNR_comp`, `r_values`, and component keep/bad indices |
| `diagnostics.json` | Effective settings, unavailable products, neuron count, requested `inline`, actual projection replacement, and phase/spectrum input semantics |

The inventory also records saved estimates, movie outputs, CaImAn parameters,
effective settings, and the run log when available. Correlation/PNR interactive
plot diagnostics are not computed in GUI runs, and the core pipeline does not
retain motion-correction shifts; both have explicit unavailable reasons.
This contract covers supported GUI workflows, not every lower-level API output.

## Same-workspace crop and component review seam

The following records core behavior and the proposed automatic checkpoint.
Current GUI curation loads saved estimates after the run and offers an explicit
calcium-event rerun; it does not implement the pause/resume seam in items 3–4.

1. Load the selected real recording through `MiniscopeDataManager.create`; expose the canonical max/min/mean/median/standard-deviation/range projections. Crop review occurs in `MiniscopePreprocessor.get_crop_coordinates`. Its legacy interactive path always opens `crop_gui`, even when coordinates exist. Its headless path uses explicit/saved coordinates and otherwise skips cropping. A compatible optional review callback can receive projection arrays, dimensions and initial coordinates and return coordinates or a defined cancellation result; absent the callback, retain current behavior. [Preprocessor](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L118).
2. Crop coordinates are `(x0, y0, x1, y1)` in bottom-left GUI space. The crop operation flips y into NumPy top-left space. Browser coordinates must be transformed once and tested against an asymmetric fixture. Successful pipeline cropping writes `analysis_parameters.csv`; preserve that existing effect and record it in history. [Crop conversion](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L157), [persistence](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L248).
3. Component review occurs after extraction and before event detection inside `postprocess_calcium_movie`. An optional review callback at that exact point is the smallest additive seam; it should provide real footprints, projection background, traces, stable component IDs and initial rejection state, and receive kept/rejected IDs. Validate bounds and apply `estimates.select_components(idx_components=kept)`; support both in-place/None and returned-object CaImAn versions, as the existing GUI does. [Postprocessor](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L102), [selection](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/gui_utils.py#L239).
4. The worker must pause without blocking the app, resume only the matching run/review token, and distinguish cancel from accept. Persist decisions against the run and uncurated estimate identity, not display numbering. The existing GUI displays 1-based IDs and internally uses 0-based IDs. [Component GUI](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/gui_utils.py#L153).
5. Saved estimates currently precede component review. A GUI must persist curation separately or deliberately save curated estimates after review; otherwise the displayed selection and saved scientific result diverge. [Processing save order](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L135).
6. `headless=True` disables component review, motion inspection, and parameter plots while preserving the selected `inline` setting. Filtering runs when enabled; `inline=True` replaces the final temporal projection with filtered data, while `False` retains the original. The miniscope CLI defaults to `True`; direct pipeline API defaults to `False`. Existing headless callers wanting the former projection behavior must set `inline=False` explicitly. Phases/spectra still run before filtering, and events use `C`; their input semantics are unchanged. An automatic review checkpoint still needs an interaction/stage adapter. [Headless policy](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L167), [CLI policy](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/shared/cli_utils.py#L133), [postprocessing order](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L102).

Additional windows to replace with embedded results: detrend plots; CNMF-E correlation/PNR and patch inspection; motion shifts/correlation/advanced diagnostics and side-by-side playback; component contour plots; calcium spectrograms; ephys signal/spectrogram/phase plots; phase-event histograms; calcium/ephys synchronized animation; optional coherence overview/coherogram/spectrogram; scatter/hexbin/population charts; analog-gas plots. These are implementation behaviors, not just crop/selection dialogs. [Preprocessor](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L187), [processor inspection](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L205), [postprocessor](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L117), [ephys visualizer](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/visualizer.py#L26), [multimodal animation](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/calcium_ephys_visualizer.py#L18).

## Configuration coverage

- Experiment analysis CSV mapping has aliases `filter_data → filter_miniscope_data`, `spectrogram → compute_miniscope_spectrogram`, `method → df_over_f_method`; None values are skipped. The mapping is an allowlist and omits some genuine pipeline args (including `crop` and multimodal-specific options). A GUI must distinguish persisted source settings from effective run arguments instead of assuming this parser round-trips everything. [Parser](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/shared/config_utils.py#L60).
- Miniscope's full CaImAn options are loaded separately from raw analysis parameters, through groups `data`, `patch`, `preprocess`, `init`, `spatial`, `temporal`, `merging`, `quality`, `online`, `motion`, `ring_CNN`. This is a materially larger surface than the pipeline signature. Maintain an advanced typed editor while keeping the common form approachable. Movie filename/dimensions/frame rate are set by runtime data; CaImAn supplies defaults for unspecified options. [Group map](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L20), [loading](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L500).
- `LabConfig` owns primary/secondary channel, frequency range, condition membership with drug flag, subject control/treatment windows (minutes), paths and run defaults. JSON loading aggregates validation errors; each subject must have windows and cannot belong to multiple conditions. Present errors next to fields. [LabConfig](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L45).
- `StatsConfig` includes filter/edge trim, normalization, autocorrelation correction, confidence, bootstrap/paired tests/minimum subjects, Welch window, coherogram, spectrogram, plot formats and resolution. Actual defaults appear below. `StudyMetadata.default()` intentionally raises; the GUI must build a real study from lab configuration. [StatsConfig](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L14), [study requirement](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L148).

## Scientific capabilities beyond the five pipelines

| Modules | Researcher-facing capability / GUI destination |
|---|---|
| `miniscope_data_manager`, `ucla_data_manager`, `onix_miniscope_data_manager`, `movie_io` | Recording-format detection, metadata/timestamp import/synchronization, convert/join videos and metadata, save/load movies. Data management and conversion actions. Factory/serialization internals need no separate button. |
| `miniscope_preprocessor`, `projections` | Crop, median/linear detrend, two DF/F variants, seven projections (six spatial plus mean temporal). Individual stage execution/preview should be available without running extraction. |
| `miniscope_processor` | Motion correction, CNMF-E, parameter diagnostics, full motion inspection, save/reload result paths. Cluster cleanup and memory-map internals are worker maintenance. |
| `miniscope_postprocessor`, `filtered_miniscope_data`, `gui_utils` | Component quality evaluation (SNR/spatial-correlation thresholds), deconvolution and derivative event methods, Hilbert phase, filtering, multitaper spectrogram, reconstructed component movies with/without background, curation and crop. Deconvolution/quality/reconstruction are not exposed by the high-level `run` arguments. |
| `pipeline_results` | Typed stage configs and output objects; implementation contracts, not separate researcher actions. |
| `ephys_data_manager`, `neuralynx_data_manager`, `rhs2116_data_manager`, `ephys_loader`, `block_processor` | Neuralynx/RHS format support, select channels, synchronize, artifact removal with configurable voltage/time/Hann thresholds at lower level, filter with order/type/band/cutoff/in-place choice, phase; RHS supports maximum sample limit. Expose meaningful load/cleanup/filter choices; keep block mechanics internal. |
| `channel`, `spectrogram`, `channel_worker`, `visualizer`, `script` | Signal/events/spectrogram models and viewers; spectrogram window/step/frequency/time-bandwidth/event overlays; quick-look CLI duplicates these views. Data classes need no separate screen. |
| `import_agent_analyzer` | ONIX analog recording import/inspection: O2, CO2, anesthetic concentration and hardware buffer plots. Legacy script relies on working-directory naming and a suffix prompt, so adaptation needs folder/suffix fields. |
| `miniscope_ephys_alignment_utils`, `phase_utils` | TTL cleanup/repair/alignment, confidence, frame/sample/file mapping; event phase by selected neurons; histogram bins/range/density/combined/mean-density controls beyond pipeline defaults. |
| `calcium_ephys_visualizer` | Synchronized movie + calcium/ephys traces; time segment/movie number, crop, normalization, intensity limits, systemic-event marker, trace length, timestamps, playback interval; play/save MP4. |
| `coherence_analysis`, `scatter_analysis`, `stats_loader`, `signal_utils` | Study analyses plus optional coherogram/spectrogram/signal-overview; subject/population exports; scatter and hexbin plots; effective sample size, robust Pearson stats, Fisher CI, Cohen d, bootstrap, paired tests; signal slicing/filtering/NaN gap handling, global normalization, envelope, spectral power, coherence/correlation, filter response and mutual information. Some lower-level numeric helpers support workflows rather than needing standalone buttons, but mutual information/filter response/envelope are additional scientific tools. |
| `event_correlograms` | Auto/cross/event correlograms and inter-event interval distributions; bin/window/normalization/support/reverse/log settings. Not wired into high-level pipelines. |
| `perievent` | Per-event segments, event-triggered and spike-triggered averages; window/support/boundary policies. Not wired into high-level pipelines. |
| `oscillatory_events` | Detect band-limited events with frequency/threshold/duration/minimum interval/filter/smoothing controls. Not wired into high-level pipelines. |
| `wavelets` | Morlet filter bank and transform with frequency bank, sampling rate, Gaussian width, window length, precision and normalization. Not wired into high-level pipelines. |
| `surrogate` | Permutation tests and event-time jitter/shift/interval-shuffle/resampling; count, tails, reproducible RNG, workers and support options. `permutation_test` accepts a callable: GUI needs explicit supported statistic recipes rather than arbitrary user code. |
| `lab_config`, `stats_config` | Project/study configuration described above. `__init__.py` files only package exports, with no independent researcher workflow. |

The public-symbol appendix accounts for every module in these three scientific packages, including data classes and infrastructure helpers. “Everything in the code” should mean all researcher workflows and settings, with implementation plumbing represented by reliable application behavior rather than arbitrary Python execution.

## Pipeline signatures (API defaults)

### compute

[compute.py:24](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/compute.py#L24)

```python
ComputePipeline.run(self, project_path: str | Path, lab_config: LabConfig, calcium_signal_dir: str | Path, data_path: str | Path | None=None, line_nums: list[int] | None=None, headless: bool=False, verbose: bool=False)
```

### ephys

[ephys.py:42](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/ephys.py#L42)

```python
EphysPipeline.run(self, line_num: int, project_path: str | Path | None=None, data_path: str | Path | None=None, channel_name: str='PFCLFPvsCBEEG', remove_artifacts: bool=False, filter_type: str | None=None, filter_range: list[float]=[0.5, 4], compute_phases: bool=False, plot_channel: bool=False, plot_spectrogram: bool=False, plot_phases: bool=False, logging_level: str | int='CRITICAL', headless: bool=False)
```

[ephys.py:145](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/ephys.py#L145)

```python
EphysPipeline.run_all_channels(self, line_num: int, project_path: str | Path | None=None, data_path: str | Path | None=None, remove_artifacts: bool=False, filter_type: str | None=None, filter_range: list[float]=[0.5, 4], plot_channel: bool=False, plot_spectrogram: bool=False, logging_level: str | int='CRITICAL', headless: bool=False)
```

[ephys.py:226](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/ephys.py#L226)

```python
EphysPipeline.run_multiple_channels(self, line_num: int, channel_names: list[str], project_path: str | Path | None=None, data_path: str | Path | None=None, remove_artifacts: bool=False, filter_type: str | None=None, filter_range: list[float]=[0.5, 4], logging_level: str | int='CRITICAL', headless: bool=False)
```

### miniscope

[miniscope.py:62](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L62)

```python
MiniscopePipeline.run(self, line_num: int, project_path: str | Path | None=None, data_path: str | Path | None=None, filenames: list[str]=[], crop: bool=True, crop_coords: list[int] | tuple[int, int, int, int] | None=None, detrend_method: str | None='median', df_over_f: bool=False, secs_window: float=5, quantile_min: float=8, df_over_f_method: str='delta_f_over_sqrt_f', parallel: bool=False, n_processes: int=12, apply_motion_correction: bool=False, inspect_motion_correction: bool=False, plot_params: bool=False, run_CNMFE: bool=False, save_estimates: bool=True, save_CNMFE_estimates_filename: str='estimates.hdf5', save_CNMFE_params: bool=False, remove_components_with_gui: bool=True, find_calcium_events: bool=True, derivative_for_estimates: str='first', event_height: float=5, compute_miniscope_phase: bool=True, filter_miniscope_data: bool=True, n: int=2, cut: list[float]=[0.1, 1.5], ftype: str='butter', btype: str='bandpass', inline: bool=False, compute_miniscope_spectrogram: bool=True, window_length: float=30, window_step: float=3, freq_lims: list[float]=[0, 15], time_bandwidth: float=2, headless: bool=False)
```

[miniscope.py:310](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/miniscope.py#L310)

```python
MiniscopePipeline.run_with_configs(self, line_num: int, preprocess: PreprocessConfig, process: ProcessConfig, postprocess: PostprocessConfig, project_path: str | Path | None=None, data_path: str | Path | None=None, filenames: list[str]=[], headless: bool=False)
```

### multimodal

[multimodal.py:64](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/multimodal.py#L64)

```python
MultimodalPipeline.run(self, line_num: int, project_path: str | Path | None=None, data_path: str | Path | None=None, channel_name: str='PFCLFPvsCBEEG', remove_artifacts: bool=False, filter_type: str | None=None, filter_range: list[float]=[0.5, 4], plot_channel: bool=False, plot_spectrogram: bool=False, plot_phases: bool=False, logging_level: str='CRITICAL', miniscope_filenames: list[str]=[], crop: bool=True, crop_coords: list[int] | tuple[int, int, int, int] | None=None, detrend_method: str='median', df_over_f: bool=False, secs_window: float=5, quantile_min: float=8, df_over_f_method: str='delta_f_over_sqrt_f', parallel: bool=False, n_processes: int=6, apply_motion_correction: bool=True, inspect_motion_correction: bool=True, plot_params: bool=False, run_CNMFE: bool=True, save_estimates: bool=True, save_CNMFE_estimates_filename: str='estimates.hdf5', save_CNMFE_params: bool=False, remove_components_with_gui: bool=True, find_calcium_events: bool=True, derivative_for_estimates: str='first', event_height: float=5, compute_miniscope_phase: bool=True, filter_miniscope_data: bool=True, n: int=2, cut: list[float]=[0.1, 1.5], ftype: str='butter', btype: str='bandpass', inline: bool=False, compute_miniscope_spectrogram: bool=True, window_length: float=30, window_step: float=3, freq_lims: list[float]=[0, 15], time_bandwidth: float=2, delete_TTLs: bool=True, fix_TTL_gaps: bool=False, only_experiment_events: bool=True, all_TTL_events: bool=True, ca_events: bool=False, time_range: list[float] | None=None, headless: bool=False)
```

### stats

[stats.py:121](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/pipelines/stats.py#L121)

```python
StatsPipeline.run(self, project_path: str | Path, data_path: str | Path | None=None, output_dir: str | Path | None=None, calcium_signal_dir: str | Path | None=None, analyses: list[str] | None=None, line_nums: list[int] | None=None, channel: str | None=None, channel_2: str | None=None, freq_range: list[float] | None=None, stats_config: StatsConfig | None=None, study_metadata: StudyMetadata | None=None, lab_config: LabConfig | None=None, headless: bool=False, verbose: bool=False, run_log_path: str | Path | None=None, lab_config_path: str | Path | None=None, stats_config_path: str | Path | None=None)
```

## Configuration fields and defaults

### PreprocessingResult

[pipeline_results.py:23](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L23)

| Field | Type | Default |
|---|---|---|
| `preprocessed_movie_filepath` | `str &#124; None` | `required` |
| `coords` | `dict[str, int] &#124; None` | `required` |

### ProcessingResult

[pipeline_results.py:40](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L40)

| Field | Type | Default |
|---|---|---|
| `CNMFE_obj` | `Any` | `required` |
| `estimates_filepath` | `str &#124; None` | `required` |
| `opts_caiman_filepath` | `str &#124; None` | `required` |
| `opts_caiman` | `Any` | `required` |
| `motion_corrected_movie_filepath` | `str &#124; None` | `required` |

### PostprocessingResult

[pipeline_results.py:60](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L60)

| Field | Type | Default |
|---|---|---|
| `projections` | `Any` | `required` |
| `ca_events_idx` | `Any` | `required` |
| `PSD_spect` | `np.ndarray &#124; None` | `required` |
| `t_spect` | `np.ndarray &#124; None` | `required` |
| `freqs_spect` | `np.ndarray &#124; None` | `required` |
| `p_spect` | `np.ndarray &#124; None` | `required` |
| `miniscope_phases` | `np.ndarray &#124; None` | `required` |
| `filter_object` | `Any` | `required` |

### PreprocessConfig

[pipeline_results.py:91](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L91)

| Field | Type | Default |
|---|---|---|
| `crop` | `bool` | `True` |
| `crop_coords` | `Any &#124; None` | `None` |
| `detrend_method` | `str &#124; None` | `'median'` |
| `df_over_f` | `bool` | `False` |
| `secs_window` | `float` | `5` |
| `quantile_min` | `float` | `8` |
| `df_over_f_method` | `str` | `'delta_f_over_sqrt_f'` |

### ProcessConfig

[pipeline_results.py:116](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L116)

| Field | Type | Default |
|---|---|---|
| `parallel` | `bool` | `False` |
| `n_processes` | `int` | `12` |
| `apply_motion_correction` | `bool` | `False` |
| `inspect_motion_correction` | `bool` | `False` |
| `plot_params` | `bool` | `False` |
| `run_CNMFE` | `bool` | `False` |
| `save_estimates` | `bool` | `True` |
| `save_CNMFE_estimates_filename` | `str` | `'estimates.hdf5'` |
| `save_CNMFE_params` | `bool` | `False` |

### PostprocessConfig

[pipeline_results.py:145](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L145)

| Field | Type | Default |
|---|---|---|
| `remove_components_with_gui` | `bool` | `True` |
| `find_calcium_events` | `bool` | `True` |
| `derivative_for_estimates` | `str` | `'first'` |
| `event_height` | `float` | `5` |
| `compute_miniscope_phase` | `bool` | `True` |
| `filter_miniscope_data` | `bool` | `True` |
| `n` | `int` | `2` |
| `cut` | `list[float]` | `field(default_factory=lambda: [0.1, 1.5])` |
| `ftype` | `str` | `'butter'` |
| `btype` | `str` | `'bandpass'` |
| `inline` | `bool` | `False` |
| `compute_miniscope_spectrogram` | `bool` | `True` |
| `window_length` | `float` | `30` |
| `window_step` | `float` | `3` |
| `freq_lims` | `list[float]` | `field(default_factory=lambda: [0, 15])` |
| `time_bandwidth` | `float` | `2` |

### ConditionSpec

[lab_config.py:16](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L16)

| Field | Type | Default |
|---|---|---|
| `subjects` | `list[int]` | `required` |
| `is_drug` | `bool` | `required` |

### PathsConfig

[lab_config.py:24](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L24)

| Field | Type | Default |
|---|---|---|
| `project_path` | `str` | `required` |
| `data_path` | `str &#124; None` | `None` |
| `output_dir` | `str &#124; None` | `None` |
| `calcium_signal_dir` | `str &#124; None` | `None` |

### RunConfig

[lab_config.py:34](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L34)

| Field | Type | Default |
|---|---|---|
| `mode` | `str` | `'all'` |
| `analyses` | `list[str] &#124; None` | `None` |
| `line_nums` | `list[int] &#124; None` | `None` |
| `headless` | `bool` | `False` |
| `verbose` | `bool` | `False` |

### LabConfig

[lab_config.py:45](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L45)

| Field | Type | Default |
|---|---|---|
| `primary_channel` | `str` | `required` |
| `freq_range` | `list[float]` | `required` |
| `conditions` | `dict[str, ConditionSpec]` | `required` |
| `time_windows` | `dict[int, list[list[float]]]` | `required` |
| `secondary_channel` | `str &#124; None` | `None` |
| `paths` | `PathsConfig &#124; None` | `None` |
| `run` | `RunConfig &#124; None` | `None` |

### StatsConfig

[stats_config.py:14](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L14)

| Field | Type | Default |
|---|---|---|
| `lowcut` | `float` | `0.5` |
| `highcut` | `float` | `4.0` |
| `filter_order` | `int` | `2` |
| `edge_trim_seconds` | `float` | `5.0` |
| `normalization_method` | `str` | `'zscore'` |
| `global_normalization` | `bool` | `True` |
| `correct_autocorrelation` | `bool` | `True` |
| `confidence_level` | `float` | `0.95` |
| `max_acf_lags` | `int` | `100` |
| `bootstrap_iterations` | `int` | `10000` |
| `paired_test` | `str` | `'wilcoxon'` |
| `min_subjects_for_stats` | `int` | `4` |
| `coherence_nperseg_seconds` | `float &#124; None` | `None` |
| `coherogram_window_length` | `float` | `5.0` |
| `coherogram_window_step` | `float` | `2.5` |
| `coherogram_nrolling` | `int` | `8` |
| `spectrogram_window_length` | `float` | `60.0` |
| `spectrogram_window_step` | `float` | `3.0` |
| `spectrogram_time_bandwidth` | `float` | `2.0` |
| `spectrogram_freq_lims` | `list[float]` | `field(default_factory=lambda: [0.0, 20.0])` |
| `plot_formats` | `list[str]` | `field(default_factory=lambda: ['svg', 'tiff'])` |
| `color_dpi` | `int` | `300` |
| `headless` | `bool` | `False` |

## Public scientific API appendix

Exact signatures identify all adjustable lower-level parameters. Underscore-prefixed implementation helpers are omitted; constructors are included because they define researcher-facing data-loading/configuration choices. The class/function docstring summary describes the implementation intent, not execution verification.

### `miniscope/__init__.py`

Package exports only.


### `miniscope/filtered_miniscope_data.py`

Class `FilterMiniscopeData` — [filtered_miniscope_data.py:9](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/filtered_miniscope_data.py#L9). Container for filtered miniscope projection data.

- [filtered_miniscope_data.py:32](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/filtered_miniscope_data.py#L32) `FilterMiniscopeData.__init__(self, projections: Projections, frame_rate: float, n: int=2, cut: float | list[float]=[0.1, 1.5], ftype: str='butter', btype: str='bandpass')`
- [filtered_miniscope_data.py:61](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/filtered_miniscope_data.py#L61) `FilterMiniscopeData.filter_miniscope_data(self)`

### `miniscope/gui_utils.py`

- [gui_utils.py:153](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/gui_utils.py#L153) `component_gui(movie, estimates, projections)`
- [gui_utils.py:265](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/gui_utils.py#L265) `crop_gui(coords_dict, projections: Projections, movie_height, movie_width, previous_coords=None)`

### `miniscope/miniscope_data_manager.py`

Class `MiniscopeDataManager` — [miniscope_data_manager.py:17](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L17). Manages raw Miniscope data import and storage.

- [miniscope_data_manager.py:64](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L64) `MiniscopeDataManager.create(cls: type[T], line_num: int, project_path: str | Path | None=None, data_path: str | Path | None=None, **kwargs: Any)`
- [miniscope_data_manager.py:104](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L104) `MiniscopeDataManager.can_handle(cls, directory: str | Path)`
- [miniscope_data_manager.py:108](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L108) `MiniscopeDataManager.__init__(self, line_num: int, project_path: str | Path | None=None, data_path: str | Path | None=None, filenames: list[str]=[], auto_import_data: bool=True)`
- [miniscope_data_manager.py:163](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L163) `MiniscopeDataManager.load_attributes(self, filepaths: list[str | Path])`
- [miniscope_data_manager.py:182](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L182) `MiniscopeDataManager.sync_timestamps(self, ephys_dm: Any | None=None, channel_name: str | None=None, **kwargs: Any)`
- [miniscope_data_manager.py:202](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_data_manager.py#L202) `MiniscopeDataManager.convert_ca_movies(self, filenames: list[str] | None=None, new_file_type: str='.tif', join_movies: bool=False, metadata_convert: bool=True)`

### `miniscope/miniscope_postprocessor.py`

Class `MiniscopePostprocessor` — [miniscope_postprocessor.py:21](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L21). Post-processor for CNMF-E extracted calcium imaging components.

- [miniscope_postprocessor.py:38](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L38) `MiniscopePostprocessor.__init__(self, data_manager: 'MiniscopeDataManager')`
- [miniscope_postprocessor.py:52](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L52) `MiniscopePostprocessor.postprocess_calcium_movie(self, remove_components_with_gui: bool=True, find_calcium_events: bool=True, derivative_for_estimates: str='first', event_height: float=5, compute_miniscope_phase: bool=True, filter_miniscope_data: bool=True, n: int=2, cut: list[float]=[0.1, 1.5], ftype: str='butter', btype: str='bandpass', inline: bool=False, compute_miniscope_spectrogram: bool=True, window_length: float=30, window_step: float=3, freq_lims: list[float]=[0, 15], time_bandwidth: float=2)`
- [miniscope_postprocessor.py:148](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L148) `MiniscopePostprocessor.compute_projections(self, movie: cm.movie | None=None)`
- [miniscope_postprocessor.py:166](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L166) `MiniscopePostprocessor.evaluate_components(self, estimates: 'Estimates', opts_caiman: 'CNMFParams', min_SNR: float=3, r_values_min: float=0.85)`
- [miniscope_postprocessor.py:196](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L196) `MiniscopePostprocessor.find_calcium_events_with_deconvolution(self, estimates: 'Estimates', opts_caiman: 'CNMFParams', dview: Any, dff_flag: bool=False)`
- [miniscope_postprocessor.py:229](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L229) `MiniscopePostprocessor.find_calcium_events_with_derivatives(estimates: 'Estimates', derivative: str='first', event_height: float=5) -> dict[int, np.ndarray]` — static method; usable on saved curated estimates without constructing a postprocessor.
- [miniscope_postprocessor.py:275](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L275) `MiniscopePostprocessor.compute_miniscope_spectrogram(data: np.ndarray, frame_rate: float, window_length: float=30, window_step: float=3, freq_lims: list[float]=[0, 15], time_bandwidth: float=2, plot_spectrogram: bool=True)`
- [miniscope_postprocessor.py:328](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L328) `MiniscopePostprocessor.compute_miniscope_phase(self, data: np.ndarray)`
- [miniscope_postprocessor.py:341](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L341) `MiniscopePostprocessor.calculate_component_movie(self, dm: 'MiniscopeDataManager')`
- [miniscope_postprocessor.py:360](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_postprocessor.py#L360) `MiniscopePostprocessor.calculate_black_component_movie(self, dm: 'MiniscopeDataManager')`

### `miniscope/miniscope_preprocessor.py`

Class `MiniscopePreprocessor` — [miniscope_preprocessor.py:21](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L21). Preprocessor for calcium imaging movies before CNMF-E analysis.

- [miniscope_preprocessor.py:36](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L36) `MiniscopePreprocessor.__init__(self, data_manager: 'MiniscopeDataManager')`
- [miniscope_preprocessor.py:46](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L46) `MiniscopePreprocessor.preprocess_calcium_movie(self, coords_dict: dict[str, int] | None=None, crop: bool=False, detrend_method: str | None=None, df_over_f: bool=False, crop_job_name_for_file: str='_cropped', secs_window: float=5, quantile_min: float=8, df_over_f_method: str='delta_f_over_sqrt_f', headless: bool=False)`
- [miniscope_preprocessor.py:100](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L100) `MiniscopePreprocessor.compute_projections(self, movie: cm.movie | None=None)`
- [miniscope_preprocessor.py:118](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L118) `MiniscopePreprocessor.get_crop_coordinates(self, coords_dict: dict[str, int] | None, projections: Projections, movie_height: int, movie_width: int, headless: bool=False)`
- [miniscope_preprocessor.py:157](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L157) `MiniscopePreprocessor.crop_movie(self, movie: cm.movie, coords_dict: dict[str, int])`
- [miniscope_preprocessor.py:187](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L187) `MiniscopePreprocessor.detrend_movie(self, movie: cm.movie, method: str='median', plot_trend: bool=True)`
- [miniscope_preprocessor.py:248](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_preprocessor.py#L248) `MiniscopePreprocessor.compute_df_over_f(self, movie: cm.movie | np.ndarray, secs_window: float=5, quantile_min: float=8, method: str='delta_f_over_sqrt_f')`

### `miniscope/miniscope_processor.py`

Class `MiniscopeProcessor` — [miniscope_processor.py:36](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L36). Main processor for calcium imaging movie analysis using CaImAn.

- [miniscope_processor.py:52](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L52) `MiniscopeProcessor.__init__(self, data_manager: MiniscopeDataManager)`
- [miniscope_processor.py:76](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L76) `MiniscopeProcessor.process_calcium_movie(self, parallel: bool=True, n_processes: int=12, apply_motion_correction: bool=True, inspect_motion_correction: bool=False, plot_params: bool=False, run_CNMFE: bool=True, save_estimates: bool=True, save_CNMFE_estimates_filename: str='estimates.hdf5', save_CNMFE_params: bool=False)`
- [miniscope_processor.py:160](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L160) `MiniscopeProcessor.motion_correction_manager(self, data_manager: MiniscopeDataManager, dview: Any, apply_motion_correction: bool, inspect_motion_correction: bool)`
- [miniscope_processor.py:197](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L197) `MiniscopeProcessor.cleanup_tkinter(self)`
- [miniscope_processor.py:205](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L205) `MiniscopeProcessor.cnmfe_parameter_handler(self, dm: MiniscopeDataManager, plot_params: bool=False)`
- [miniscope_processor.py:255](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/miniscope_processor.py#L255) `MiniscopeProcessor.inspect_motion_correction(self, mc: Any, opts_caiman: 'CNMFParams', original_movie: cm.movie, frame_rate: float, plot_rigid_motion_correction: bool=True, plot_shifts: bool=True, play_concatenated_movies: bool=True, down_sample_ratio: float=0.2, plot_correlation: bool=True, plot_advanced_MC_inspection: bool=True)`

### `miniscope/movie_io.py`

Class `MovieIO` — [movie_io.py:6](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/movie_io.py#L6). Static utility class for saving and loading CaImAn movies.

- [movie_io.py:13](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/movie_io.py#L13) `MovieIO.save_movie(dm, movie_file_name, movie=None)`
- [movie_io.py:46](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/movie_io.py#L46) `MovieIO.load_movie(miniscope_dir_path, movie_file_name)`

### `miniscope/onix_miniscope_data_manager.py`

Class `OnixMiniscopeDataManager` — [onix_miniscope_data_manager.py:14](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/onix_miniscope_data_manager.py#L14). Handles UCLA V4 Miniscope data formats (start-time_*_miniscope.csv, ucla-miniscope-v4-clock_*.raw).

- [onix_miniscope_data_manager.py:22](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/onix_miniscope_data_manager.py#L22) `OnixMiniscopeDataManager.can_handle(cls, directory: str | Path)`
- [onix_miniscope_data_manager.py:117](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/onix_miniscope_data_manager.py#L117) `OnixMiniscopeDataManager.sync_timestamps(self, ephys_dm: Any | None=None, channel_name: str | None=None, **kwargs: Any)`

### `miniscope/pipeline_results.py`

Class `PreprocessingResult` — [pipeline_results.py:23](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L23). Outputs captured by :class:`~aceneurotools.miniscope.miniscope_preprocessor.MiniscopePreprocessor`.

Class `ProcessingResult` — [pipeline_results.py:40](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L40). Outputs captured by :class:`~aceneurotools.miniscope.miniscope_processor.MiniscopeProcessor`.

Class `PostprocessingResult` — [pipeline_results.py:60](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L60). Outputs captured by :class:`~aceneurotools.miniscope.miniscope_postprocessor.MiniscopePostprocessor`.

Class `PreprocessConfig` — [pipeline_results.py:91](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L91). Configuration for the preprocessing stage of :class:`~aceneurotools.pipelines.miniscope.MiniscopePipeline`.

Class `ProcessConfig` — [pipeline_results.py:116](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L116). Configuration for the processing stage of :class:`~aceneurotools.pipelines.miniscope.MiniscopePipeline`.

Class `PostprocessConfig` — [pipeline_results.py:145](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/pipeline_results.py#L145). Configuration for the post-processing stage of :class:`~aceneurotools.pipelines.miniscope.MiniscopePipeline`.


### `miniscope/projections.py`

Class `Projections` — [projections.py:65](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/projections.py#L65). Container for spatial and temporal projections of a calcium movie.

- [projections.py:17](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/projections.py#L17) `compute_projections(movie: 'np.ndarray')`
- [projections.py:88](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/projections.py#L88) `Projections.__init__(self, max: np.ndarray, std: np.ndarray, min: np.ndarray, mean: np.ndarray, median: np.ndarray, range: np.ndarray, time: np.ndarray)`

### `miniscope/ucla_data_manager.py`

Class `UCLADataManager` — [ucla_data_manager.py:16](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/ucla_data_manager.py#L16). Handles V3 Miniscope data formats (metaData.json, timeStamps.csv, default events).

- [ucla_data_manager.py:22](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/ucla_data_manager.py#L22) `UCLADataManager.can_handle(cls, directory: str | Path)`
- [ucla_data_manager.py:119](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/miniscope/ucla_data_manager.py#L119) `UCLADataManager.sync_timestamps(self, ephys_dm: Any | None=None, channel_name: str | None=None, **kwargs: Any)`

### `ephys/__init__.py`

Package exports only.


### `ephys/block_processor.py`

Class `BlockProcessor` — [block_processor.py:33](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/block_processor.py#L33). Processes a Neo Block containing raw ephys data into Channel objects.

- [block_processor.py:47](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/block_processor.py#L47) `BlockProcessor.__init__(self, ephys_block: Block, logger: logging.Logger)`
- [block_processor.py:58](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/block_processor.py#L58) `BlockProcessor.process_raw_ephys(self, channels: str | list[str], remove_artifacts: bool=False)`
- [block_processor.py:105](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/block_processor.py#L105) `BlockProcessor.remove_artifacts(self, channel: Channel, volt_threshold: float=1500, time_threshold: float=60, hannNum: int=75)`

### `ephys/channel.py`

Class `Channel` — [channel.py:6](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel.py#L6). Represents a single electrophysiology recording channel.

- [channel.py:30](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel.py#L30) `Channel.__init__(self, name: str, signal: np.ndarray, sampling_rate: float, time_vector: np.ndarray, events: dict[str, Any])`

### `ephys/channel_worker.py`

Class `ChannelWorker` — [channel_worker.py:11](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel_worker.py#L11). Worker class for processing and visualizing a single ephys channel.

- [channel_worker.py:27](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel_worker.py#L27) `ChannelWorker.__init__(self, channel: Channel)`
- [channel_worker.py:37](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel_worker.py#L37) `ChannelWorker.plot_channel(self, use_filtered: bool=False)`
- [channel_worker.py:46](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel_worker.py#L46) `ChannelWorker.plot_spectrogram(self, window_length: float=30, window_step: float=3, freq_limits: list[float]=[0, 50], time_bandwidth: float=2, plot_events: bool=False, use_filtered: bool=False)`
- [channel_worker.py:75](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel_worker.py#L75) `ChannelWorker.compute_spectrogram(self, channel: Channel, window_length: float=30, window_step: float=3, freq_limits: list[float]=[0, 50], time_bandwidth: float=2, use_filtered: bool=False)`
- [channel_worker.py:117](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/channel_worker.py#L117) `ChannelWorker.plot_phases(self)`

### `ephys/ephys_data_manager.py`

Class `EphysDataManager` — [ephys_data_manager.py:13](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L13). Abstract base class for ephys data managers.

- [ephys_data_manager.py:31](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L31) `EphysDataManager.create(cls: type[T], ephys_directory: str | Path, **kwargs: Any)`
- [ephys_data_manager.py:44](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L44) `EphysDataManager.can_handle(cls, directory: str | Path)`
- [ephys_data_manager.py:49](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L49) `EphysDataManager.__init__(self, ephys_directory: str | Path | None=None, auto_import_ephys_block: bool=True, auto_process_block: bool=True, auto_compute_phases: bool=True, level: str | int='CRITICAL', channels: list[str] | None=None, remove_artifacts: bool=False)`
- [ephys_data_manager.py:88](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L88) `EphysDataManager.import_ephys_block(self, ephys_directory: str | Path)`
- [ephys_data_manager.py:93](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L93) `EphysDataManager.process_ephys_block_to_channels(self, channels: list[str] | None=None, remove_artifacts: bool=False)`
- [ephys_data_manager.py:98](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L98) `EphysDataManager.get_sync_timestamps(self, channel_name: str | None=None)`
- [ephys_data_manager.py:105](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L105) `EphysDataManager.compute_phases_all_channels(self)`
- [ephys_data_manager.py:111](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L111) `EphysDataManager.compute_phase(self, channel: Channel)`
- [ephys_data_manager.py:126](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L126) `EphysDataManager.filter_ephys(self, channel_name: str, n: int=2, cut: float | list[float] | np.ndarray=[0.5, 4], ftype: str='butter', btype: str='bandpass', replace_signal: bool=True)`
- [ephys_data_manager.py:178](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L178) `EphysDataManager.get_channels(self)`
- [ephys_data_manager.py:182](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_data_manager.py#L182) `EphysDataManager.get_channel(self, channel_name: str)`

### `ephys/ephys_loader.py`

- [ephys_loader.py:21](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/ephys_loader.py#L21) `load_ephys_for_analysis(line_num: int, project_path: str | Path, data_path: str | Path | None, channel_names: list[str], filter_type: str | None=None, filter_range: list[float]=[0.5, 4.0], remove_artifacts: bool=False, logging_level: str | int='CRITICAL')`

### `ephys/import_agent_analyzer.py`

- [import_agent_analyzer.py:14](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/import_agent_analyzer.py#L14) `import_agent_analyzer(suffix: str='2024-08-22T14_16_06')`
- [import_agent_analyzer.py:30](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/import_agent_analyzer.py#L30) `plot_O2(analog_input: dict)`
- [import_agent_analyzer.py:41](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/import_agent_analyzer.py#L41) `plot_CO2(analog_input: dict)`
- [import_agent_analyzer.py:51](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/import_agent_analyzer.py#L51) `plot_anesthetic(analog_input: dict, anesthetic: str='SEV')`

### `ephys/neuralynx_data_manager.py`

Class `NeuralynxDataManager` — [neuralynx_data_manager.py:18](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/neuralynx_data_manager.py#L18). Manages the import of raw Neuralynx ephys data.

- [neuralynx_data_manager.py:24](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/neuralynx_data_manager.py#L24) `NeuralynxDataManager.can_handle(cls, directory: str | Path)`
- [neuralynx_data_manager.py:31](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/neuralynx_data_manager.py#L31) `NeuralynxDataManager.import_ephys_block(self, ephys_directory: str | Path)`
- [neuralynx_data_manager.py:39](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/neuralynx_data_manager.py#L39) `NeuralynxDataManager.process_ephys_block_to_channels(self, channels: list[str] | None=None, remove_artifacts: bool=False)`
- [neuralynx_data_manager.py:65](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/neuralynx_data_manager.py#L65) `NeuralynxDataManager.get_sync_timestamps(self, channel_name: str | None=None)`

### `ephys/rhs2116_data_manager.py`

Class `RHS2116DataManager` — [rhs2116_data_manager.py:19](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/rhs2116_data_manager.py#L19). Manages the import of raw RHS2116 ephys data.

- [rhs2116_data_manager.py:41](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/rhs2116_data_manager.py#L41) `RHS2116DataManager.can_handle(cls, directory: str | Path)`
- [rhs2116_data_manager.py:48](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/rhs2116_data_manager.py#L48) `RHS2116DataManager.import_ephys_block(self, ephys_directory: str | Path)`
- [rhs2116_data_manager.py:85](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/rhs2116_data_manager.py#L85) `RHS2116DataManager.process_ephys_block_to_channels(self, channels: list[str] | None=None, remove_artifacts: bool=False, max_samples: int | None=None)`
- [rhs2116_data_manager.py:174](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/rhs2116_data_manager.py#L174) `RHS2116DataManager.get_sync_timestamps(self, channel_name: str | None=None)`

### `ephys/script.py`

- [script.py:17](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/script.py#L17) `main()`

### `ephys/spectrogram.py`

Class `Spectrogram` — [spectrogram.py:5](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/spectrogram.py#L5). Represents a computed spectrogram from ephys data.

- [spectrogram.py:21](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/spectrogram.py#L21) `Spectrogram.__init__(self, psd: np.ndarray, stimes: np.ndarray, sfreqs: np.ndarray)`

### `ephys/visualizer.py`

Class `Visualizer` — [visualizer.py:11](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/visualizer.py#L11). Class for visualizing ephys data.

- [visualizer.py:16](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/visualizer.py#L16) `Visualizer.__init__(self, level: str | int='CRITICAL')`
- [visualizer.py:26](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/visualizer.py#L26) `Visualizer.plot_channel(self, channel: Channel, use_filtered: bool=False)`
- [visualizer.py:40](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/visualizer.py#L40) `Visualizer.plot_spectrogram_helper(self, psd: np.ndarray, stimes: np.ndarray, sfreqs: np.ndarray, events: dict[str, Any] | None=None)`
- [visualizer.py:73](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/ephys/visualizer.py#L73) `Visualizer.plot_spectrogram(self, spectrogram: Spectrogram, events: dict[str, Any] | None=None)`

### `multimodal/__init__.py`

Package exports only.


### `multimodal/calcium_ephys_visualizer.py`

- [calcium_ephys_visualizer.py:18](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/calcium_ephys_visualizer.py#L18) `create_ca_ephys_movie(miniscope_dm: 'MiniscopeDataManager', ephys_idx_all_TTL_events: np.ndarray, channel_object: 'Channel', time_range: list[float] | None=None, movie_num: int | None=None, crop: bool=False, crop_coords: list[int] | tuple[int, int, int, int] | None=None, plot_mean_fluorescence: bool=False, df_over_sqrt_f: bool=False, vmin: float | None=None, vmax: float | None=None, mark_start_systemic: bool=True, plot_ephys: bool=True, num_frames_of_traces: int=10, time_stamps: bool=True, playback_interval: int=33, play_movie: bool=True, save_movie: bool=False)`

### `multimodal/coherence_analysis.py`

Class `SubjectCoherenceResult` — [coherence_analysis.py:32](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L32). Power, coherence, XC, and lag for a single subject — control and treatment windows.

Class `CoherenceAnalysis` — [coherence_analysis.py:61](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L61). Compute, visualize, and save coherence statistics for one or many subjects.

- [coherence_analysis.py:48](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L48) `SubjectCoherenceResult.to_dataframe(self)`
- [coherence_analysis.py:64](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L64) `CoherenceAnalysis.__init__(self, config: StatsConfig | None=None)`
- [coherence_analysis.py:67](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L67) `CoherenceAnalysis.run_subject(self, signal_1: np.ndarray, signal_2: np.ndarray, fr: float, line_num: int, selections: dict[int, list[list[float]]], drug: str, output_dir: str | Path, signal_1_label: str='Signal 1', signal_2_label: str='Signal 2', *, plot_coherogram: bool=False, plot_spectrogram: bool=False, plot_signal_overview: bool=False, save_plots: bool=True)`
- [coherence_analysis.py:150](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L150) `CoherenceAnalysis.run_population(self, results: list[SubjectCoherenceResult], drug_groups: dict[str, list[int]], output_dir: str | Path, channel_label: str='channel')`
- [coherence_analysis.py:179](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/coherence_analysis.py#L179) `CoherenceAnalysis.save_results(self, raw_df: pd.DataFrame | None, avg_df: pd.DataFrame | None, output_dir: str | Path, drug_name: str, channel_label: str='channel')`

### `multimodal/event_correlograms.py`

- [event_correlograms.py:88](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/event_correlograms.py#L88) `compute_autocorrelogram(group: dict[int, np.ndarray], binsize: float, windowsize: float, t_start: float | None=None, t_end: float | None=None, norm: bool=True)`
- [event_correlograms.py:147](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/event_correlograms.py#L147) `compute_crosscorrelogram(group: dict[int, np.ndarray] | tuple[dict[int, np.ndarray], dict[int, np.ndarray]] | list[dict[int, np.ndarray]], binsize: float, windowsize: float, t_start: float | None=None, t_end: float | None=None, norm: bool=True, reverse: bool=False)`
- [event_correlograms.py:223](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/event_correlograms.py#L223) `compute_eventcorrelogram(group: dict[int, np.ndarray], event: np.ndarray, binsize: float, windowsize: float, t_start: float | None=None, t_end: float | None=None, norm: bool=True)`
- [event_correlograms.py:272](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/event_correlograms.py#L272) `compute_isi_distribution(data: np.ndarray | dict[int, np.ndarray], bins: int | list[float] | np.ndarray=10, log_scale: bool=False, t_start: float | None=None, t_end: float | None=None)`

### `multimodal/lab_config.py`

Class `ConditionSpec` — [lab_config.py:16](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L16). A single experimental condition with its subject list and drug flag.

Class `PathsConfig` — [lab_config.py:24](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L24). File system paths for a lab project.

Class `RunConfig` — [lab_config.py:34](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L34). Pipeline execution settings.

Class `LabConfig` — [lab_config.py:45](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L45). Lab-level configuration: channel identity, study design, paths, and run settings.

- [lab_config.py:56](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L56) `LabConfig.all_line_nums(self)`
- [lab_config.py:63](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L63) `LabConfig.to_json(self, path: str | Path)`
- [lab_config.py:94](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L94) `LabConfig.from_json(cls, path: str | Path)`
- [lab_config.py:174](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/lab_config.py#L174) `LabConfig.to_study_metadata(self)`

### `multimodal/miniscope_ephys_alignment_utils.py`

- [miniscope_ephys_alignment_utils.py:15](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/miniscope_ephys_alignment_utils.py#L15) `sync_neuralynx_miniscope_timestamps(channel: Channel, miniscope_dm: 'MiniscopeDataManager', ephys_dm: EphysDataManager, delete_TTLs: bool=True, fix_TTL_gaps: bool=False, only_experiment_events: bool=True)`
- [miniscope_ephys_alignment_utils.py:141](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/miniscope_ephys_alignment_utils.py#L141) `find_ephys_idx_of_TTL_events(tCaIm: np.ndarray, channel: Channel, frame_rate: float, ca_events_idx: dict[int, np.ndarray] | None=None, all_TTL_events: bool=True)`
- [miniscope_ephys_alignment_utils.py:172](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/miniscope_ephys_alignment_utils.py#L172) `find_ca_movie_frame_num_of_ephys_idx(channel: Channel, ephys_idx_all_TTL_events: np.ndarray)`
- [miniscope_ephys_alignment_utils.py:186](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/miniscope_ephys_alignment_utils.py#L186) `find_ca_movie_filenums(channel: Channel, ephys_idx_all_TTL_events: np.ndarray, miniscope_dm: 'MiniscopeDataManager', time_range: list[float] | None=None)`

### `multimodal/oscillatory_events.py`

- [oscillatory_events.py:93](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/oscillatory_events.py#L93) `detect_oscillatory_events(signal: np.ndarray, fs: float, frequency_band: tuple[float, float], threshold_band: tuple[float, float], duration_band: tuple[float, float], min_interval: float, sliding_window_samples: int=51, t_start: float=0.0, filter_order: int=2)`

### `multimodal/perievent.py`

- [perievent.py:40](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/perievent.py#L40) `compute_perievent(signal: np.ndarray, event_times: np.ndarray, fs: float, window: float | tuple[float, float] | list[float], t_start: float=0.0, drop_boundary_events: bool=True)`
- [perievent.py:122](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/perievent.py#L122) `compute_event_triggered_average(signal: np.ndarray, event_times: np.ndarray, fs: float, window: float | tuple[float, float] | list[float], t_start: float=0.0, drop_boundary_events: bool=True)`
- [perievent.py:194](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/perievent.py#L194) `compute_spike_triggered_average(signal: np.ndarray, spike_times: np.ndarray, fs: float, window: float | tuple[float, float] | list[float], t_start: float=0.0, drop_boundary_events: bool=True)`

### `multimodal/phase_utils.py`

- [phase_utils.py:11](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/phase_utils.py#L11) `ephys_phase_ca_events(ephys_idx_ca_events: dict[int, np.ndarray], channel_object: 'Channel', neurons: str | list[int]='all')`
- [phase_utils.py:40](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/phase_utils.py#L40) `miniscope_phase_ca_events(ca_events_idx: dict[int, np.ndarray], miniscope_phases: np.ndarray, neurons: str | list[int] | int='all')`
- [phase_utils.py:67](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/phase_utils.py#L67) `phase_ca_events_histogram(ca_events_phases: dict[int, np.ndarray], neurons: str | list[int] | int='all', bins: int=18, hist_range: tuple[float, float]=(-np.pi, np.pi), density: bool=False, mean_density: bool=False, combined: bool=True, plot_histogram: bool=True)`

### `multimodal/scatter_analysis.py`

Class `PopulationCorrelationCollector` — [scatter_analysis.py:332](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L332). Accumulate per-subject correlation statistics for population analysis.

Class `ScatterAnalysis` — [scatter_analysis.py:822](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L822). High-level orchestrator for per-subject EEG–calcium scatter analyses.

- [scatter_analysis.py:105](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L105) `estimate_effective_sample_size(x: np.ndarray, y: np.ndarray, max_lags: int=100)`
- [scatter_analysis.py:138](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L138) `compute_confidence_interval(r: float, n_effective: float, confidence: float=0.95)`
- [scatter_analysis.py:162](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L162) `compute_statistics_robust(x: np.ndarray, y: np.ndarray, fr: float=30.0, correct_autocorrelation: bool=True, confidence_level: float=0.95, max_acf_lags: int=100)`
- [scatter_analysis.py:224](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L224) `compute_cohens_d(group1: np.ndarray, group2: np.ndarray, paired: bool=True)`
- [scatter_analysis.py:252](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L252) `bootstrap_ci(data: np.ndarray, statistic: str='median', n_bootstrap: int=10000, confidence: float=0.95)`
- [scatter_analysis.py:276](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L276) `paired_statistical_test(control: np.ndarray, treatment: np.ndarray, test_type: str='wilcoxon', min_n: int=4)`
- [scatter_analysis.py:339](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L339) `PopulationCorrelationCollector.__init__(self, drug_name: str)`
- [scatter_analysis.py:351](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L351) `PopulationCorrelationCollector.add_subject(self, line_num: int, control_stats: dict, treatment_stats: dict)`
- [scatter_analysis.py:363](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L363) `PopulationCorrelationCollector.has_data(self)`
- [scatter_analysis.py:367](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L367) `PopulationCorrelationCollector.get_arrays(self)`
- [scatter_analysis.py:371](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L371) `PopulationCorrelationCollector.compute_population_statistics(self, bootstrap_iterations: int=10000, confidence_level: float=0.95, paired_test: str='wilcoxon', min_n: int=4)`
- [scatter_analysis.py:449](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L449) `create_scatter_plot(calcium_signal: np.ndarray, eeg_signal: np.ndarray, line_num: int, drug: str, period: str, channel: str, fr: float, time_window: list[float], config: StatsConfig, save_path: Path | None=None)`
- [scatter_analysis.py:501](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L501) `create_hexbin_plot(calcium_signal: np.ndarray, eeg_signal: np.ndarray, line_num: int, drug: str, period: str, channel: str, fr: float, time_window: list[float], config: StatsConfig, save_path: Path | None=None)`
- [scatter_analysis.py:554](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L554) `create_combined_scatter_plot(calcium_ctrl: np.ndarray, eeg_ctrl: np.ndarray, calcium_treat: np.ndarray, eeg_treat: np.ndarray, line_num: int, drug: str, channel: str, fr: float, time_window_ctrl: list[float], time_window_treat: list[float], config: StatsConfig, save_path: Path | None=None)`
- [scatter_analysis.py:609](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L609) `create_combined_hexbin_plot(calcium_ctrl: np.ndarray, eeg_ctrl: np.ndarray, calcium_treat: np.ndarray, eeg_treat: np.ndarray, line_num: int, drug: str, channel: str, fr: float, time_window_ctrl: list[float], time_window_treat: list[float], config: StatsConfig, save_path: Path | None=None)`
- [scatter_analysis.py:672](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L672) `create_population_violin_plot(collector: PopulationCorrelationCollector, output_dir: str | Path, channel: str, config: StatsConfig)`
- [scatter_analysis.py:755](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L755) `create_all_drugs_summary_plot(all_collectors: dict[str, PopulationCorrelationCollector], output_dir: str | Path, channel: str, config: StatsConfig)`
- [scatter_analysis.py:830](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L830) `ScatterAnalysis.__init__(self, config: StatsConfig | None=None)`
- [scatter_analysis.py:833](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/scatter_analysis.py#L833) `ScatterAnalysis.run_subject(self, eeg_signal: np.ndarray, calcium_signal: np.ndarray, fr: float, line_num: int, drug: str, selections: dict[int, list[list[float]]], channel: str, output_dir: str | Path, collector: PopulationCorrelationCollector | None=None)`

### `multimodal/signal_utils.py`

- [signal_utils.py:14](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L14) `slice_signal(signal: np.ndarray, selections: dict[int, list[list[float]]], line_num: int, fr: float)`
- [signal_utils.py:42](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L42) `filter_signals(signal_1: np.ndarray, signal_2: np.ndarray, fr: float, freq_range: list[float], order: int=2)`
- [signal_utils.py:60](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L60) `trim_filter_edges(signal: np.ndarray, fr: float, trim_seconds: float=5.0)`
- [signal_utils.py:74](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L74) `handle_nans(signal: np.ndarray, fr: float, max_gap_seconds: float=0.5)`
- [signal_utils.py:122](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L122) `normalize_signals_global(control_1: np.ndarray, treatment_1: np.ndarray, control_2: np.ndarray, treatment_2: np.ndarray)`
- [signal_utils.py:159](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L159) `compute_coherence(signal_1: np.ndarray, signal_2: np.ndarray, fr: float, freq_range: list[float], nperseg_seconds: float | None=None)`
- [signal_utils.py:173](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L173) `compute_cross_correlation(signal_1: np.ndarray, signal_2: np.ndarray, fr: float, max_lag_seconds: float=10.0)`
- [signal_utils.py:194](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L194) `compute_spectral_power(signal: np.ndarray, fr: float, freq_range: list[float], window_length: float=60.0, window_step: float=3.0, time_bandwidth: float=2.0)`
- [signal_utils.py:229](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L229) `compute_signal_stats(signal_1: np.ndarray, signal_2: np.ndarray, fr: float, freq_range: list[float], window_length: float=60.0, window_step: float=3.0, time_bandwidth: float=2.0, coherence_nperseg_seconds: float | None=None)`
- [signal_utils.py:247](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L247) `compute_hilbert_envelope(signal: np.ndarray)`
- [signal_utils.py:266](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L266) `get_filter_frequency_response(freq_range: float | tuple[float, float] | list[float], fr: float, filter_type: str='bandpass', order: int=2, worN: int=1024)`
- [signal_utils.py:303](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/signal_utils.py#L303) `compute_mutual_information(tuning_curve: np.ndarray, occupancy: np.ndarray, mean_rate: float | None=None)`

### `multimodal/stats_config.py`

Class `StatsConfig` — [stats_config.py:14](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L14). Tunable algorithm parameters for the statistical analysis pipeline.

Class `StudyMetadata` — [stats_config.py:112](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L112). Drug groups and per-subject control/treatment time windows (in minutes).

- [stats_config.py:59](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L59) `StatsConfig.to_json(self, path: str | Path)`
- [stats_config.py:64](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L64) `StatsConfig.from_json(cls, path: str | Path)`
- [stats_config.py:118](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L118) `StudyMetadata.__init__(self, drug_groups: dict[str, list[int]], selections: dict[int, list[list[float]]], no_drug_conditions: set[str] | None=None)`
- [stats_config.py:134](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L134) `StudyMetadata.drug_of(self, line_num: int)`
- [stats_config.py:137](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L137) `StudyMetadata.has_drug_event(self, line_num: int)`
- [stats_config.py:141](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L141) `StudyMetadata.all_line_nums(self)`
- [stats_config.py:144](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L144) `StudyMetadata.line_nums_for(self, drug: str)`
- [stats_config.py:148](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L148) `StudyMetadata.default(cls)`
- [stats_config.py:163](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L163) `StudyMetadata.example(cls)`
- [stats_config.py:171](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L171) `StudyMetadata.from_json(cls, path: str | Path)`
- [stats_config.py:183](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_config.py#L183) `StudyMetadata.to_json(self, path: str | Path)`

### `multimodal/stats_loader.py`

- [stats_loader.py:56](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_loader.py#L56) `load_for_stats(line_num: int, project_path: str | Path, data_path: str | Path | None=None, channel_name: str='CBvsPCEEG', freq_range: list[float] | None=None, delete_TTLs: bool=True, fix_TTL_gaps: bool=True, only_experiment_events: bool=True)`
- [stats_loader.py:193](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_loader.py#L193) `load_for_stats_two_channels(line_num: int, project_path: str | Path, data_path: str | Path | None=None, channel_name_1: str='PFCLFPvsCBEEG', channel_name_2: str='PFCEEGvsCBEEG', freq_range: list[float] | None=None, delete_TTLs: bool=True, fix_TTL_gaps: bool=True, only_experiment_events: bool=True)`
- [stats_loader.py:323](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/stats_loader.py#L323) `load_calcium_signal(miniscope_dm: MiniscopeDataManager, calcium_signal_dir: str | Path, line_num: int, npz_key: str='meanFluorescence')`

### `multimodal/surrogate.py`

Class `PermutationTestResult` — [surrogate.py:28](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L28). Result of a Monte-Carlo permutation test.

- [surrogate.py:53](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L53) `permutation_test(observed_statistic: float, surrogate_statistic_fn: Callable[[np.random.Generator], float], n_surrogates: int=1000, alternative: str='two-sided', rng: np.random.Generator | None=None, n_jobs: int=1)`
- [surrogate.py:128](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L128) `jitter_event_times(event_times: np.ndarray, max_jitter: float, t_start: float | None=None, t_end: float | None=None, clip_to_support: bool=False, rng: np.random.Generator | None=None)`
- [surrogate.py:171](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L171) `shift_event_times(event_times: np.ndarray, t_start: float, t_end: float, min_shift: float=0.0, max_shift: float | None=None, mode: str='drop', rng: np.random.Generator | None=None)`
- [surrogate.py:226](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L226) `shuffle_event_intervals(event_times: np.ndarray, rng: np.random.Generator | None=None)`
- [surrogate.py:256](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L256) `resample_event_times(event_times: np.ndarray, t_start: float, t_end: float, n: int | None=None, rng: np.random.Generator | None=None)`
- [surrogate.py:292](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/surrogate.py#L292) `apply_to_group(fn: Callable[..., np.ndarray], group: dict[int, np.ndarray], **kwargs)`

### `multimodal/wavelets.py`

- [wavelets.py:50](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/wavelets.py#L50) `generate_morlet_filterbank(freqs: np.ndarray, fs: float, gaussian_width: float=1.5, window_length: float=1.0, precision: int=16)`
- [wavelets.py:137](https://github.com/emelon8/experiment_analysis/blob/main/src/aceneurotools/multimodal/wavelets.py#L137) `compute_wavelet_transform(signal: np.ndarray, freqs: np.ndarray, fs: float, gaussian_width: float=1.5, window_length: float=1.0, precision: int=16, norm: str | None='l1')`

## Implementation acceptance evidence needed

1. Register a real project and round-trip experiment metadata, every supported analysis setting and study config without losing unknown fields.
2. Complete a real miniscope run through embedded crop and component review; confirm kept component IDs, event results and saved curated output match. Reopen the app and verify decisions/results survive.
3. Complete real ephys, multimodal, mean-fluorescence and all three study-statistics workflows; expose channel/subject/condition selection and actual generated files, with skipped/partial failures visible.
4. Exercise every lower-level researcher tool listed above through a supported GUI recipe or explicitly leave it marked unimplemented. A catalog label is not feature parity.
5. Verify existing CLI/scripts against baseline behavior and ensure no plotting/input prompt steals focus or hangs a GUI worker.
6. Validate cancellation, failed imports, missing files, invalid settings and reruns using separate run identity/output provenance. No success state without worker completion and verified outputs.
