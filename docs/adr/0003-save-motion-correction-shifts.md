---
status: proposed
---

# Save motion-correction shifts for later inspection

## Context

Line numbers in this section refer to base `ded08fd`.

`CalciumImagingProcessor.motion_correction_manager`
(`src/aceneurotools/calcium_imaging/calcium_imaging_processor.py:170-205`) keeps the
CaImAn `MotionCorrect` object in the local variable `motion_correction_object`
(line 191). The only consumer is `inspect_motion_correction` (line 202-203), which
opens blocking windows and describes itself as "a mess ... It does not work well at
all" (line 278). After the method returns, the per-frame shifts and templates are
lost. Headless runs, including every GUI run, disable that inspection
(`shared/cli_utils.py` `apply_headless_policy`), so no record of the correction is
kept. Re-creating it later requires running motion correction again.

Related findings, not changed by this proposal:

- `inspect_motion_correction` plots the rigid shifts when `pw_rigid` is true and
  the piecewise shifts when it is false (line 297-310), the reverse of the
  condition used to compute `border_pix` (line 433-436).
- `CalciumImagingDataManager.motion_corrected_movie_filepath` is initialized to
  `None` and never assigned, so `ProcessingResult.motion_corrected_movie_filepath`
  is always `None` and the GUI inventory always reports that output as missing
  (`gui/run_outputs.py:170`).

## Proposed change

After `_apply_motion_correction` returns, write the `MotionCorrect` arrays that
exist (`shifts_rig`, `x_shifts_els`, `y_shifts_els`, `total_template_rig`,
`total_template_els`, as float32), the settings that locate each patch
(`strides`, `overlaps`, `max_shifts`, `upsample_factor_grid`, `shifts_opencv`;
with `shifts_opencv` false CaImAn returns piecewise shifts on a grid refined by
`upsample_factor_grid`), `border_to_0`, `pw_rigid`, the frame rate, the source
movie path and a UTC `saved_at` time to
`<calcium imaging directory>/saved_movies/motion_correction_shifts.npz`, the
folder that already receives `estimates.hdf5` (`_save_processed_data`, line 492).
Values that cannot be stored as numbers are left out and named in
`skipped_attributes`, so the file always loads without pickle. The file is
written to a temporary file in the same folder and renamed over the destination,
so a failed write leaves any earlier file intact.
The writer and a reader live in a new CaImAn-free module,
`calcium_imaging/motion_correction_record.py`, so reports and tests can use them
without CaImAn. The path is stored on the data manager and on
`ProcessingResult.motion_correction_shifts_filepath`, a new field with a `None`
default so positional construction keeps working. The path is reset to `None` at
the start of each motion-correction step, so a reused data manager never reports
an earlier run's file. Any failure to build or write the file (not only `OSError`)
prints a warning and does not stop the run.

The GUI output inventory (`gui/run_outputs.py`) reports the file as exported when
it was written, instead of always marking it unavailable, and the run review lists
it as a destination when motion correction is enabled.

## Compatibility

- Numerical results are unchanged: the arrays are copied after motion correction
  and nothing reads them during processing.
- When `apply_motion_correction` is true and metadata is available, runs write one
  additional compressed file (shifts are `T x 2` or `T x patches` floats plus one
  template for rigid runs or two for piecewise runs; size grows with the number of
  frames and patches). Runs without motion correction write nothing new.
- Repeated runs overwrite the file in `saved_movies/`. Unlike the estimates file,
  its name is not configurable, so runs that save estimates under different names
  still share one shifts file, and a run without motion correction leaves the
  previous file in place. `source_movie` names the input movie, not the run;
  consumers should use the path in `ProcessingResult` (which is `None` when the run
  did not write the file) or compare `saved_at` with the run time.
- `inspect_motion_correction` and its CLI behavior are untouched.

## Alternatives

- Keep the `MotionCorrect` object on the data manager only. It is lost when the
  process ends, so the GUI's separate run worker and later report could not use it.
- Patch `inspect_motion_correction` at run time from the GUI worker to save
  figures. This depends on a method the code itself calls broken and saves images
  instead of data.
- Gate the file behind a new option. Rejected as unnecessary for a small file; it
  can be added if a lab objects to the extra output.

## Unblocks

The GUI motion-correction report (x/y shift traces and templates in Results),
which is on hold until this is approved. The report would read the file with
`load_motion_correction_shifts` and list it in the run's output inventory.

## Implementation reviewed in this proposal

Save float32 shift/template arrays, patch-grid settings and source-movie identity after correction. The saved record is additional output; scientific calculations are unchanged.

## Risks

Piecewise shift arrays can be large. Outputs are overwritten on repeated runs; consumers must check `saved_at` or use the path the run reports before treating a record as current. Saving the record must not interrupt scientific processing, so every failure is caught, reported as a warning and leaves any earlier file intact. A caught `MemoryError` means the run continues close to the memory limit; the record is small next to the movie, so this is unlikely to be the step that runs out.

## Tests

- `tests/test_motion_correction_record.py`: round trip and dtypes; skipped and
  listed values (ragged shifts, int64 overflow, non-numeric `border_to_0` and frame
  rate) with pickle-free loading; any `fname` shape; exact filenames; a failed
  write keeps the earlier file and leaves no temporary file; ordinary file
  permissions; real CaImAn correction for rigid, piecewise and upsampled-grid runs,
  checking recovered shifts, saved piecewise values and that the saved settings
  reproduce the patch count; the processor writes the file, passes the corrected
  movie and unchanged border to CNMF-E, leaves the `MotionCorrect` object
  unchanged, warns and continues on any save failure or missing recording folder,
  writes nothing without metadata, and resets the path for a reused data manager.
- `tests/test_gui_run_outputs.py`: the inventory reports a written file as
  exported and an unwritten one as not computed with the right reason.
