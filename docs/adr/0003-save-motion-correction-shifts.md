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
  templates; typically well under a few MB). Runs without motion correction write
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

## Verification

Diff not test-verified: no test environment was available. The diff applies to
base commit `9e47959` and every changed Python file passed
`python -m py_compile`. Once the locked environment exists (`environment.yml` /
`conda-lock.yml`, then `pip install -e ".[dev]"`), run:

```sh
python -m pytest tests/test_motion_correction_record.py -q
python -m pytest tests/test_gui_run_outputs.py tests/test_miniscope_filtering.py tests/test_gui_parity.py -q
python -m pytest -q
```

## Diff

```diff
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
index 0000000..b788ecb
--- /dev/null
+++ b/src/aceneurotools/calcium_imaging/motion_correction_record.py
@@ -0,0 +1,74 @@
+"""Persist motion-correction shifts so they can be inspected after a run.
+
+CaImAn's ``MotionCorrect`` object holds the per-frame shifts and templates only
+in memory. This module copies them to a small ``.npz`` file without importing
+CaImAn, so reports can be drawn later without re-running motion correction.
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
+#: ``MotionCorrect`` attributes copied when present and non-empty.
+_ARRAY_ATTRIBUTES = (
+    "shifts_rig",
+    "x_shifts_els",
+    "y_shifts_els",
+    "total_template_rig",
+    "total_template_els",
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
+    for name in _ARRAY_ATTRIBUTES:
+        value = getattr(mc, name, None)
+        if value is None:
+            continue
+        array = np.asarray(value)
+        if array.size:
+            arrays[name] = array
+    arrays["pw_rigid"] = np.asarray(bool(pw_rigid))
+    border = getattr(mc, "border_to_0", None)
+    if border is not None:
+        arrays["border_to_0"] = np.asarray(border)
+    if frame_rate is not None:
+        arrays["frame_rate"] = np.asarray(float(frame_rate))
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
index 0000000..79349c0
--- /dev/null
+++ b/tests/test_motion_correction_record.py
@@ -0,0 +1,56 @@
+"""Motion-correction shifts are persisted without CaImAn and read back unchanged."""
+
+from types import SimpleNamespace
+
+import numpy as np
+import pytest
+
+from aceneurotools.calcium_imaging.motion_correction_record import (
+    MOTION_CORRECTION_SHIFTS_FILENAME,
+    load_motion_correction_shifts,
+    motion_correction_arrays,
+    save_motion_correction_shifts,
+)
+from aceneurotools.calcium_imaging.pipeline_results import ProcessingResult
+
+
+def fake_mc(pw_rigid):
+    rng = np.random.default_rng(0)
+    return SimpleNamespace(
+        shifts_rig=[tuple(row) for row in rng.normal(size=(50, 2))],
+        x_shifts_els=rng.normal(size=(50, 4)).tolist() if pw_rigid else [],
+        y_shifts_els=rng.normal(size=(50, 4)).tolist() if pw_rigid else [],
+        total_template_rig=rng.random((16, 16)),
+        total_template_els=rng.random((16, 16)) if pw_rigid else None,
+        border_to_0=3,
+    )
+
+
+@pytest.mark.parametrize("pw_rigid", [False, True])
+def test_shifts_round_trip(tmp_path, pw_rigid):
+    mc = fake_mc(pw_rigid)
+    path = save_motion_correction_shifts(mc, tmp_path / "saved_movies", pw_rigid=pw_rigid, frame_rate=20.0)
+
+    assert path == str(tmp_path / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME)
+    saved = load_motion_correction_shifts(path)
+    np.testing.assert_array_equal(saved["shifts_rig"], np.asarray(mc.shifts_rig))
+    np.testing.assert_array_equal(saved["total_template_rig"], mc.total_template_rig)
+    assert bool(saved["pw_rigid"]) is pw_rigid
+    assert float(saved["frame_rate"]) == 20.0
+    assert int(saved["border_to_0"]) == 3
+    if pw_rigid:
+        np.testing.assert_array_equal(saved["x_shifts_els"], np.asarray(mc.x_shifts_els))
+        np.testing.assert_array_equal(saved["y_shifts_els"], np.asarray(mc.y_shifts_els))
+    else:
+        # Empty piecewise lists and missing templates are omitted rather than saved as empty arrays.
+        assert {"x_shifts_els", "y_shifts_els", "total_template_els"}.isdisjoint(saved)
+
+
+def test_missing_attributes_are_skipped():
+    arrays = motion_correction_arrays(SimpleNamespace(), pw_rigid=False)
+    assert set(arrays) == {"pw_rigid"}
+
+
+def test_processing_result_keeps_positional_compatibility():
+    result = ProcessingResult(None, None, None, None, None)
+    assert result.motion_correction_shifts_filepath is None
```
