---
status: proposed
---

# Save motion-correction shifts for later inspection

## Context

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
`total_template_els`) plus `pw_rigid`, `border_to_0` and the frame rate to
`<calcium imaging directory>/saved_movies/motion_correction_shifts.npz`, the
folder that already receives `estimates.hdf5` (`_save_processed_data`, line 492).
The writer and a reader live in a new CaImAn-free module,
`calcium_imaging/motion_correction_record.py`, so reports and tests can use them
without CaImAn. The path is stored on the data manager and on
`ProcessingResult.motion_correction_shifts_filepath`, a new field with a `None`
default so positional construction keeps working. A write failure prints a
warning and does not stop the run.

## Compatibility

- Numerical results are unchanged: the arrays are copied after motion correction
  and nothing reads them during processing.
- When `apply_motion_correction` is true and metadata is available, runs write one
  additional compressed file (shifts are `T x 2` or `T x patches` floats plus two
  templates; size grows with the number of frames and patches). Runs without motion correction write
  nothing new.
- Repeated runs overwrite the file in `saved_movies/`, as they already overwrite
  the default `estimates.hdf5`.
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

Piecewise shift arrays can be large. Outputs are overwritten on repeated runs; consumers must check source identity before treating a record as current. Saving metadata must not interrupt scientific processing.

## Tests

Focused regression tests: `tests/test_motion_correction_record.py`.

## Verification

The exact implementation patch below is taken from the reviewed verification branch against base `ded08fd`. The proposal remains `status: proposed`; publication as a draft PR is not maintainer approval.

Focused tests are rerun during PR preparation, with exact results recorded in the PR description. Earlier full-suite attempts were interrupted because this environment denied localhost socket creation; the same restriction reproduced on unchanged main. No green full-suite result is claimed. Full tests, changed-line coverage, strict documentation build and representative recording checks remain prerequisites for merge.

## Diff

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 55eebaf..a2a8834 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -30,6 +30,9 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ### Added
 