- `tests/test_gui_analysis.py`: the run review names the shifts destination only
  when motion correction is enabled.

## Verification

The patch below is the full change against base `ded08fd`, excluding this ADR.
The proposal remains `status: proposed`; publication as a draft PR is not
maintainer approval.

During review round 1 the full default suite
(`pytest tests -m "not slow"`), changed-line coverage, documentation coverage,
the documentation link check and the strict MkDocs build were run; the exact
results are in the PR. Representative recording checks remain a prerequisite
for merge.

## Diff

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 55eebaf..4066850 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -30,6 +30,11 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ### Added
 
+- Save motion-correction shifts, templates and patch settings to
+  `saved_movies/motion_correction_shifts.npz` whenever motion correction runs, and
+  report the file in `ProcessingResult.motion_correction_shifts_filepath` and in
+  the GUI's output inventory and run review. Analysis results are unchanged. If
+  the file cannot be written, the run prints a warning and continues.
 - Installed `ace-gui` workbench with per-launch API authentication and shared
   CLI/GUI defaults. CSVs remain the settings source of truth.
 - GUI feature registry and run plans: new workbench screens register their own
diff --git a/docs/api/calcium_imaging.md b/docs/api/calcium_imaging.md
index a3e80e2..a9d6960 100644
--- a/docs/api/calcium_imaging.md
+++ b/docs/api/calcium_imaging.md
@@ -12,5 +12,11 @@ This section details the pipeline for processing calcium imaging data.
 ## Processor (CNMF-E)
 ::: aceneurotools.calcium_imaging.calcium_imaging_processor.CalciumImagingProcessor
 
+## Processing result
+::: aceneurotools.calcium_imaging.pipeline_results.ProcessingResult
+
+## Motion-correction record
+::: aceneurotools.calcium_imaging.motion_correction_record
+
 ## Postprocessor
 ::: aceneurotools.calcium_imaging.calcium_imaging_postprocessor.CalciumImagingPostprocessor
diff --git a/docs/gui.md b/docs/gui.md
index 636358d..2c2d60b 100644
--- a/docs/gui.md
+++ b/docs/gui.md
@@ -171,7 +171,7 @@ spreadsheet can display. Ask the analyst to inspect those arrays.
 | Location within a run | Contents when the corresponding step succeeds |
 | --- | --- |
 | `run.log`, CSV snapshots, `effective-parameters.json` | Log and settings used for that run |
-| `recording/saved_movies/` | Processed movies, saved estimates and CaImAn settings when enabled |
+| `recording/saved_movies/` | Processed movies, saved estimates and CaImAn settings when enabled, and `motion_correction_shifts.npz` when motion correction runs |
 | `calcium_signals/meanFluorescence_<ID>.npz` | Mean fluorescence |
 | `preprocessing.npz` | Preprocessing image/timing summaries |
 | `postprocessing.npz`, `components.npz` | Available cell signals and footprints |
diff --git a/docs/guides/calcium_imaging.md b/docs/guides/calcium_imaging.md
index 75b419d..132a2d6 100644
--- a/docs/guides/calcium_imaging.md
+++ b/docs/guides/calcium_imaging.md
@@ -77,6 +77,35 @@ saving is enabled. GUI runs place that recording copy under
 events and available diagnostics; consult [Results](../gui.md#find-and-reopen-results).
 Those GUI exports are not automatically written by direct pipeline calls.
 
+When motion correction runs (`apply_motion_correction`), the per-frame shifts
+are also saved to `saved_movies/motion_correction_shifts.npz`, so the
+correction can be inspected later without running it again. Saving the file does
+not change any analysis result. Read it with
+`aceneurotools.calcium_imaging.motion_correction_record.load_motion_correction_shifts`,
+which returns a dictionary of arrays:
+
+| Key | Contents | Present |
+| --- | --- | --- |
+| `shifts_rig` | Rigid shift per frame, float32, shape `(frames, 2)`. Column 0 is the row (vertical) axis, column 1 the column (horizontal) axis. Values are the correction CaImAn applied, the negative of the movement. | Always, after motion correction |
+| `x_shifts_els`, `y_shifts_els` | Piecewise shift per frame and patch, float32, shape `(frames, patches)` | `pw_rigid` runs |
+| `total_template_rig`, `total_template_els` | Rigid and piecewise templates, float32 | Rigid always; piecewise for `pw_rigid` runs |
+| `strides`, `overlaps`, `max_shifts`, `upsample_factor_grid`, `shifts_opencv` | Motion settings that locate each patch. With `shifts_opencv` false, CaImAn reports piecewise shifts on a grid refined by `upsample_factor_grid` | Always |
+| `border_to_0` | Border width CaImAn set to zero, in pixels | Always |
+| `pw_rigid` | Whether piecewise-rigid correction was requested | Always |
+| `frame_rate` | Frame rate in Hz | When the recording's frame rate is known |
+| `source_movie` | Path of the movie the shifts were computed from | Always |
+| `saved_at` | Time the file was written, UTC, ISO 8601 | Always |
+| `skipped_attributes` | Names of values that could not be stored as numbers and were left out | Only when something was skipped |
+
+`source_movie` names the input movie, not the run: every run with the same
+preprocessing reads the same movie path. A later run without motion correction,
+or one whose save fails, leaves an earlier file in place, so compare `saved_at`
+with the time of the run, or use the path the run reports in
+`ProcessingResult.motion_correction_shifts_filepath`, which is `None` when that
+run did not write the file. The file is written to a temporary file and then
+renamed, so a failed save never leaves a partial file. If it cannot be written
+for any reason, the run prints a warning and continues.
+
 The core pipeline computes projection phases and spectra before filtering;
 those describe the unfiltered projection even if `inline=True` replaces the
 final projection with its filtered version. `inline=False` retains the original
diff --git a/src/aceneurotools/calcium_imaging/calcium_imaging_data_manager.py b/src/aceneurotools/calcium_imaging/calcium_imaging_data_manager.py
index c771a0d..3330f26 100644
--- a/src/aceneurotools/calcium_imaging/calcium_imaging_data_manager.py
+++ b/src/aceneurotools/calcium_imaging/calcium_imaging_data_manager.py
@@ -153,6 +153,7 @@ class CalciumImagingDataManager(ExperimentDataManager, ABC):
         self.preprocessed_movie_filepath = None #Your preprocessed movie must be saved to disk and its filepath stored here before processing
         self.coords = None #contains the coordinates/shape of your cropped movie
         self.motion_corrected_movie_filepath = None
+        self.motion_correction_shifts_filepath = None
         self.CNMFE_obj = None
         self.estimates_filepath = None
         self.dview = None
diff --git a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
index afb56b1..581d6c8 100644
--- a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
+++ b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
@@ -9,6 +9,7 @@ import numpy as np
 
 import aceneurotools.shared.misc_functions as misc_functions
 from aceneurotools.calcium_imaging.calcium_imaging_data_manager import CalciumImagingDataManager
+from aceneurotools.calcium_imaging.motion_correction_record import save_motion_correction_shifts
 from aceneurotools.calcium_imaging.pipeline_results import ProcessingResult
 from aceneurotools.shared.exceptions import ProcessingError
 
@@ -159,6 +160,7 @@ class CalciumImagingProcessor:
             opts_caiman_filepath=getattr(self.data_manager, 'opts_caiman_filepath', None),
             opts_caiman=self.data_manager.opts_caiman,
             motion_corrected_movie_filepath=getattr(self.data_manager, 'motion_corrected_movie_filepath', None),
+            motion_correction_shifts_filepath=getattr(self.data_manager, 'motion_correction_shifts_filepath', None),
         )
 
         return self.data_manager
