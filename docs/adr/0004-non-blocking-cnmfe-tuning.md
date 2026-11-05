---
status: proposed
---

# Compute CNMF-E tuning images without opening windows

## Context

With `plot_params=True`, `CalciumImagingProcessor.cnmfe_parameter_handler`
(`src/aceneurotools/calcium_imaging/calcium_imaging_processor.py:215-262`) computes
values inline and shows them in blocking windows:

- the correlation and peak-to-noise-ratio images from
  `cm.summary_images.correlation_pnr`, using a fixed `gsig_tmp = (3, 3)` and every
  `max(T // 1000, 1)`-th frame (lines 241-242);
- the patch width, stride and overlap from CaImAn `rf` and `stride`
  (lines 249-252);
- the quilt display limits, the 50th and 99.5th percentiles of the correlation
  image (line 255-256).

None of these values can be computed without the windows. Headless runs disable
`plot_params`, and the GUI reports these diagnostics as unavailable
(`gui/run_outputs.py:173`). The planned GUI "Tune CNMF-E" step therefore has to
copy this arithmetic, which can drift from the CLI.

Related finding, not changed by this proposal: `cnmfe_parameter_handler` always
calls `cleanup_tkinter()` (line 231), which calls `set_backend(headless=False)`
(line 213). Every run, including headless runs, switches matplotlib to the
interactive backend before CNMF-E.

## Proposed change

Add `calcium_imaging/cnmfe_tuning.py` with pure functions:
`cnmfe_patch_geometry(rf, stride)`, `tuning_frame_step(n_frames)`,
`compute_cnmfe_tuning_images(images, gsig=(3, 3))` and
`quilt_display_limits(correlation_image)`. CaImAn is imported only inside
`compute_cnmfe_tuning_images`. `cnmfe_parameter_handler` calls these functions
and keeps every window, message and pause exactly as before.

## Compatibility

- Numerical results are unchanged. The functions compute the same expressions;
  `images.shape[0]` equals the `T` returned by `cm.load_memmap` because `images` is
  reshaped to `(T,) + dims`. Quilt limits are passed as Python floats instead of
  NumPy floats, with identical values.
- CLI, notebook and `plot_params` behavior are unchanged; CNMF-E inputs are not
  affected.
- New public names only; nothing is removed.

## Alternatives