+- Save motion-correction shifts, templates and patch settings to
+  `saved_movies/motion_correction_shifts.npz` whenever motion correction runs, and
+  report the file in `ProcessingResult.motion_correction_shifts_filepath`.
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
diff --git a/docs/guides/calcium_imaging.md b/docs/guides/calcium_imaging.md
index 75b419d..e6e7855 100644
--- a/docs/guides/calcium_imaging.md
+++ b/docs/guides/calcium_imaging.md
@@ -77,6 +77,17 @@ saving is enabled. GUI runs place that recording copy under
 events and available diagnostics; consult [Results](../gui.md#find-and-reopen-results).
 Those GUI exports are not automatically written by direct pipeline calls.
 
+When motion correction runs (`apply_motion_correction`), the per-frame shifts
+are also saved to `saved_movies/motion_correction_shifts.npz`, so the
+correction can be inspected later without running it again. The file holds the
+rigid shifts, the piecewise shifts when `pw_rigid` is on, the templates, the patch
+settings (`strides`, `overlaps`, `max_shifts`), the frame rate and the movie the
+shifts came from (`source_movie`). Read it with
+`aceneurotools.calcium_imaging.motion_correction_record.load_motion_correction_shifts`.
+A later run without motion correction leaves an earlier file in place; check
+`source_movie` to see which run wrote it. If the file cannot be written, the run
+prints a warning and continues.
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
index afb56b1..eb5d2b4 100644
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
@@ -192,6 +194,8 @@ class CalciumImagingProcessor:
         if apply_motion_correction:
             #apply motion correction
             motion_correction_object, data_manager.opts_caiman = self._apply_motion_correction(data_manager.opts_caiman, dview)
+            #keep the shifts and templates on disk for later, non-blocking inspection
+            data_manager.motion_correction_shifts_filepath = self._save_motion_correction_shifts(data_manager, motion_correction_object)
             #save the mmap file to disk and add that filepath to opts_caiman
             data_manager.opts_caiman = self._add_temp_mmap_to_opts_caiman(motion_correction_object.mmap_file, data_manager.opts_caiman, data_manager.opts_caiman.get('patch', 'border_pix'))
             #save the mmap file stored in motion_correction_object to data_manager
@@ -204,6 +208,21 @@ class CalciumImagingProcessor:
 
         return data_manager
 
+    def _save_motion_correction_shifts(self, dm: CalciumImagingDataManager, mc: Any) -> str | None:
+        """Save motion-correction shifts next to the estimates; return the path, or None without metadata."""
+        if dm.metadata is None:
+            return None
+        save_dir = os.path.join(str(dm.metadata['calcium imaging directory']), "saved_movies")
+        try:
+            filepath = save_motion_correction_shifts(
+                mc, save_dir, pw_rigid=bool(dm.opts_caiman.get('motion', 'pw_rigid')), frame_rate=dm.fr
+            )
+        except OSError as exc:
+            print(f"Warning: motion-correction shifts could not be saved: {exc}")
+            return None
+        print(f"Saved motion-correction shifts to {filepath}")
+        return filepath
+
     def cleanup_tkinter(self) -> None:
         """Destroy any active Tkinter root and set the interactive matplotlib backend."""
         root = getattr(tkinter, '_default_root', None)
diff --git a/src/aceneurotools/calcium_imaging/motion_correction_record.py b/src/aceneurotools/calcium_imaging/motion_correction_record.py
new file mode 100644
index 0000000..5b248af
--- /dev/null
+++ b/src/aceneurotools/calcium_imaging/motion_correction_record.py
@@ -0,0 +1,97 @@
+"""Persist motion-correction shifts so they can be inspected after a run.
+
+CaImAn's ``MotionCorrect`` object holds the per-frame shifts and templates only
+in memory. This module copies them to a small ``.npz`` file without importing
+CaImAn, so reports can be drawn later without re-running motion correction.
+
+Shifts and templates are stored as float32 to keep piecewise-rigid files small
+(per-frame, per-patch shifts dominate the size). The file also records the
+motion settings that define the patch grid (``strides``, ``overlaps``,
+``max_shifts``; with a template's shape they locate each patch), and the movie
+the shifts were computed from, so a report can check that a file in
+``saved_movies/`` belongs to the run it is describing. Attributes that are
+missing, empty or not numeric are skipped rather than failing the run.
+"""
+
+from __future__ import annotations
+
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
+)
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
+    for names, dtype in ((_FLOAT_ATTRIBUTES, np.float32), (_INTEGER_ATTRIBUTES, np.int64)):
+        for name in names:
+            value = getattr(mc, name, None)
+            if value is None:
+                continue
+            try:
+                array = np.asarray(value, dtype=dtype)
+            except (TypeError, ValueError):
+                continue
+            if array.size:
+                arrays[name] = array
+    arrays["pw_rigid"] = np.asarray(bool(pw_rigid))
+    border = getattr(mc, "border_to_0", None)
+    if border is not None:
+        arrays["border_to_0"] = np.asarray(border)
+    if frame_rate is not None:
+        arrays["frame_rate"] = np.asarray(float(frame_rate))
+    source = getattr(mc, "fname", None)
+    if source:
+        names = [source] if isinstance(source, (str, Path)) else list(source)
+        arrays["source_movie"] = np.asarray([str(name) for name in names])
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
+    Returns:
+        The written file path.
+    """
+    target = Path(directory) / filename
+    target.parent.mkdir(parents=True, exist_ok=True)
+    np.savez_compressed(target, **motion_correction_arrays(mc, pw_rigid=pw_rigid, frame_rate=frame_rate))
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
diff --git a/tests/test_motion_correction_record.py b/tests/test_motion_correction_record.py
new file mode 100644
index 0000000..71cf155
--- /dev/null
+++ b/tests/test_motion_correction_record.py
@@ -0,0 +1,207 @@
+"""Motion-correction shifts are saved during processing and read back unchanged."""
+
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
+    assert int(saved["border_to_0"]) == 3
+    assert "coord_shifts_els" not in saved
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
+    assert set(motion_correction_arrays(SimpleNamespace(), pw_rigid=False)) == {"pw_rigid"}
+    odd = SimpleNamespace(shifts_rig=["left", "right"], strides="wide", fname="single.tif")
+    arrays = motion_correction_arrays(odd, pw_rigid=True)
+    assert set(arrays) == {"pw_rigid", "source_movie"}
+    assert arrays["source_movie"].tolist() == ["single.tif"]
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
+@pytest.mark.parametrize("pw_rigid", [False, True])
+def test_real_motion_correction_shifts_recover_the_injected_motion(tmp_path, monkeypatch, pw_rigid):
+    monkeypatch.setenv("CAIMAN_TEMP", str(tmp_path / "caiman-temp"))
+    (tmp_path / "caiman-temp").mkdir()
+    from caiman.motion_correction import MotionCorrect
+
+    movie = str(tmp_path / "synthetic.tif")
+    known = synthetic_movie(movie)
+    mc = MotionCorrect(
+        movie, dview=None, max_shifts=(4, 4), strides=(32, 32), overlaps=(16, 16),
+        max_deviation_rigid=3, pw_rigid=pw_rigid, border_nan="copy",
+    )
+    mc.motion_correct(save_movie=False)
+    saved = load_motion_correction_shifts(save_motion_correction_shifts(mc, tmp_path, pw_rigid=pw_rigid, frame_rate=20))
+
+    # CaImAn reports the correction, which is the negative of the injected displacement.
+    assert saved["shifts_rig"].shape == (120, 2)
+    assert np.max(np.abs(saved["shifts_rig"] + known)) < 0.5
+    assert saved["source_movie"].tolist() == [movie]
+    if pw_rigid:
+        assert saved["x_shifts_els"].shape[0] == 120 and saved["x_shifts_els"].shape == saved["y_shifts_els"].shape
+        assert saved["total_template_els"].shape == saved["total_template_rig"].shape == (64, 64)
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
+    monkeypatch.setattr(processor, "_apply_motion_correction", apply)
+    monkeypatch.setattr(processor, "_add_temp_mmap_to_opts_caiman", lambda *args, **kwargs: manager.opts_caiman)
+    return processor, manager, calls
+
+
+def test_motion_correction_writes_shifts_next_to_the_estimates(tmp_path, monkeypatch, capsys):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch, pw_rigid=True)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+
+    expected = tmp_path / "recording" / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME
+    assert calls == ["apply"]
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
+    assert calls == [] and manager.motion_correction_shifts_filepath is None
+    assert not (tmp_path / "recording").exists()
+
+
+def test_no_shifts_file_without_metadata(tmp_path, monkeypatch):
+    processor, manager, calls = bare_processor(tmp_path, monkeypatch, metadata=False)
+    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
+    assert calls == ["apply"] and manager.motion_correction_shifts_filepath is None
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
+    assert "Warning: motion-correction shifts could not be saved: read-only recording folder" in capsys.readouterr().out
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
