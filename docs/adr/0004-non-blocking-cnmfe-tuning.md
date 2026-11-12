---
status: accepted
---

# Compute CNMF-E tuning images without opening windows

## Context

With `plot_params=True`, `CalciumImagingProcessor.cnmfe_parameter_handler`
(`src/aceneurotools/calcium_imaging/calcium_imaging_processor.py:240-287` at
`accb6e0`) computes
values inline and shows them in blocking windows:

- the correlation and peak-to-noise-ratio images from
  `cm.summary_images.correlation_pnr`, using a fixed `gsig_tmp = (3, 3)` and every
  `max(T // 1000, 1)`-th frame (lines 266-267);
- the patch width, stride and overlap from CaImAn `rf` and `stride`
  (lines 274-277);
- the quilt display limits, the 50th and 99.5th percentiles of the correlation
  image (lines 280-281).

None of these values can be computed without the windows. Headless runs disable
`plot_params`, and the GUI reports these diagnostics as unavailable
(`gui/run_outputs.py:174`). The planned GUI "Tune CNMF-E" step therefore has to
copy this arithmetic, which can drift from the CLI.

Related finding, not changed by this proposal: `cnmfe_parameter_handler` always
calls `cleanup_tkinter()` (line 256), which calls `set_backend(headless=False)`
(line 238). Every run, including headless runs, switches matplotlib to the
interactive backend before CNMF-E.

## Proposed change

Add `calcium_imaging/cnmfe_tuning.py`, which computes the tuning values without
opening windows:

- `TUNING_GSIG = 3` and `TUNING_MAX_FRAMES = 1000`, the values the inline code used.
- `CNMFEPatchGeometry(width, stride, overlap)` and
  `cnmfe_patch_geometry(rf, stride)`: width `2 * rf + 1`, overlap `stride + 1`,
  step `width - overlap`.
- `tuning_frame_step(n_frames, max_frames=TUNING_MAX_FRAMES)`:
  `max(n_frames // max_frames, 1)`.
- `compute_cnmfe_tuning_images(images, gsig=TUNING_GSIG, max_frames=TUNING_MAX_FRAMES)`:
  CaImAn's `correlation_pnr` on every step-th frame. `gsig` is one whole number
  or a `(rows, columns)` pair such as the CNMF-E `gSig` setting; a pair is passed
  to CaImAn as a list, the only sequence type CaImAn recognizes.
- `quilt_display_limits(correlation_image)`: the 50th and 99.5th percentiles.

The functions that take settings check them and raise `ValueError` for values the old
arithmetic could not use: `rf` must be a positive whole number, `stride` a
non-negative whole number smaller than `2 * rf` (otherwise patches cannot
advance), frame counts non-negative and `max_frames` positive whole numbers.
Importing the module does not import CaImAn; only
`compute_cnmfe_tuning_images` does. The functions run synchronously.

`cnmfe_parameter_handler` calls these functions and keeps every window, message,
pause and timer call in the same order. Its docstring now tells users to call
`compute_cnmfe_tuning_images(images, gsig=...)` to try other kernel sizes,
because the inline `gsig_tmp` variable it used to mention no longer exists.

## Compatibility

- Numerical results are unchanged. The functions compute the same expressions;
  `images.shape[0]` equals the `T` returned by `cm.load_memmap` because `images` is
  reshaped to `(T,) + dims`. Quilt limits are passed as Python floats instead of
  NumPy floats, with identical values.
- Runs without `plot_params`, and runs with valid patch settings, behave as
  before. With `plot_params` on and an unusable `rf`/`stride` (missing, a list,
  or `stride >= 2 * rf`), the run now stops with a `ValueError` after the first
  window. Before, it failed with a `TypeError` (missing or list values), with a
  `ValueError` from `range()` inside CaImAn's `view_quilt` (`stride == 2 * rf`),
  or drew a single meaningless patch (`stride > 2 * rf`). CaImAn itself cannot
  build patches when `stride == 2 * rf`.
- New public names only; nothing is removed.

## Alternatives

- Leave the core as is. A GUI tuning step would then have to copy this
  arithmetic and add a test that fails when the copy drifts (AGENTS.md rule 2).
- Also return the figures. Rejected: the GUI renders its own images, and CaImAn's
  interactive figure helpers are not needed for the values.

## Unblocks

A GUI "Tune CNMF-E" step can call these functions on a preprocessed sample
instead of copying the arithmetic.