@@ -189,9 +191,13 @@ class CalciumImagingProcessor:
             Updated data_manager with motion-corrected memory map.
         """
         motion_correction_object = None
+        #a reused data manager must not report an earlier run's shifts file
+        data_manager.motion_correction_shifts_filepath = None
         if apply_motion_correction:
             #apply motion correction
             motion_correction_object, data_manager.opts_caiman = self._apply_motion_correction(data_manager.opts_caiman, dview)
+            #keep the shifts and templates on disk for later, non-blocking inspection
+            data_manager.motion_correction_shifts_filepath = self._save_motion_correction_shifts(data_manager, motion_correction_object)
             #save the mmap file to disk and add that filepath to opts_caiman
             data_manager.opts_caiman = self._add_temp_mmap_to_opts_caiman(motion_correction_object.mmap_file, data_manager.opts_caiman, data_manager.opts_caiman.get('patch', 'border_pix'))
             #save the mmap file stored in motion_correction_object to data_manager
@@ -204,6 +210,25 @@ class CalciumImagingProcessor:
 
         return data_manager
 
+    def _save_motion_correction_shifts(self, dm: CalciumImagingDataManager, mc: Any) -> str | None:
+        """Save motion-correction shifts next to the estimates; return the path, or None if not written.
+
+        The record is optional output: any failure to build or write it prints a
+        warning and returns None, so the scientific run continues.
+        """
+        if dm.metadata is None:
+            return None
+        try:
+            save_dir = os.path.join(str(dm.metadata['calcium imaging directory']), "saved_movies")
+            filepath = save_motion_correction_shifts(
+                mc, save_dir, pw_rigid=bool(dm.opts_caiman.get('motion', 'pw_rigid')), frame_rate=dm.fr
+            )
+        except Exception as exc:  # optional output must never stop processing
+            print(f"Warning: motion-correction shifts could not be saved: {exc!r}")
+            return None
+        print(f"Saved motion-correction shifts to {filepath}")
+        return filepath
+
     def cleanup_tkinter(self) -> None:
         """Destroy any active Tkinter root and set the interactive matplotlib backend."""
         root = getattr(tkinter, '_default_root', None)
diff --git a/src/aceneurotools/calcium_imaging/motion_correction_record.py b/src/aceneurotools/calcium_imaging/motion_correction_record.py
new file mode 100644
index 0000000..664f29f
--- /dev/null
+++ b/src/aceneurotools/calcium_imaging/motion_correction_record.py
@@ -0,0 +1,135 @@
+"""Persist motion-correction shifts so they can be inspected after a run.
+
+CaImAn's ``MotionCorrect`` object holds the per-frame shifts and templates only
+in memory. This module copies them to a small ``.npz`` file without importing
+CaImAn, so reports can be drawn later without re-running motion correction.
+
+Shifts and templates are stored as float32 to keep piecewise-rigid files small
+(per-frame, per-patch shifts dominate the size). The file also records the
+motion settings that define the patch grid (``strides``, ``overlaps``,
+``max_shifts``, ``upsample_factor_grid`` and ``shifts_opencv``; with a
+template's shape they locate each patch), the movie the shifts were computed
+from and the time the file was written (UTC). Attributes that are missing,
+empty or not numeric are skipped rather than failing the run; their names are
+listed in ``skipped_attributes``.
+
+The file is written to a temporary file in the same directory and then renamed
+over the destination, so a failed write leaves any earlier file intact.
+"""
+
+from __future__ import annotations
+
+import contextlib
+import os
+import uuid
+from datetime import datetime, timezone
+from pathlib import Path
+from typing import Any
+
+import numpy as np
+
+MOTION_CORRECTION_SHIFTS_FILENAME = "motion_correction_shifts.npz"
+
+#: Float ``MotionCorrect`` arrays copied when present and non-empty (stored as float32).
+_FLOAT_ATTRIBUTES = (
+    "shifts_rig",
+    "x_shifts_els",
+    "y_shifts_els",
+    "total_template_rig",
+    "total_template_els",
+)
+#: Integer ``MotionCorrect`` settings describing the patch grid (stored as int64).
+#: (``coord_shifts_els`` is not saved: CaImAn 1.13 fills it with ``None`` per frame.)
+_INTEGER_ATTRIBUTES = (
+    "strides",
+    "overlaps",
+    "max_shifts",
+    "upsample_factor_grid",
+    "border_to_0",
+)
+#: Boolean ``MotionCorrect`` settings. With ``shifts_opencv=False``, CaImAn returns
+#: piecewise shifts on a grid refined by ``upsample_factor_grid``.
+_BOOLEAN_ATTRIBUTES = ("shifts_opencv",)
+
+
+def motion_correction_arrays(mc: Any, *, pw_rigid: bool, frame_rate: float | None = None) -> dict[str, np.ndarray]:
+    """Return the shift and template arrays held by a CaImAn ``MotionCorrect`` object.
+
+    Args:
+        mc: Object with CaImAn ``MotionCorrect`` attributes.
+        pw_rigid: Whether piecewise-rigid correction was requested.
+        frame_rate: Movie frame rate in Hz, recorded for plotting against time.
+    """
+    arrays: dict[str, np.ndarray] = {}
+    skipped: list[str] = []
+    for names, dtype in (
+        (_FLOAT_ATTRIBUTES, np.float32),
+        (_INTEGER_ATTRIBUTES, np.int64),
+        (_BOOLEAN_ATTRIBUTES, np.bool_),
+    ):
+        for name in names:
+            value = getattr(mc, name, None)
+            if value is None:
+                continue
+            try:
+                array = np.asarray(value, dtype=dtype)
+            except (TypeError, ValueError, OverflowError):
+                skipped.append(name)
+                continue
+            if array.size:
+                arrays[name] = array
+    arrays["pw_rigid"] = np.asarray(bool(pw_rigid))
+    if frame_rate is not None:
+        try:
+            arrays["frame_rate"] = np.asarray(float(frame_rate))
+        except (TypeError, ValueError):
+            skipped.append("frame_rate")
+    source = getattr(mc, "fname", None)
+    if source is not None:
+        names = [source] if isinstance(source, (str, Path)) else np.ravel(np.asarray(source, dtype=object)).tolist()
+        names = [str(name) for name in names if name is not None]
+        if names:
+            arrays["source_movie"] = np.asarray(names)
+    arrays["saved_at"] = np.asarray(datetime.now(timezone.utc).isoformat(timespec="seconds"))
+    if skipped:
+        arrays["skipped_attributes"] = np.asarray(skipped)
+    return arrays
+
+
+def save_motion_correction_shifts(
+    mc: Any,
+    directory: str | Path,
+    *,
+    pw_rigid: bool,
+    frame_rate: float | None = None,
+    filename: str = MOTION_CORRECTION_SHIFTS_FILENAME,
+) -> str:
+    """Write the motion-correction shifts and templates to ``directory/filename``.
+
+    The file is written to a temporary file first and then renamed, so a failed
+    write never leaves a partial file at ``directory/filename``. The name is used
+    exactly as given (no ``.npz`` suffix is added).
+
+    Returns:
+        The written file path.
+    """
+    arrays = motion_correction_arrays(mc, pw_rigid=pw_rigid, frame_rate=frame_rate)
+    target = Path(directory) / filename
+    target.parent.mkdir(parents=True, exist_ok=True)
+    # A unique name opened with open() (not mkstemp) keeps the umask's usual permissions.
+    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
+    try:
+        with open(temporary, "xb") as stream:
+            np.savez_compressed(stream, **arrays)
+        os.replace(temporary, target)
+    except BaseException:
+        with contextlib.suppress(OSError):
+            os.unlink(temporary)
+        raise
+    return str(target)
+
+
+def load_motion_correction_shifts(path: str | Path) -> dict[str, np.ndarray]:
+    """Read a file written by :func:`save_motion_correction_shifts`."""
+    with np.load(path) as data:
+        return {name: data[name] for name in data.files}
diff --git a/src/aceneurotools/calcium_imaging/pipeline_results.py b/src/aceneurotools/calcium_imaging/pipeline_results.py
index bb3f962..983b003 100644
--- a/src/aceneurotools/calcium_imaging/pipeline_results.py
+++ b/src/aceneurotools/calcium_imaging/pipeline_results.py
@@ -49,6 +49,9 @@ class ProcessingResult:
         opts_caiman: CaImAn ``CNMFParams`` object used during processing.
         motion_corrected_movie_filepath: Path to the motion-corrected memory
             map, or ``None`` if motion correction was not applied.
+        motion_correction_shifts_filepath: Path to the saved per-frame shifts
+            and templates (``motion_correction_shifts.npz``), or ``None`` if
+            motion correction was not applied or the file was not written.
     """
 
     CNMFE_obj: Any
@@ -56,6 +59,7 @@ class ProcessingResult:
     opts_caiman_filepath: str | None
     opts_caiman: Any
     motion_corrected_movie_filepath: str | None
+    motion_correction_shifts_filepath: str | None = None
 
 
 @accept_legacy_keywords(miniscope_phases="calcium_imaging_phases")
diff --git a/src/aceneurotools/gui/run_outputs.py b/src/aceneurotools/gui/run_outputs.py
index b3facf2..451171a 100644
--- a/src/aceneurotools/gui/run_outputs.py
+++ b/src/aceneurotools/gui/run_outputs.py
@@ -168,12 +168,10 @@ def miniscope_outputs(report, dm):
         ("caiman_parameters", "opts_caiman_filepath", "save_CNMFE_params"),
         ("preprocessed_movie", "preprocessed_movie_filepath", None),
         ("motion_corrected_movie", "motion_corrected_movie_filepath", "apply_motion_correction"),
+        ("motion_correction_shifts", "motion_correction_shifts_filepath", "apply_motion_correction"),
     ]:
         report.artifact(name, getattr(dm, attribute, None), flag)
     report.missing("correlation_pnr_diagnostics", reason="Interactive plot diagnostics are not computed by the GUI run")
