# Neuron review and meeting follow-ups

Implementation update: October 6, 2026. Sources: the supplied
`curate_neurons-3.py` and lab-meeting transcript pasted into the conversation.
Transcript statements are investigation leads, not confirmed diagnoses or
authorization to alter scientific methods. The October 6 continuation adds GUI
export orchestration and makes the existing derivative detector callable without
a movie/postprocessor instance; its scientific calculations are unchanged.

## Implemented

The Neurons workspace loads actual CNMF estimates, displays summed spatial
footprints and the selected footprint, marks the selected maximum pixel, and
shows the raw `C` trace with a peak-centred window. Frame-rate override, window
duration, previous/next, keep/reject with automatic advance, K/R/arrow shortcuts,
and D/Enter finish are present. Finishing requires an explicit decision for any
undecided neurons. All-rejected reviews retain an audit record without writing
an invalid empty CNMF file.

Exports reload the original estimates, use CaImAn `select_components` and `save`,
and write the script's HDF5/NPZ outputs with original zero-based component IDs.
Each export gets a new directory; source estimates and earlier outputs remain
available. Dense NPZ footprints over 128 MB use documented sparse CSC arrays.
This memory guard is an intentional difference from the supplied script.

Meeting-driven additions are trace window zoom/pan, clickable overview, numbered
navigation, next undecided, decision counts, undo, autosave/resume, source-change
checks, and saved decision/provenance records. This supports long reviews without
requiring files or Python code to be edited. The existing ivory/green visual style
and embedded workspace are retained.

An `ACE Experiments` application-menu shortcut and `./launch-gui` now locate the
existing analysis environment, start the local server, and open the browser.
Launching again reuses the server. No additional packages or frontend build are
required. This is environment discovery, not environment installation.

See the [usage and file-format guide](../guides/experiment_gui.md#review-neurons-and-recompute-calcium-events).

Finish review now offers calcium-event recomputation from the saved curated
HDF5. Visible derivative/threshold controls start from the current experiment
settings. The optional `calcium-events.json` records kept-neuron events, the
curated-to-original ID mapping, parameters, frame rate, and source/curation
provenance. Repeated exports preserve earlier trials. Detection failures leave
source estimates and decisions available without installing partial output.

Saving curated copies alone does not recompute events. Event dictionary keys
index rows in curated `C`; the `neuron_ids` list maps those rows to original
zero-based component IDs. First/second derivative peak indices refer to
`np.diff(C, n=1 or 2)` without an added frame offset, matching the existing detector.
This export is separate from the initial run's `calcium-events.json` and does not
replace earlier run products.

Initial analysis runs now expose `output-inventory.json` in Results, including
events, component IDs, original/filtered signals, sparse footprints, and available
component quality diagnostics. Missing products have explicit reasons. Quality
arrays are exported when CaImAn provides them; explanatory quality views in the
Neurons workspace remain a separate priority.

The approved headless-policy fix preserves the selected `inline` setting while
suppressing GUI interactions. `inline=True` replaces the final temporal projection
with filtered data; `False` retains the original. Miniscope CLI defaults to `True`,
direct API to `False`; explicitly choose `False` for historical headless behavior.
Events use `C`, and phases/spectra still precede filtering, so these inputs are
unchanged by the fix. See the [capability inventory](pipeline-capabilities.md).

## Next priorities from the meeting

| Priority | Improvement | Concrete next step |
| --- | --- | --- |
| 1 | Prove real recording curation | Load a researcher-produced fitted HDF5, review representative neurons, compare footprints/traces and exported component IDs with the supplied script |
| 1 | Continue multimodal analysis from curated estimates | Calcium-event recomputation is implemented; add explicit curated inputs to multimodal processing and tie those products to their chosen curation |
| 1 | Understand neuron quality | Show existing signal/noise, spatial/temporal quality metrics alongside traces, with explanations and source provenance rather than inventing a new acceptance rule |
| 1 | Clear experiment history | Present runs, parameter snapshots, curations, and restore behavior together; keep Git/EVC attachment as a separate validated integration |
| 2 | Inspect missed neurons | Compare raw/corrected movie, detections, and a scientifically defined reconstruction residual in the same workspace |
| 2 | Recover missed neurons | Agree on manual ROI geometry, trace extraction, background handling, component IDs, and downstream effects before adding ROIs |
| 2 | Events on traces | Reuse event readers; overlay injection/treatment times and expose selected pre/post intervals with clear clock alignment |
| 2 | Export cluster jobs | Export the reviewed effective settings to Python/Slurm jobs, separating extraction and local curation; declare paths, environment, CPUs, and memory |
| 2 | Compare trials | Name alternate parameter/crop/curation trials and compare outputs without overwriting older results |
| 3 | Additional scientific exploration | Specify and validate interval autocorrelation/cross-correlation, PCA/clustering, latent-state and dynamical analyses as separate methods |

The review is not an automatic pipeline pause/resume checkpoint. The explicit
export action recomputes calcium events from saved curated estimates; previously
computed run arrays and multimodal products remain associated with their run.
Residual-video generation, manual ROI addition, event overlays, and cluster export
are not implemented in this pass.

## Remaining source changes to consider, not implemented

- **Broader saved-estimates continuation.** Event analysis now runs from reviewed
  estimates without extraction. Extend that explicit input/provenance contract to
  multimodal processing in a separate change.
- **Movie segment ordering.** Reproduce the reported lexical ordering
  `0, 1, 10, 11, 2` using acquisition filenames and timestamps, then identify which
  discovery/concatenation layer owns the ordering. A numeric ordering policy should
  be tested against frame/timestamp alignment before changing the source.
- **Residual semantics.** The existing movie-without-neurons helper masks pixels;
  it should not be presented as a validated CNMF reconstruction residual. A genuine
  residual viewer needs an agreed reconstruction/background definition.
- **Memory and workers.** Profile allocations and worker counts by stage on a
  representative recording. The processor already uses a movie reference rather
  than the reported whole-movie deep copy; inspect remaining copies before proposing
  that change again. The transcript's memory figures are not verified measurements.

## Validation boundary

Tests use a real CaImAn-saved fitted estimates fixture, including per-component
AR coefficients, then load/select/save through the installed CaImAn environment.
They compare kept `C` rows, spatial footprints, IDs, and unchanged source bytes;
also cover resume, stale tabs, changed sources, undecided handling, all-rejected
exports, invalid frame rates, full-trace window persistence, and HTTP routing.
Event regression tests verify all three derivatives, different thresholds,
rejected-neuron exclusion, original IDs, unchanged source/earlier exports, invalid
settings, and failed detection without partial outputs.
Browser validation uses temporary projects, not researcher CSVs or recordings.

A scalar AR-coefficient placeholder in the initial unfitted test fixture caused
CaImAn component selection to fail. The fixture was corrected to represent fitted
estimates; neither CaImAn nor ACE scientific source was modified. Export failures
retain the original estimates and review journal and show the failure reason.