## Risks

- A caller that tunes on a short sample movie samples frames differently from a
  full run, because the frame step depends on the movie length.
- The tuning images always use `TUNING_GSIG` in the interactive step; trying the
  user's `gSig` means calling `compute_cnmfe_tuning_images` directly.
- The new input checks reject `rf`/`stride` forms that CaImAn's CNMF-E itself
  accepts (per-axis lists, `rf=None` for no patches). The interactive step could
  never draw those, so only callers of the new functions see the difference.

## Tests

`tests/test_cnmfe_tuning.py`:

- the defaults, and that importing the module does not import CaImAn;
- patch geometry, frame step and quilt limits against the previous inline
  arithmetic, including NumPy integers, and every rejected input;
- `compute_cnmfe_tuning_images` forwards the frame target and kernel size
  (single numbers and pairs, passed as a list) and matches a direct CaImAn call;
- the processor's `plot_params` branch: the exact order of computation, timer
  pauses, both blocking windows, the quilt arguments, title and printed line;
  that it stops on invalid patch settings after the first window; and that
  nothing is drawn without `plot_params`.

## Verification

The patch below is the full change against base `accb6e0` (main after PR #152),
excluding this ADR.
It was accepted when PR #153 was merged after adversarial review. The review ran
the full default suite (`pytest tests -m "not slow"`), changed-line coverage,
documentation coverage, the documentation link check and the strict MkDocs
build; the results are in the PR. Representative recording validation is
handled separately by the lab, as `AGENTS.md` describes.

## Diff

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 4066850..0b97636 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -35,6 +35,10 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
   report the file in `ProcessingResult.motion_correction_shifts_filepath` and in
   the GUI's output inventory and run review. Analysis results are unchanged. If
   the file cannot be written, the run prints a warning and continues.
+- `aceneurotools.calcium_imaging.cnmfe_tuning` computes the CNMF-E tuning images,
+  patch layout and display limits shown by `plot_params` without opening windows,
+  for example in a notebook. Analysis results are unchanged. With `plot_params`
+  on, unusable `rf`/`stride` settings now stop the run with a clear error.
 - Installed `ace-gui` workbench with per-launch API authentication and shared
   CLI/GUI defaults. CSVs remain the settings source of truth.
 - GUI feature registry and run plans: new workbench screens register their own
diff --git a/docs/api/calcium_imaging.md b/docs/api/calcium_imaging.md
index a9d6960..f6496e4 100644
--- a/docs/api/calcium_imaging.md
+++ b/docs/api/calcium_imaging.md
@@ -12,6 +12,12 @@ This section details the pipeline for processing calcium imaging data.
 ## Processor (CNMF-E)
 ::: aceneurotools.calcium_imaging.calcium_imaging_processor.CalciumImagingProcessor
 
+## CNMF-E tuning values
+These functions compute the correlation/peak-to-noise images, patch layout and
+display limits that `plot_params=True` shows, without opening windows.
+
+::: aceneurotools.calcium_imaging.cnmfe_tuning
+
 ## Processing result
 ::: aceneurotools.calcium_imaging.pipeline_results.ProcessingResult
 
diff --git a/docs/guides/calcium_imaging.md b/docs/guides/calcium_imaging.md
index 0a9a455..306e7e7 100644
--- a/docs/guides/calcium_imaging.md
+++ b/docs/guides/calcium_imaging.md
@@ -68,6 +68,38 @@ invalid/missing crop until it is saved or disabled.
 Use the [API](../api/calcium_imaging.md) for full details. GUI separate-window
 plots and component-selection dialogs are disabled; use embedded Crop/Neurons.
 
+### Tuning CNMF-E settings
+
+With `plot_params` on (desktop runs only; headless and GUI runs turn it off),
+the run shows two windows before CNMF-E and continues when you close each one:
+
+1. The correlation and peak-to-noise-ratio images, computed with a fixed
+   Gaussian kernel half-size of 3 pixels on every frame of movies shorter than
+   2000 frames, and on every `frames // 1000`-th frame of longer ones. Use the
+   sliders to find where neurons are clearest, then set `min_corr` and `min_pnr`
+   slightly below those values.
+2. The patch layout from `rf` and `stride`: patches are `2 * rf + 1` pixels
+   wide and overlap by `stride + 1` pixels. Choose values so that each patch
+   holds at least 3-4 neuron diameters and at least one neuron fits in the
+   overlap. `stride` must be smaller than `2 * rf`.
+
+To compute the same values without windows, for example in a notebook or to try
+other kernel sizes, use `aceneurotools.calcium_imaging.cnmfe_tuning`:
+
+```python
+from aceneurotools.calcium_imaging.cnmfe_tuning import (
+    cnmfe_patch_geometry,
+    compute_cnmfe_tuning_images,
+    quilt_display_limits,
+)
+
+# images: the motion-corrected movie, frames first: (frames, height, width).
+# CalciumImagingProcessor.cnmfe_parameter_handler returns it as its second value.
+correlation, peak_to_noise = compute_cnmfe_tuning_images(images, gsig=[5, 5])
+patches = cnmfe_patch_geometry(rf=40, stride=20)  # width 81, overlap 21, step 60
+vmin, vmax = quilt_display_limits(correlation)
+```
+
 ## Outputs and interpretation
 
 Successful saved extraction normally creates `saved_movies/estimates.hdf5` within
diff --git a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
index 581d6c8..15f1c35 100644
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
 from aceneurotools.calcium_imaging.motion_correction_record import save_motion_correction_shifts
 from aceneurotools.calcium_imaging.pipeline_results import ProcessingResult
 from aceneurotools.shared.exceptions import ProcessingError
@@ -241,8 +246,9 @@ class CalciumImagingProcessor:
         """
         -This is an important step before CNMFE. It handles the most important CNMFE parameters.
 
-        -It uses the 'gsig_tmp' below to make the first plot. Adjust this value until the plot shown does not merge any neurons,
-        then update 'gsig' in analysis_parameters.csv with the best 'gsig_tmp' value
+        -The first plot always uses a Gaussian kernel half-size of 3 pixels (``cnmfe_tuning.TUNING_GSIG``). To try other
+        values, call ``cnmfe_tuning.compute_cnmfe_tuning_images(images, gsig=...)`` yourself (for example in a notebook) and
+        adjust it until the plot shown does not merge any neurons, then update 'gSig' in analysis_parameters.csv
 
         -First, this function calculates correlation and peak to noise ratios and plots them. Use the sliders to adjust 'vmax' until neurons are most visible,
         then adjust 'min_corr' and 'min_pnr' in analysis_parameters.csv to values slightly below those vmax values
@@ -263,23 +269,21 @@ class CalciumImagingProcessor:
 
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
index 0000000..00aedcd
--- /dev/null
+++ b/src/aceneurotools/calcium_imaging/cnmfe_tuning.py
@@ -0,0 +1,127 @@
+"""Window-free CNMF-E parameter-tuning computations.
+
+These functions compute the values shown by the interactive ``plot_params``
+step of :meth:`CalciumImagingProcessor.cnmfe_parameter_handler` without
+opening windows, so command-line, notebook and GUI callers share one
+implementation. They run synchronously: computing the tuning images on a long
+movie can take a while, and ``plot_params=True`` itself still waits for each
+window to be closed. Importing this module does not import CaImAn; only
+:func:`compute_cnmfe_tuning_images` does.
+"""
+
+from __future__ import annotations
+
+from collections.abc import Sequence
+from dataclasses import dataclass
+
+import numpy as np
+
+#: Gaussian kernel half-size (``gSig``, pixels) used for the tuning correlation/PNR images.
+#: The legacy code wrote ``gsig_tmp = (3, 3)`` but passed only its first element.
+TUNING_GSIG = 3
+
+#: Subsampling target for tuning images: the frame step is ``n_frames // TUNING_MAX_FRAMES``
+#: (at least 1), so between ``TUNING_MAX_FRAMES`` and ``2 * TUNING_MAX_FRAMES - 1`` frames
+#: are used for movies longer than the target, and every frame for shorter movies.
+TUNING_MAX_FRAMES = 1000
+
+
+def _is_whole_number(value) -> bool:
+    return not isinstance(value, bool) and isinstance(value, (int, np.integer))
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
+    """Return the patch width, step and overlap drawn by the tuning quilt plot.
+
+    ``rf`` is CaImAn's patch half-size and ``stride`` its patch overlap, both single
+    whole numbers of pixels. The width is ``2 * rf + 1``, the overlap ``stride + 1``
+    and the step between patches ``width - overlap``.
+
+    Raises:
+        ValueError: If ``rf`` is not a positive whole number, ``stride`` is not a
+            non-negative whole number, or ``stride >= 2 * rf`` (the overlap would be
+            at least the patch width, so patches could not advance).
+    """
+    if not _is_whole_number(rf) or rf < 1:
+        raise ValueError("rf must be a positive whole number of pixels.")
+    if not _is_whole_number(stride) or stride < 0:
+        raise ValueError("stride must be a non-negative whole number of pixels.")
+    if stride >= 2 * rf:
+        raise ValueError("stride must be smaller than 2 * rf so that patches advance.")
+    width = int(rf) * 2 + 1
+    overlap = int(stride) + 1
+    return CNMFEPatchGeometry(width=width, stride=width - overlap, overlap=overlap)
+
+
+def tuning_frame_step(n_frames: int, max_frames: int = TUNING_MAX_FRAMES) -> int:
+    """Return the legacy frame step ``max(n_frames // max_frames, 1)``.
+
+    ``max_frames`` is a target, not a bound: 1999 frames with a target of 1000 gives
+    a step of 1, so all 1999 frames are used. This matches the previous inline code.
+
+    Raises:
+        ValueError: If ``n_frames`` is not a non-negative whole number or
+            ``max_frames`` is not a positive whole number.
+    """
+    if not _is_whole_number(n_frames) or n_frames < 0:
+        raise ValueError("n_frames must be a non-negative whole number.")
+    if not _is_whole_number(max_frames) or max_frames < 1:
+        raise ValueError("max_frames must be a positive whole number.")
+    return max(int(n_frames) // int(max_frames), 1)
+
+
+def _caiman_gsig(gsig: int | Sequence[int]) -> int | list[int]:
+    if _is_whole_number(gsig) and gsig >= 1:
+        return int(gsig)
+    if (
+        isinstance(gsig, (list, tuple, np.ndarray))
+        and np.ndim(gsig) == 1
+        and len(gsig) == 2
+        and all(_is_whole_number(value) and value >= 1 for value in gsig)
+    ):
+        return [int(value) for value in gsig]
+    raise ValueError("gsig must be a positive whole number of pixels or a pair of them, such as 3 or [3, 3].")
+
+
+def compute_cnmfe_tuning_images(
+    images: np.ndarray,
+    gsig: int | Sequence[int] = TUNING_GSIG,
+    max_frames: int = TUNING_MAX_FRAMES,
+) -> tuple[np.ndarray, np.ndarray]:
+    """Return the correlation and peak-to-noise-ratio images used for tuning.
+
+    Args:
+        images: Movie with frames on the first axis, shape ``(T, height, width)``.
+        gsig: Gaussian kernel half-size in pixels, passed to CaImAn as ``gSig``.
+            Either one whole number (the ``plot_params`` step uses
+            :data:`TUNING_GSIG`) or a ``(rows, columns)`` pair such as the CNMF-E
+            ``gSig`` setting.
+        max_frames: Subsampling target; see :func:`tuning_frame_step`.
+
+    Returns:
+        ``(correlation_image, peak_to_noise_ratio)`` from
+        ``caiman.summary_images.correlation_pnr``.
+
+    Raises:
+        ValueError: If ``gsig`` or ``max_frames`` is not valid.
+    """
+    caiman_gsig = _caiman_gsig(gsig)
+    step = tuning_frame_step(images.shape[0], max_frames)
+    import caiman as cm
+
+    return cm.summary_images.correlation_pnr(images[::step], gSig=caiman_gsig, swap_dim=False)
+
+
+def quilt_display_limits(correlation_image: np.ndarray) -> tuple[float, float]:
+    """Return the ``(vmin, vmax)`` percentiles used to display the patch quilt."""
+    values = np.ravel(correlation_image)
+    return float(np.percentile(values, 50)), float(np.percentile(values, 99.5))
diff --git a/tests/test_cnmfe_tuning.py b/tests/test_cnmfe_tuning.py
new file mode 100644
index 0000000..bc1163b
--- /dev/null
+++ b/tests/test_cnmfe_tuning.py
@@ -0,0 +1,309 @@
+"""Window-free CNMF-E tuning helpers match the interactive plot_params step."""
+
+from types import SimpleNamespace
+
+import numpy as np
+import pytest
+
+from aceneurotools.calcium_imaging.cnmfe_tuning import (
+    TUNING_GSIG,
+    TUNING_MAX_FRAMES,
+    CNMFEPatchGeometry,
+    cnmfe_patch_geometry,
+    compute_cnmfe_tuning_images,
+    quilt_display_limits,
+    tuning_frame_step,
+)
+
+
+def test_defaults_match_the_previous_inline_values():
+    assert (TUNING_GSIG, TUNING_MAX_FRAMES) == (3, 1000)
+
+
+def test_importing_the_module_does_not_import_caiman():
+    import os
+    import subprocess
+    import sys
+    from pathlib import Path
+
+    import aceneurotools
+
+    # Import the same source tree the tests use (a worktree's src, not an editable install elsewhere).
+    source_root = str(Path(aceneurotools.__file__).resolve().parents[1])
+    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([source_root, os.environ.get("PYTHONPATH", "")])}
+    code = "import sys, aceneurotools.calcium_imaging.cnmfe_tuning; print('caiman' in sys.modules)"
+    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=environment)
+    assert result.stdout.strip() == "False"
+
+
+# --- patch geometry -------------------------------------------------------------
+
+
+@pytest.mark.parametrize(
+    ("rf", "stride", "expected"),
+    [
+        (40, 20, CNMFEPatchGeometry(81, 60, 21)),
+        (12, 6, CNMFEPatchGeometry(25, 18, 7)),
+        (1, 0, CNMFEPatchGeometry(3, 2, 1)),
+        (5, 9, CNMFEPatchGeometry(11, 1, 10)),  # largest valid stride: step of one pixel
+        (np.int64(12), np.int32(6), CNMFEPatchGeometry(25, 18, 7)),
+    ],
+)
+def test_patch_geometry_matches_previous_inline_arithmetic(rf, stride, expected):
+    width = int(rf) * 2 + 1
+    overlap = int(stride) + 1
+    geometry = cnmfe_patch_geometry(rf, stride)
+    assert geometry == expected == CNMFEPatchGeometry(width, width - overlap, overlap)
+    assert all(type(value) is int for value in (geometry.width, geometry.stride, geometry.overlap))
+
+
+@pytest.mark.parametrize(
+    ("rf", "stride", "message"),
+    [
+        (0, 0, "rf"),
+        (-3, 1, "rf"),
+        (None, 6, "rf"),
+        ([12, 12], 6, "rf"),
+        (12.0, 6, "rf"),
+        (True, 0, "rf"),
+        (12, -1, "stride"),
+        (12, None, "stride"),
+        (12, [6, 6], "stride"),
+        (12, 6.0, "stride"),
+        (5, 10, "2 \\* rf"),  # overlap equals the width: patches would not advance
+        (3, 10, "2 \\* rf"),  # previously returned a negative step
+    ],
+)
+def test_patch_geometry_rejects_invalid_settings(rf, stride, message):
+    with pytest.raises(ValueError, match=message):
+        cnmfe_patch_geometry(rf, stride)
+
+
+# --- frame subsampling ----------------------------------------------------------
+
+
+@pytest.mark.parametrize(("frames", "step"), [(0, 1), (1, 1), (999, 1), (1000, 1), (1999, 1), (2000, 2), (30000, 30)])
+def test_frame_step_matches_previous_subsampling(frames, step):
+    assert tuning_frame_step(frames) == max(frames // 1000, 1) == step
+
+
+def test_frame_step_uses_the_given_target_and_numpy_integers():
+    assert tuning_frame_step(np.int64(2500), np.int32(500)) == 5
+    assert type(tuning_frame_step(np.int64(2500), np.int32(500))) is int
+
+
+@pytest.mark.parametrize("max_frames", [0, -1, 1.5, True, None])
+def test_frame_step_rejects_invalid_targets(max_frames):
+    with pytest.raises(ValueError, match="max_frames"):
+        tuning_frame_step(100, max_frames)
+
+
+@pytest.mark.parametrize("n_frames", [-1, 2500.0, True, None])
+def test_frame_step_rejects_invalid_frame_counts(n_frames):
+    with pytest.raises(ValueError, match="n_frames"):
+        tuning_frame_step(n_frames)
+
+
+# --- quilt limits ---------------------------------------------------------------
+
+
+def test_quilt_limits_match_previous_percentiles():
+    image = np.random.default_rng(0).random((32, 48))
+    limits = quilt_display_limits(image)
+    assert limits == (np.percentile(np.ravel(image), 50), np.percentile(np.ravel(image), 99.5))
+    assert all(type(value) is float for value in limits)
+
+
+# --- tuning images --------------------------------------------------------------
+
+
+@pytest.fixture
+def recorded_correlation_pnr(monkeypatch):
+    caiman = pytest.importorskip("caiman")
+    calls = []
+    correlation, pnr = np.ones((8, 8)), np.full((8, 8), 2.0)
+
+    def correlation_pnr(images, gSig, swap_dim):
+        calls.append({"images": images, "gSig": gSig, "swap_dim": swap_dim})
+        return correlation, pnr
+
+    monkeypatch.setattr(caiman.summary_images, "correlation_pnr", correlation_pnr)
+    return calls, correlation, pnr
+
+
+def test_tuning_images_forward_the_kernel_size_and_frame_target(recorded_correlation_pnr):
+    calls, correlation, pnr = recorded_correlation_pnr
+    images = np.arange(2500 * 2 * 2, dtype=np.float32).reshape(2500, 2, 2)
+
+    result = compute_cnmfe_tuning_images(images, gsig=np.int64(4), max_frames=500)
+
+    assert result[0] is correlation and result[1] is pnr
+    (call,) = calls
+    np.testing.assert_array_equal(call["images"], images[::5])
+    assert call["gSig"] == 4 and type(call["gSig"]) is int
+    assert call["swap_dim"] is False
+
+
+@pytest.mark.parametrize("gsig", [[5, 5], (5, 7), np.array([5, 7])])
+def test_tuning_images_pass_a_kernel_pair_to_caiman_as_a_list(recorded_correlation_pnr, gsig):
+    calls, _, _ = recorded_correlation_pnr
+    compute_cnmfe_tuning_images(np.zeros((10, 8, 8), dtype=np.float32), gsig=gsig)
+    assert calls[0]["gSig"] == [int(value) for value in gsig]
+    assert type(calls[0]["gSig"]) is list and all(type(value) is int for value in calls[0]["gSig"])
+
+
+def test_tuning_images_match_direct_caiman_call():
+    cm = pytest.importorskip("caiman")
+    images = np.random.default_rng(1).random((2000, 10, 10)).astype(np.float32)
+    expected = cm.summary_images.correlation_pnr(images[::2], gSig=3, swap_dim=False)
+
+    for actual in (compute_cnmfe_tuning_images(images), compute_cnmfe_tuning_images(images, gsig=[3, 3])):
+        for left, right in zip(actual, expected):
+            np.testing.assert_array_equal(left, right)
+
+
+@pytest.mark.parametrize(
+    "gsig", [0, -3, 2.5, True, None, "3", (3,), [3, 3, 3], [0, 3], [3, 2.5], [True, 3], np.array(3), np.ones((2, 2), int)]
+)
+def test_tuning_images_reject_invalid_kernel_sizes(gsig):
+    with pytest.raises(ValueError, match="gsig"):
+        compute_cnmfe_tuning_images(np.zeros((4, 8, 8), dtype=np.float32), gsig=gsig)
+
+
+def test_tuning_images_reject_invalid_frame_targets():
+    with pytest.raises(ValueError, match="max_frames"):
+        compute_cnmfe_tuning_images(np.zeros((4, 8, 8), dtype=np.float32), max_frames=0)
+
+
+# --- the processor's plot_params branch draws what the old inline code drew ------
+
+
+class FakeOpts:
+    def __init__(self, rf=12, stride=6):
+        self.values = {("data", "fnames"): ["movie.mmap"], ("patch", "rf"): rf, ("patch", "stride"): stride}
+        self.changes = []
+
+    def get(self, group, key):
+        return self.values[(group, key)]
+
+    def change_params(self, params):
+        self.changes.append(params)
+
+
+class FakeTimer:
+    def __init__(self, events):
+        self.events = events
+
+    def pause_timer(self):
+        self.events.append("pause")
+
+    def resume_timer(self):
+        self.events.append("resume")
+
+
+@pytest.fixture
+def tuning_run(monkeypatch):
+    caiman = pytest.importorskip("caiman")
+
+    from aceneurotools.calcium_imaging import calcium_imaging_processor as module
+    from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor
+
+    events = []
+    details = {}
+    frames, dims = 2500, (8, 10)
+    Yr = np.random.default_rng(2).random((dims[0] * dims[1], frames)).astype(np.float32)
+    correlation = np.linspace(0, 1, 80).reshape(dims)
+    pnr = np.full(dims, 7.0)
+
+    def correlation_pnr(images, gSig, swap_dim):
+        events.append("correlation_pnr")
+        details["correlation_pnr"] = (images.shape, gSig, swap_dim)
+        return correlation, pnr
+
+    class Axis:
+        def set_title(self, title):
+            events.append("set_title")
+            details["title"] = title
+
+    def view_quilt(*args, **kwargs):
+        events.append("view_quilt")
+        details["view_quilt"] = (args, kwargs)
+        return Axis()
+
+    def inspect(c, p):
+        events.append("inspect_correlation_pnr")
+        details["inspect"] = (c, p)
+
+    def show(*args, **kwargs):
+        events.append(f"show(block={kwargs.get('block')!r})")
+
+    processor = object.__new__(CalciumImagingProcessor)
+    monkeypatch.setattr(processor, "cleanup_tkinter", lambda: events.append("cleanup_tkinter"))
+    monkeypatch.setattr(module.cm, "load_memmap", lambda path: (Yr, dims, frames))
+    # compute_cnmfe_tuning_images imports caiman itself, so patch the shared module object.
+    monkeypatch.setattr(caiman.summary_images, "correlation_pnr", correlation_pnr)
+    monkeypatch.setattr(module.cm.utils.visualization, "inspect_correlation_pnr", inspect)
+    monkeypatch.setattr(module.cm.utils.visualization, "view_quilt", view_quilt)
+    monkeypatch.setattr(module.plt, "show", show)
+    return SimpleNamespace(
+        processor=processor, events=events, details=details, Yr=Yr, dims=dims, correlation=correlation, pnr=pnr
+    )
+
+
+def test_plot_params_draws_the_tuning_images_and_patch_quilt_in_order(tuning_run, capsys):
+    run = tuning_run
+    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=FakeTimer(run.events))
+
+    returned, images = run.processor.cnmfe_parameter_handler(manager, plot_params=True)
+
+    assert returned is manager and manager.opts_caiman.changes == [{"data": {"dims": run.dims}}]
+    np.testing.assert_array_equal(images, run.Yr.T.reshape((2500,) + run.dims, order="F"))
+    assert run.events == [
+        "cleanup_tkinter",
+        "correlation_pnr",
+        "pause",
+        "inspect_correlation_pnr",
+        "show(block=True)",
+        "resume",
+        "pause",
+        "view_quilt",
+        "set_title",
+        "show(block=True)",
+        "resume",
+    ]
+    assert run.details["correlation_pnr"] == ((1250,) + run.dims, 3, False), "2500 frames, every 2nd, gSig=3"
+    assert run.details["inspect"][0] is run.correlation and run.details["inspect"][1] is run.pnr
+    args, kwargs = run.details["view_quilt"]
+    # rf=12, stride=6 -> width 25, overlap 7, step 18 (the previous inline arithmetic).
+    assert args == (run.correlation, 18, 7)
+    assert kwargs == {
+        "vmin": np.percentile(run.correlation, 50),
+        "vmax": np.percentile(run.correlation, 99.5),
+        "color": "yellow",
+        "figsize": (4, 4),
+    }
+    assert run.details["title"] == "CNMFE Patch Width 25, Overlap 7"
+    assert capsys.readouterr().out == "Patch width: 25 , Stride: 18, Overlap: 7\n"
+
+
+def test_plot_params_without_a_timer_still_shows_both_windows(tuning_run):
+    run = tuning_run
+    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=None)
+    run.processor.cnmfe_parameter_handler(manager, plot_params=True)
+    assert "pause" not in run.events and run.events.count("show(block=True)") == 2
+
+
+def test_plot_params_stops_on_invalid_patch_settings_after_the_first_window(tuning_run):
+    run = tuning_run
+    manager = SimpleNamespace(opts_caiman=FakeOpts(rf=3, stride=10), diag_logger=FakeTimer(run.events))
+    with pytest.raises(ValueError, match="2 \\* rf"):
+        run.processor.cnmfe_parameter_handler(manager, plot_params=True)
+    assert run.events[-1] == "resume" and "view_quilt" not in run.events
+
+
+def test_without_plot_params_nothing_is_drawn(tuning_run):
+    run = tuning_run
+    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=FakeTimer(run.events))
+    _, images = run.processor.cnmfe_parameter_handler(manager, plot_params=False)
+    assert images.shape == (2500,) + run.dims
+    assert run.events == ["cleanup_tkinter"]
```