-    report.missing(
-        "motion_correction_shifts", reason="The core pipeline does not retain a motion-correction object or shifts"
-    )
     report.diagnostics.update(
         neuron_count=len(ids) if ids is not None else None,
         inline_requested=params.get("inline"),
diff --git a/src/aceneurotools/gui/runs.py b/src/aceneurotools/gui/runs.py
index ca3afaf..3fd6658 100644
--- a/src/aceneurotools/gui/runs.py
+++ b/src/aceneurotools/gui/runs.py
@@ -252,6 +252,10 @@ class Runs:
                     / "saved_movies"
                     / str(params.get("save_CNMFE_estimates_filename", "estimates.hdf5"))
                 )
+            if params.get("apply_motion_correction"):
+                destinations["Motion-correction shifts (when written)"] = str(
+                    directory / "recording" / "saved_movies" / "motion_correction_shifts.npz"
+                )
             if params.get("save_CNMFE_params"):
                 destinations["CaImAn parameters"] = str(directory / "recording" / "saved_movies" / "opts_caiman.json")
         if kind == "multimodal":
diff --git a/tests/test_gui_analysis.py b/tests/test_gui_analysis.py
index f74d988..6b98308 100644
--- a/tests/test_gui_analysis.py
+++ b/tests/test_gui_analysis.py
@@ -142,6 +142,20 @@ def test_cnmfe_review_names_exact_destinations_and_respects_disabled_outputs(rec
     assert "Neuron estimates" not in review["destinations"]
 
 
+@pytest.mark.parametrize("apply", ["True", "False"])
+def test_cnmfe_review_names_the_motion_correction_shifts_destination(recording, apply):
+    root, frames = recording
+    project = Project.open(root)
+    project.parameters["1"]["apply_motion_correction"] = apply
+    review = Runs().review(project, payload(project, kind="miniscope"))
+    directory = Path(review["directory"])
+    label = "Motion-correction shifts (when written)"
+    if apply == "True":
+        assert review["destinations"][label] == str(directory / "recording/saved_movies/motion_correction_shifts.npz")
+    else:
+        assert label not in review["destinations"]
+
+
 def test_changed_recording_and_missing_data_block_execution(recording):
     root, frames = recording
     project = Project.open(root)
diff --git a/tests/test_gui_run_outputs.py b/tests/test_gui_run_outputs.py
index cf7b574..210cd79 100644
--- a/tests/test_gui_run_outputs.py
+++ b/tests/test_gui_run_outputs.py
@@ -171,3 +171,41 @@ def test_numeric_object_diagnostics_are_exported_without_pickle(tmp_path):
         np.testing.assert_array_equal(saved["neurons_sn"], [119.5, 116.25])
         assert saved["neurons_sn"].dtype.kind == "f"
         np.testing.assert_array_equal(saved["g"], [[0.8], [0.9]])
+
+
+def test_inventory_reports_a_written_motion_correction_shifts_file(worker_case, monkeypatch):
+    from aceneurotools.pipelines import calcium_imaging as miniscope
+
+    root, manifest, dm = worker_case
+    manifest["parameters"]["apply_motion_correction"] = True
+    shifts = root / "recording" / "saved_movies" / "motion_correction_shifts.npz"
+
+    class WritesShifts(miniscope.CalciumImagingPipeline):
+        def run(self, **params):
+            # The core writes the file into the run's recording copy during motion correction.
+            shifts.parent.mkdir(parents=True, exist_ok=True)
+            np.savez(shifts, shifts_rig=np.zeros((20, 2), dtype=np.float32))
+            dm.motion_correction_shifts_filepath = str(shifts)
+            return super().run(**params)
+
+    monkeypatch.setattr(miniscope, "CalciumImagingPipeline", WritesShifts)
+    execute(manifest)
+    entries = {item["name"]: item for item in json.loads((root / "output-inventory.json").read_text())["outputs"]}
+    assert entries["motion_correction_shifts"] == {
+        "name": "motion_correction_shifts",
+        "status": "exported",
+        "file": "recording/saved_movies/motion_correction_shifts.npz",
+    }
+
+
+@pytest.mark.parametrize("apply", [False, True])
+def test_inventory_marks_unwritten_motion_correction_shifts_not_computed(worker_case, apply):
+    root, manifest, dm = worker_case
+    manifest["parameters"]["apply_motion_correction"] = apply
+    dm.motion_correction_shifts_filepath = None
+    execute(manifest)
+    entries = {item["name"]: item for item in json.loads((root / "output-inventory.json").read_text())["outputs"]}
+    entry = entries["motion_correction_shifts"]
+    assert entry["status"] == "not_computed"
+    assert ("apply_motion_correction disabled" in entry["reason"]) is (not apply)
+    assert "does not retain" not in entry["reason"]
diff --git a/tests/test_motion_correction_record.py b/tests/test_motion_correction_record.py
new file mode 100644
index 0000000..d954f5c
--- /dev/null
+++ b/tests/test_motion_correction_record.py
@@ -0,0 +1,356 @@
+"""Motion-correction shifts are saved during processing and read back unchanged."""
+
+import os
+import stat
+from datetime import datetime
+from pathlib import Path
+from types import SimpleNamespace
+
+import numpy as np
+import pytest
+
+from aceneurotools.calcium_imaging import calcium_imaging_processor as processor_module
+from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor
+from aceneurotools.calcium_imaging.motion_correction_record import (
+    MOTION_CORRECTION_SHIFTS_FILENAME,
+    load_motion_correction_shifts,
+    motion_correction_arrays,
+    save_motion_correction_shifts,
+)
+from aceneurotools.calcium_imaging.pipeline_results import ProcessingResult
+
+
+def fake_mc(pw_rigid, fname=("movie.tif",)):
+    rng = np.random.default_rng(0)
+    return SimpleNamespace(
+        shifts_rig=[tuple(row) for row in rng.normal(size=(50, 2))],
+        x_shifts_els=rng.normal(size=(50, 4)).tolist() if pw_rigid else [],
+        y_shifts_els=rng.normal(size=(50, 4)).tolist() if pw_rigid else [],
+        total_template_rig=rng.random((16, 16)),
+        total_template_els=rng.random((16, 16)) if pw_rigid else None,
+        strides=(8, 8),
+        overlaps=(4, 4),
+        max_shifts=(3, 3),
+        coord_shifts_els=[None] * 50,  # What CaImAn 1.13 stores; must be skipped, not crash.
+        border_to_0=3,
+        upsample_factor_grid=4,
+        shifts_opencv=True,
+        fname=list(fname),
+    )
+
+
+@pytest.mark.parametrize("pw_rigid", [False, True])
+def test_shifts_round_trip_as_float32_with_patch_grid_and_source(tmp_path, pw_rigid):
+    mc = fake_mc(pw_rigid)
+    path = save_motion_correction_shifts(mc, tmp_path / "saved_movies", pw_rigid=pw_rigid, frame_rate=20.0)
+
+    assert path == str(tmp_path / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME)
+    saved = load_motion_correction_shifts(path)
+    for name in ["shifts_rig", "total_template_rig"]:
+        assert saved[name].dtype == np.float32
+        np.testing.assert_allclose(saved[name], np.asarray(getattr(mc, name)), rtol=1e-6)
+    np.testing.assert_array_equal(saved["strides"], [8, 8])
+    np.testing.assert_array_equal(saved["overlaps"], [4, 4])
+    np.testing.assert_array_equal(saved["max_shifts"], [3, 3])
+    assert saved["source_movie"].tolist() == ["movie.tif"]
+    assert bool(saved["pw_rigid"]) is pw_rigid
+    assert float(saved["frame_rate"]) == 20.0
+    assert int(saved["border_to_0"]) == 3 and saved["border_to_0"].dtype == np.int64
+    assert int(saved["upsample_factor_grid"]) == 4
+    assert bool(saved["shifts_opencv"]) is True
+    assert datetime.fromisoformat(str(saved["saved_at"])).tzinfo is not None
+    assert "coord_shifts_els" not in saved
+    assert "skipped_attributes" not in saved
+    if pw_rigid:
+        for name in ["x_shifts_els", "y_shifts_els", "total_template_els"]:
+            assert saved[name].dtype == np.float32
+            np.testing.assert_allclose(saved[name], np.asarray(getattr(mc, name)), rtol=1e-6)
+    else:
+        # Empty piecewise lists and missing templates are omitted rather than saved as empty arrays.
+        assert {"x_shifts_els", "y_shifts_els", "total_template_els"}.isdisjoint(saved)
+
+
+def test_missing_and_unconvertible_attributes_are_skipped():
+    assert set(motion_correction_arrays(SimpleNamespace(), pw_rigid=False)) == {"pw_rigid", "saved_at"}
+    odd = SimpleNamespace(shifts_rig=["left", "right"], strides="wide", fname="single.tif")
+    arrays = motion_correction_arrays(odd, pw_rigid=True)
+    assert set(arrays) == {"pw_rigid", "source_movie", "saved_at", "skipped_attributes"}
+    assert arrays["source_movie"].tolist() == ["single.tif"]
+    assert arrays["skipped_attributes"].tolist() == ["shifts_rig", "strides"]
+
+
+def test_values_that_would_break_the_file_are_skipped_and_listed(tmp_path):
+    odd = SimpleNamespace(
+        x_shifts_els=[[1.0, 2.0], [3.0]],  # ragged
+        strides=(2**70, 1),  # overflows int64
+        border_to_0={"not": "a number"},  # would become a pickled object array
+    )
+    path = save_motion_correction_shifts(odd, tmp_path, pw_rigid=True, frame_rate="fast")
+    saved = load_motion_correction_shifts(path)  # loads without allow_pickle
+    assert saved["skipped_attributes"].tolist() == [
+        "x_shifts_els", "strides", "border_to_0", "frame_rate"
+    ]
+    assert set(saved) == {"pw_rigid", "saved_at", "skipped_attributes"}
+
+
+@pytest.mark.parametrize(
+    "fname, expected",
+    [
+        (Path("one.tif"), ["one.tif"]),
+        (np.array(["a.tif", "b.tif"]), ["a.tif", "b.tif"]),
+        (("a.tif", None), ["a.tif"]),
+        (5, ["5"]),
+        ([], None),
+    ],
+)
+def test_source_movie_accepts_any_fname_shape(fname, expected):
+    arrays = motion_correction_arrays(SimpleNamespace(fname=fname), pw_rigid=False)
+    if expected is None:
+        assert "source_movie" not in arrays
+    else:
+        assert arrays["source_movie"].tolist() == expected
+
+
+def test_a_filename_without_npz_suffix_is_written_exactly(tmp_path):
+    path = save_motion_correction_shifts(fake_mc(False), tmp_path, pw_rigid=False, filename="shifts")
+    assert path == str(tmp_path / "shifts")
+    assert sorted(p.name for p in tmp_path.iterdir()) == ["shifts"]
+    assert load_motion_correction_shifts(path)["shifts_rig"].shape == (50, 2)
+
+
+def test_a_failed_write_keeps_the_earlier_file_and_leaves_no_temporary(tmp_path, monkeypatch):
+    target = tmp_path / MOTION_CORRECTION_SHIFTS_FILENAME
+    save_motion_correction_shifts(fake_mc(False), tmp_path, pw_rigid=False, frame_rate=10.0)
+    before = target.read_bytes()
+
+    def explode(file, **arrays):
+        # Fail part-way through, after some bytes have reached the file.
+        if isinstance(file, (str, os.PathLike)):
+            with open(file, "wb") as partial:
+                partial.write(b"PK partial")
+        else:
+            file.write(b"PK partial")
+        raise MemoryError("no room")
+
+    monkeypatch.setattr(np, "savez_compressed", explode)
+    with pytest.raises(MemoryError):
+        save_motion_correction_shifts(fake_mc(True), tmp_path, pw_rigid=True)
+    assert target.read_bytes() == before
+    assert sorted(p.name for p in tmp_path.iterdir()) == [MOTION_CORRECTION_SHIFTS_FILENAME]
+
+
+def test_the_written_file_has_ordinary_permissions(tmp_path):
+    previous = os.umask(0o022)
+    try:
+        path = save_motion_correction_shifts(fake_mc(False), tmp_path, pw_rigid=False)
+    finally:
+        os.umask(previous)
+    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
+
+
+def test_processing_result_keeps_positional_compatibility():
+    result = ProcessingResult(None, None, None, None, None)
+    assert result.motion_correction_shifts_filepath is None
+
+
+# Real CaImAn motion correction on a synthetic movie with known shifts.
+
+
+def synthetic_movie(path):
+    import tifffile
+
+    rng = np.random.default_rng(0)
+    yy, xx = np.mgrid[:64, :64]
+    base = sum(np.exp(-((yy - y) ** 2 + (xx - x) ** 2) / 8.0) for y, x in rng.uniform(10, 54, size=(12, 2)))
+    known = np.array([(int(2 * np.sin(t / 10)), int(2 * np.cos(t / 13))) for t in range(120)])
+    frames = [np.roll(base, tuple(shift), axis=(0, 1)) * 100 + 5 + rng.normal(0, 0.5, (64, 64)) for shift in known]
+    tifffile.imwrite(path, np.asarray(frames, dtype=np.float32))
+    return known
+
+
+@pytest.mark.parametrize(
+    "pw_rigid, shifts_opencv", [(False, True), (True, True), (True, False)], ids=["rigid", "pw-opencv", "pw-upsampled"]
+)
+def test_real_motion_correction_shifts_recover_the_injected_motion(tmp_path, monkeypatch, pw_rigid, shifts_opencv):
+    monkeypatch.setenv("CAIMAN_TEMP", str(tmp_path / "caiman-temp"))
+    (tmp_path / "caiman-temp").mkdir()
+    from caiman.motion_correction import MotionCorrect, get_patch_centers
+
+    movie = str(tmp_path / "synthetic.tif")
+    known = synthetic_movie(movie)
+    mc = MotionCorrect(
+        movie, dview=None, max_shifts=(4, 4), strides=(32, 32), overlaps=(16, 16),
+        max_deviation_rigid=3, pw_rigid=pw_rigid, border_nan="copy",
+        shifts_opencv=shifts_opencv, upsample_factor_grid=2,
+    )
+    mc.motion_correct(save_movie=False)
+    saved = load_motion_correction_shifts(save_motion_correction_shifts(mc, tmp_path, pw_rigid=pw_rigid, frame_rate=20))
+
+    # CaImAn reports the correction, which is the negative of the injected displacement.
+    assert saved["shifts_rig"].shape == (120, 2)
+    assert np.max(np.abs(saved["shifts_rig"] + known)) < 0.5
+    assert saved["source_movie"].tolist() == [movie]
+    # Keys the guide documents as always present after real motion correction.
+    always = {"shifts_rig", "total_template_rig", "strides", "overlaps", "max_shifts", "upsample_factor_grid",
+              "shifts_opencv", "border_to_0", "pw_rigid", "frame_rate", "source_movie", "saved_at"}
+    assert always <= set(saved) and "skipped_attributes" not in saved
+    assert bool(saved["shifts_opencv"]) is shifts_opencv and int(saved["upsample_factor_grid"]) == 2
+    if pw_rigid:
+        assert saved["x_shifts_els"].shape[0] == 120 and saved["x_shifts_els"].shape == saved["y_shifts_els"].shape
+        assert saved["total_template_els"].shape == saved["total_template_rig"].shape == (64, 64)
+        for name in ["x_shifts_els", "y_shifts_els"]:
+            np.testing.assert_allclose(saved[name], np.asarray(mc.__dict__[name], dtype=np.float32))
+        # The saved settings alone locate every patch the shifts belong to.
+        centers = get_patch_centers(
+            saved["total_template_rig"].shape,
+            overlaps=tuple(saved["overlaps"]),
+            strides=tuple(saved["strides"]),
+            shifts_opencv=bool(saved["shifts_opencv"]),
+            upsample_factor_grid=int(saved["upsample_factor_grid"]),
+        )
+        assert np.prod([len(axis) for axis in centers]) == saved["x_shifts_els"].shape[1]
+    else:
+        assert "x_shifts_els" not in saved
+
+
+# The processor writes the file during motion correction and reports it.
+
+
+class FakeOpts:
+    def __init__(self, pw_rigid=False):
+        self.values = {("motion", "pw_rigid"): pw_rigid, ("patch", "border_pix"): 0, ("data", "fnames"): ["movie.mmap"]}
+
+    def get(self, group, key):
+        return self.values[(group, key)]
+
+    def change_params(self, params):
+        pass
+
+
+def bare_processor(tmp_path, monkeypatch, metadata=True, pw_rigid=False):
+    manager = SimpleNamespace(
+        metadata={"calcium imaging directory": str(tmp_path / "recording")} if metadata else None,
+        opts_caiman=FakeOpts(pw_rigid),
+        fr=20.0,
+        motion_correction_shifts_filepath=None,
+        motion_corrected_movie_filepath=None,
+        movie=None,
+        CNMFE_obj=None,
+        estimates_filepath=None,
+    )
+    processor = object.__new__(CalciumImagingProcessor)
+    processor.data_manager = manager
+    processor.preprocessed_movie = None
+    calls = []
+    mc = fake_mc(pw_rigid)
+    mc.mmap_file = ["corrected.mmap"]
+
+    def apply(opts, dview=None):
+        calls.append("apply")
+        return mc, opts
+
+    def add_mmap(mmap, opts, border_pix, *args):
+        calls.append(("mmap", mmap, border_pix))
+        return opts
+
+    monkeypatch.setattr(processor, "_apply_motion_correction", apply)
+    monkeypatch.setattr(processor, "_add_temp_mmap_to_opts_caiman", add_mmap)
+    processor.mc = mc
+    return processor, manager, calls
+
+
+def test_motion_correction_writes_shifts_next_to_the_estimates(tmp_path, monkeypatch, capsys):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch, pw_rigid=True)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+
+    expected = tmp_path / "recording" / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME
+    # Saving does not change what CNMF-E receives: the corrected mmap and the unchanged border.
+    assert calls == ["apply", ("mmap", ["corrected.mmap"], 0)]
+    assert manager.motion_correction_shifts_filepath == str(expected)
+    saved = load_motion_correction_shifts(expected)
+    assert bool(saved["pw_rigid"]) is True and float(saved["frame_rate"]) == 20.0
+    assert "x_shifts_els" in saved
+    assert f"Saved motion-correction shifts to {expected}" in capsys.readouterr().out
+
+
+def test_no_shifts_file_without_motion_correction(tmp_path, monkeypatch):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=False, inspect_motion_correction=False)
+    assert calls == [("mmap", ["movie.mmap"], 0)] and manager.motion_correction_shifts_filepath is None
+    assert not (tmp_path / "recording").exists()
+
+
+def test_no_shifts_file_without_metadata(tmp_path, monkeypatch):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch, metadata=False)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    assert calls == ["apply", ("mmap", ["corrected.mmap"], 0)] and manager.motion_correction_shifts_filepath is None
+    assert list(tmp_path.rglob("*")) == []
+
+
+def test_a_failed_shifts_write_warns_and_processing_continues(tmp_path, monkeypatch, capsys):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch)
+
+    def refuse(*args, **kwargs):
+        raise PermissionError("read-only recording folder")
+
+    monkeypatch.setattr(processor_module, "save_motion_correction_shifts", refuse)
+    returned = processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    assert returned is manager and manager.motion_correction_shifts_filepath is None
+    assert calls[-1] == ("mmap", ["corrected.mmap"], 0)
+    out = capsys.readouterr().out
+    assert "Warning: motion-correction shifts could not be saved: PermissionError('read-only recording folder')" in out
+
+
+@pytest.mark.parametrize("error", [ValueError("odd fname"), MemoryError(), OverflowError("too big"), TypeError("x")])
+def test_any_save_failure_warns_and_processing_continues(tmp_path, monkeypatch, capsys, error):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch)
+
+    def fail(*args, **kwargs):
+        raise error
+
+    monkeypatch.setattr(processor_module, "save_motion_correction_shifts", fail)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    assert manager.motion_correction_shifts_filepath is None
+    assert calls[-1] == ("mmap", ["corrected.mmap"], 0)
+    assert f"could not be saved: {error!r}" in capsys.readouterr().out
+
+
+def test_metadata_without_a_recording_directory_warns_and_continues(tmp_path, monkeypatch, capsys):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch)
+    manager.metadata = {}
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    assert manager.motion_correction_shifts_filepath is None and calls[-1][0] == "mmap"
+    assert "could not be saved: KeyError('calcium imaging directory')" in capsys.readouterr().out
+
+
+def test_saving_leaves_the_motion_correction_object_unchanged(tmp_path, monkeypatch):
+    processor, manager, _ = bare_processor(tmp_path, monkeypatch, pw_rigid=True)
+    before = {name: np.array(value, dtype=object) for name, value in vars(processor.mc).items()}
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    after = vars(processor.mc)
+    assert set(after) == set(before)
+    for name, value in before.items():
+        np.testing.assert_array_equal(np.array(after[name], dtype=object), value)
+
+
+def test_a_reused_manager_does_not_report_an_earlier_shifts_file(tmp_path, monkeypatch):
+    processor, manager, _ = bare_processor(tmp_path, monkeypatch)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    first = manager.motion_correction_shifts_filepath
+    assert first is not None
+    processor.motion_correction_manager(manager, None, apply_motion_correction=False, inspect_motion_correction=False)
+    assert manager.motion_correction_shifts_filepath is None
+    assert Path(first).is_file()  # the earlier file is left in place, as documented
+
+
+def test_processing_result_reports_the_shifts_file(tmp_path, monkeypatch):
+    processor, manager, _ = bare_processor(tmp_path, monkeypatch)
+    monkeypatch.setattr(processor, "cnmfe_parameter_handler", lambda dm, plot_params=False: (dm, np.zeros((3, 4, 4))))
+    monkeypatch.setattr(processor, "_save_processed_data", lambda dm, *args: dm)
+    monkeypatch.setattr(processor_module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: SimpleNamespace())
+    monkeypatch.setattr(processor_module.cm, "stop_server", lambda dview=None: None)
+
+    processor.process_calcium_movie(parallel=False, apply_motion_correction=True, run_CNMFE=False, save_estimates=False)
+    expected = str(Path(tmp_path) / "recording" / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME)
+    assert processor.result.motion_correction_shifts_filepath == expected
+    assert manager.motion_correction_shifts_filepath == expected
```
