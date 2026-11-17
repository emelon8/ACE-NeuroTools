---
status: proposed
---

# Add pipeline entry points for library-only multimodal analyses

This is a design proposal with interface sketches, not an exact diff. The
analyses need scientific choices (event sources, windows, the binned variable for
mutual information) that the lab should make before code is written. Each phase
below would come back as its own reviewed diff.

## Context

`src/aceneurotools/multimodal/__init__.py` exports analyses that no pipeline,
command or GUI route calls. They are reachable only from Python scripts and
notebooks:

| Function | Signature (current main) |
| --- | --- |
| `compute_perievent`, `compute_event_triggered_average`, `compute_spike_triggered_average` | `(signal, event_times, fs, window, t_start=0.0, drop_boundary_events=True)` (`perievent.py:43`, `:135`, `:207`) |
| `detect_oscillatory_events` | `(signal, fs, frequency_band, threshold_band, duration_band, min_interval, sliding_window_samples=51, t_start=0.0, filter_order=2)` (`oscillatory_events.py:93`) |
| `compute_autocorrelogram`, `compute_crosscorrelogram`, `compute_eventcorrelogram`, `compute_isi_distribution` | `(group: dict[int, ndarray], binsize, windowsize, t_start=None, t_end=None, norm=True, ...)` returning a `DataFrame` (`event_correlograms.py:88`, `:147`, `:223`, `:272`) |
| `permutation_test` and surrogate generators | `permutation_test(observed_statistic, surrogate_statistic_fn, n_surrogates=1000, alternative="two-sided", rng=None, n_jobs=1)` plus `jitter_event_times`, `shift_event_times`, `shuffle_event_intervals`, `resample_event_times`, `apply_to_group` (`surrogate.py:53` onward) |
| `compute_wavelet_transform` | `(signal, freqs, fs, gaussian_width=1.5, window_length=1.0, precision=16, norm="l1")` (`wavelets.py:137`) |
| `compute_mutual_information` | `(tuning_curve, occupancy, mean_rate=None) -> (bits_per_second, bits_per_event)` (`signal_utils.py:351`) |

ADR 0001 asks the GUI and CLI to share application operations. A GUI-only
wrapper around these functions would create features with no command-line
equivalent, so the entry points belong in the pipelines first.

`StatsPipeline` (`src/aceneurotools/pipelines/stats.py`) already has the
structure these analyses need:

- `VALID_ANALYSES` (line 27) names each analysis and drives `--analyses` choices.
- `run()` dispatches each selected analysis to `_run_<name>` with an
  `output_dir / <name>` folder (lines 262-300).
- Each `_run_<name>` loops over subjects, loads with `load_for_stats`
  (TTL-aligned, downsampled ephys channel and the calcium data manager) or
  `load_calcium_signal`, writes `line_<N>/` outputs and records
  `record_complete` / `record_skip` in `run_log.json` (`_RunLog`, line 45).
- Algorithm settings come from `stats_config.json` (`StatsConfig`) and study
  design from `lab_config.json` (`LabConfig`).

## Design blockers

This is an unresolved design proposal, not an implementation. The existing `load_for_stats` path selects ephys samples at camera timestamps without anti-alias filtering (`src/aceneurotools/multimodal/stats_loader.py`). It must not be used as-is for oscillatory detection or wavelet power. A 20 Hz analysis requires a sampling rate greater than 40 Hz and appropriate filtering when reducing the rate.

Before implementing phases 1–2, define full-rate aligned ephys loading, any resampling/filtering contract, the event-time source and clock, boundary handling, and output/provenance requirements. The phase list below is historical direction, not an approved data-loading design. New analysis dispatch also needs explicit wiring and tests.

## Proposed design

Register new analyses in `VALID_ANALYSES` and implement each as a
`_run_<name>(subjects, meta, config, ...)` method with the same per-subject loop,
output layout and run-log records. They then appear in `--analyses`, in
`lab_config.json` `run.analyses`, in `ace-neuro --mode stats`, and in the planned
GUI Study page after explicit dispatch and interface wiring are implemented.

```python
VALID_ANALYSES.update({
    "oscillatory_events": "Detect band-limited bursts (slow waves, spindles, ...) on the ephys channel.",
    "perievent_average": "Event-triggered averages of ephys and calcium signals around detected or recorded events.",
    "wavelet_power": "Morlet wavelet time-frequency power of the ephys channel.",
    "event_correlograms": "Auto/cross-correlograms of calcium event trains, with surrogate significance.",
    "mutual_information": "Skaggs information between calcium event rate and a binned signal state.",
})
```

Settings would be new optional `StatsConfig` fields with conservative
defaults, kept in `stats_config.json`:

```python
# stats_config.json (sketch)
"oscillation_bands": {"slow_wave": {"frequency_band": [0.5, 4], "threshold_band": [2, 1e9],
                                    "duration_band": [0.25, 2], "min_interval": 0.2}},
"perievent_window": [-2.0, 2.0],
"perievent_event_source": "oscillatory_events",   # or "ephys_events:<label prefix>" or "calcium_events"
"wavelet_freqs": {"start": 0.5, "stop": 20, "num": 40},
"correlogram_binsize": 0.05, "correlogram_windowsize": 2.0,
"surrogate_method": "shuffle_intervals", "n_surrogates": 1000,
"mi_variable": "ephys_band_power", "mi_bins": 10
```

Outputs per subject (`<output_dir>/<analysis>/line_<N>/`): the computed arrays
as `.npz`, event tables as `.csv`, and figures in `StatsConfig.plot_formats`.
Population summaries go under `<output_dir>/<analysis>/population/`, with output
failures recorded through `record_output_failure` as the existing analyses do.

## Phasing

1. `oscillatory_events` and `perievent_average`: first design full-rate aligned ephys and explicit event sources; calcium data can use `load_calcium_signal` where appropriate.
2. `wavelet_power`: use the reviewed full-rate alignment/loading contract; do not use camera-rate ephys without a justified resampling and filtering design.
3. `event_correlograms` with surrogate testing: needs a new loader for
   per-neuron calcium event times (`calcium-events.json` from runs or curations),
   because `stats_loader` reads mean fluorescence only.
4. `mutual_information`: needs the lab to define the binned variable and rate.

## Compatibility

Existing analyses, their outputs and defaults are unchanged. New `StatsConfig`
fields are optional; existing `stats_config.json` files keep loading. The new
names only run when selected.

## Open questions for the lab

- Which event sources matter: recorded TTL labels, detected oscillations,
  calcium events, or all three?
- Which oscillation band presets should ship as defaults, if any? Defaults must
  stay general; lab-specific presets belong in each project's `stats_config.json`.
- Is mean fluorescence enough for peri-event calcium averages, or are per-neuron
  traces from curated estimates required?

## Unblocks

GUI Study-page support for these analyses through the same `StatsPipeline` path
as coherence and scatter correlation, with matching command-line runs and job
exports.

## Verification

Design only: no code diff is proposed yet, so nothing was run. Each phase would
add tests alongside `tests/test_oscillatory_events.py`, `tests/test_perievent.py`,
`tests/test_event_correlograms.py`, `tests/test_surrogate.py`,
`tests/test_wavelets.py` and `tests/test_mutual_information.py`, plus a
`StatsPipeline` dispatch and run-log test per analysis.

## Risks and alternatives

Aliasing, frequencies above Nyquist and ambiguous event clocks can produce misleading scientific results. Keeping these analyses Python-only is the current fallback. Implement one analysis at a time after scientific choices and synthetic reference tests are reviewed.