- Leave the core as is and keep a copy of the arithmetic in the GUI with a test
  that fails when the two drift (the GUI plan's fallback).
- Also return the figures. Rejected: the GUI renders its own images, and CaImAn's
  interactive figure helpers are not needed for the values.

## Unblocks

The GUI "Tune CNMF-E" step can call these functions on a preprocessed sample
instead of copying them, and its drift test can be removed.

## Verification

Diff not test-verified: no test environment was available. The diff applies to
base commit `9e47959` and every changed Python file passed
`python -m py_compile`. Once the locked environment exists (`environment.yml` /
`conda-lock.yml`, then `pip install -e ".[dev]"`), run:

```sh
python -m pytest tests/test_cnmfe_tuning.py -q
python -m pytest tests/test_miniscope_filtering.py tests/test_gui_parity.py -q
python -m pytest -q
```

The last test in `tests/test_cnmfe_tuning.py` compares against a direct CaImAn
call and is skipped when CaImAn is not installed.

## Diff

```diff
diff --git a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
index afb56b1..9ef1139 100644
--- a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
+++ b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
@@ -9,6 +9,11 @@ import numpy as np
 
 import aceneurotools.shared.misc_functions as misc_functions
 from aceneurotools.calcium_imaging.calcium_imaging_data_manager import CalciumImagingDataManager
+from aceneurotools.calcium_imaging.cnmfe_tuning import (
+    cnmfe_patch_geometry,
+    compute_cnmfe_tuning_images,
+    quilt_display_limits,
+)
 from aceneurotools.calcium_imaging.pipeline_results import ProcessingResult
 from aceneurotools.shared.exceptions import ProcessingError
 
@@ -238,23 +243,21 @@ class CalciumImagingProcessor:
 
         if plot_params:
             #calculate min correlation/min pnr and plot them
-            gsig_tmp = (3,3)
-            correlation_image, peak_to_noise_ratio = cm.summary_images.correlation_pnr(images[::max(T//1000, 1)], gSig=gsig_tmp[0], swap_dim=False)
+            correlation_image, peak_to_noise_ratio = compute_cnmfe_tuning_images(images)
             if hasattr(dm, 'diag_logger') and dm.diag_logger is not None: dm.diag_logger.pause_timer()
             cm.utils.visualization.inspect_correlation_pnr(correlation_image, peak_to_noise_ratio)
             plt.show(block=True)
             if hasattr(dm, 'diag_logger') and dm.diag_logger is not None: dm.diag_logger.resume_timer()
 
             #Calculate stride/overlap and plot them
-            cnmfe_patch_width = dm.opts_caiman.get('patch', 'rf') * 2 + 1
-            cnmfe_patch_overlap = dm.opts_caiman.get('patch', 'stride') + 1
-            cnmfe_patch_stride = cnmfe_patch_width - cnmfe_patch_overlap
-            print(f'Patch width: {cnmfe_patch_width} , Stride: {cnmfe_patch_stride}, Overlap: {cnmfe_patch_overlap}')
+            patches = cnmfe_patch_geometry(dm.opts_caiman.get('patch', 'rf'), dm.opts_caiman.get('patch', 'stride'))
+            print(f'Patch width: {patches.width} , Stride: {patches.stride}, Overlap: {patches.overlap}')
 
             if hasattr(dm, 'diag_logger') and dm.diag_logger is not None: dm.diag_logger.pause_timer()
-            patch_ax = cm.utils.visualization.view_quilt(correlation_image, cnmfe_patch_stride, cnmfe_patch_overlap, vmin=np.percentile(np.ravel(correlation_image), 50),
-                                                         vmax=np.percentile(np.ravel(correlation_image), 99.5), color='yellow', figsize=(4,4))
-            patch_ax.set_title(f'CNMFE Patch Width {cnmfe_patch_width}, Overlap {cnmfe_patch_overlap}')
+            vmin, vmax = quilt_display_limits(correlation_image)
+            patch_ax = cm.utils.visualization.view_quilt(correlation_image, patches.stride, patches.overlap, vmin=vmin,
+                                                         vmax=vmax, color='yellow', figsize=(4,4))
+            patch_ax.set_title(f'CNMFE Patch Width {patches.width}, Overlap {patches.overlap}')
             plt.show(block=True)
             if hasattr(dm, 'diag_logger') and dm.diag_logger is not None: dm.diag_logger.resume_timer()
 
diff --git a/src/aceneurotools/calcium_imaging/cnmfe_tuning.py b/src/aceneurotools/calcium_imaging/cnmfe_tuning.py
new file mode 100644
index 0000000..117ec7e
--- /dev/null
+++ b/src/aceneurotools/calcium_imaging/cnmfe_tuning.py
@@ -0,0 +1,68 @@
+"""Non-blocking CNMF-E parameter-tuning computations.
+
+These functions compute the values shown by the interactive ``plot_params``
+step of :meth:`CalciumImagingProcessor.cnmfe_parameter_handler` without
+opening windows, so command-line, notebook and GUI callers share one
+implementation. CaImAn is imported only by the function that needs it.
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass
+
+import numpy as np
+
+#: Spatial kernel used for the tuning correlation/PNR images.
+TUNING_GSIG = (3, 3)
+
+#: At most this many frames are sampled when computing tuning images.
+TUNING_MAX_FRAMES = 1000
+
+
+@dataclass(frozen=True)
+class CNMFEPatchGeometry:
+    """Patch layout derived from CaImAn ``rf`` and ``stride`` parameters (pixels)."""
+
+    width: int
+    stride: int
+    overlap: int
+
+
+def cnmfe_patch_geometry(rf: int, stride: int) -> CNMFEPatchGeometry:
+    """Return the patch width, step and overlap drawn by the tuning quilt plot."""
+    width = rf * 2 + 1
+    overlap = stride + 1
+    return CNMFEPatchGeometry(width=width, stride=width - overlap, overlap=overlap)
+
+
+def tuning_frame_step(n_frames: int, max_frames: int = TUNING_MAX_FRAMES) -> int:
+    """Return the frame step that samples at most about ``max_frames`` frames."""
+    return max(n_frames // max_frames, 1)
+
+
+def compute_cnmfe_tuning_images(
+    images: np.ndarray,
+    gsig: tuple[int, int] = TUNING_GSIG,
+    max_frames: int = TUNING_MAX_FRAMES,
+) -> tuple[np.ndarray, np.ndarray]:
+    """Return the correlation and peak-to-noise-ratio images used for tuning.
+
+    Args:
+        images: Movie with frames on the first axis, shape ``(T, height, width)``.
+        gsig: Gaussian kernel half-size passed to CaImAn as ``gSig``.
+        max_frames: Upper bound on the number of frames sampled.
+
+    Returns:
+        ``(correlation_image, peak_to_noise_ratio)`` from
+        ``caiman.summary_images.correlation_pnr``.
+    """
+    import caiman as cm
+
+    step = tuning_frame_step(images.shape[0], max_frames)
+    return cm.summary_images.correlation_pnr(images[::step], gSig=gsig[0], swap_dim=False)
+
+
+def quilt_display_limits(correlation_image: np.ndarray) -> tuple[float, float]:
+    """Return the ``(vmin, vmax)`` percentiles used to display the patch quilt."""
+    values = np.ravel(correlation_image)
+    return float(np.percentile(values, 50)), float(np.percentile(values, 99.5))
diff --git a/tests/test_cnmfe_tuning.py b/tests/test_cnmfe_tuning.py
new file mode 100644
index 0000000..463cf49
--- /dev/null
+++ b/tests/test_cnmfe_tuning.py
@@ -0,0 +1,42 @@
+"""Non-blocking CNMF-E tuning helpers match the interactive plot_params step."""
+
+import numpy as np
+import pytest
+
+from aceneurotools.calcium_imaging.cnmfe_tuning import (
+    CNMFEPatchGeometry,
+    cnmfe_patch_geometry,
+    quilt_display_limits,
+    tuning_frame_step,
+)
+
+
+@pytest.mark.parametrize(
+    ("rf", "stride", "expected"),
+    [(40, 20, CNMFEPatchGeometry(81, 60, 21)), (12, 6, CNMFEPatchGeometry(25, 18, 7)), (0, 0, CNMFEPatchGeometry(1, 0, 1))],
+)
+def test_patch_geometry_matches_previous_inline_arithmetic(rf, stride, expected):
+    width = rf * 2 + 1
+    overlap = stride + 1
+    assert cnmfe_patch_geometry(rf, stride) == expected == CNMFEPatchGeometry(width, width - overlap, overlap)
+
+
+@pytest.mark.parametrize(("frames", "step"), [(1, 1), (999, 1), (1000, 1), (1999, 1), (2000, 2), (30000, 30)])
+def test_frame_step_matches_previous_subsampling(frames, step):
+    assert tuning_frame_step(frames) == max(frames // 1000, 1) == step
+
+
+def test_quilt_limits_match_previous_percentiles():
+    image = np.random.default_rng(0).random((32, 48))
+    assert quilt_display_limits(image) == (np.percentile(np.ravel(image), 50), np.percentile(np.ravel(image), 99.5))
+
+
+def test_tuning_images_match_direct_caiman_call():
+    cm = pytest.importorskip("caiman")
+    from aceneurotools.calcium_imaging.cnmfe_tuning import compute_cnmfe_tuning_images
+
+    images = np.random.default_rng(1).random((2500, 24, 24)).astype(np.float32)
+    expected = cm.summary_images.correlation_pnr(images[::2], gSig=3, swap_dim=False)
+    actual = compute_cnmfe_tuning_images(images)
+    for left, right in zip(actual, expected):
+        np.testing.assert_array_equal(left, right)
```
