---
status: accepted
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

Every function checks its inputs and raises `ValueError` for values the old
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
  window. Before, it failed with a `TypeError` or drew a meaningless quilt, and
  CaImAn itself cannot build patches when `stride == 2 * rf`.
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

The patch below is the full change against base `ded08fd`, excluding this ADR.
It was accepted when PR #153 was merged after adversarial review. The review ran
the full default suite (`pytest tests -m "not slow"`), changed-line coverage,
documentation coverage, the documentation link check and the strict MkDocs
build; the results are in the PR. Representative recording validation is
handled separately by the lab, as `AGENTS.md` describes.

## Diff

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 55eebaf..1fbc328 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -30,6 +30,8 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 ### Added
 
+- `aceneurotools.calcium_imaging.cnmfe_tuning` computes the CNMF-E tuning images,
+  patch layout and display limits shown by `plot_params` without opening windows.
 - Installed `ace-gui` workbench with per-launch API authentication and shared
   CLI/GUI defaults. CSVs remain the settings source of truth.
 - GUI feature registry and run plans: new workbench screens register their own
diff --git a/docs/api/calcium_imaging.md b/docs/api/calcium_imaging.md
index a3e80e2..1b65ff1 100644
--- a/docs/api/calcium_imaging.md
+++ b/docs/api/calcium_imaging.md
@@ -12,5 +12,11 @@ This section details the pipeline for processing calcium imaging data.
 ## Processor (CNMF-E)
 ::: aceneurotools.calcium_imaging.calcium_imaging_processor.CalciumImagingProcessor
 
+## CNMF-E tuning values
+These functions compute the correlation/peak-to-noise images, patch layout and
+display limits that `plot_params=True` shows, without opening windows.
+
+::: aceneurotools.calcium_imaging.cnmfe_tuning
+
 ## Postprocessor
 ::: aceneurotools.calcium_imaging.calcium_imaging_postprocessor.CalciumImagingPostprocessor
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
index 0000000..9027621
--- /dev/null
+++ b/src/aceneurotools/calcium_imaging/cnmfe_tuning.py
@@ -0,0 +1,79 @@
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
+    """Return the legacy frame step ``max(n_frames // max_frames, 1)``.
+
+    ``max_frames`` is a target, not a bound: 1999 frames with a target of 1000 gives
+    a step of 1, so all 1999 frames are used. This matches the previous inline code.
+    """
+    if isinstance(max_frames, bool) or not isinstance(max_frames, (int, np.integer)) or max_frames < 1:
+        raise ValueError("max_frames must be a positive whole number.")
+    return max(n_frames // max_frames, 1)
+
+
+def compute_cnmfe_tuning_images(
+    images: np.ndarray,
+    gsig: int = TUNING_GSIG,
+    max_frames: int = TUNING_MAX_FRAMES,
+) -> tuple[np.ndarray, np.ndarray]:
+    """Return the correlation and peak-to-noise-ratio images used for tuning.
+
+    Args:
+        images: Movie with frames on the first axis, shape ``(T, height, width)``.
+        gsig: Gaussian kernel half-size in pixels, passed to CaImAn as ``gSig``.
+        max_frames: Subsampling target; see :func:`tuning_frame_step`.
+
+    Returns:
+        ``(correlation_image, peak_to_noise_ratio)`` from
+        ``caiman.summary_images.correlation_pnr``.
+    """
+    if isinstance(gsig, bool) or not isinstance(gsig, (int, np.integer)) or gsig < 1:
+        raise ValueError("gsig must be a positive whole number of pixels.")
+    import caiman as cm
+
+    step = tuning_frame_step(images.shape[0], max_frames)
+    return cm.summary_images.correlation_pnr(images[::step], gSig=int(gsig), swap_dim=False)
+
+
+def quilt_display_limits(correlation_image: np.ndarray) -> tuple[float, float]:
+    """Return the ``(vmin, vmax)`` percentiles used to display the patch quilt."""
+    values = np.ravel(correlation_image)
+    return float(np.percentile(values, 50)), float(np.percentile(values, 99.5))
diff --git a/tests/test_cnmfe_tuning.py b/tests/test_cnmfe_tuning.py
new file mode 100644
index 0000000..14bce33
--- /dev/null
+++ b/tests/test_cnmfe_tuning.py
@@ -0,0 +1,138 @@
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
+
+
+@pytest.mark.parametrize("gsig", [0, -3, 2.5, True, (3, 3)])
+def test_tuning_images_reject_invalid_kernel_sizes(gsig):
+    from aceneurotools.calcium_imaging.cnmfe_tuning import compute_cnmfe_tuning_images
+
+    with pytest.raises(ValueError, match="gsig"):
+        compute_cnmfe_tuning_images(np.zeros((4, 8, 8), dtype=np.float32), gsig=gsig)
+
+
+@pytest.mark.parametrize("max_frames", [0, -1, 1.5, True])
+def test_frame_step_rejects_invalid_targets(max_frames):
+    with pytest.raises(ValueError, match="max_frames"):
+        tuning_frame_step(100, max_frames)
+
+
+# The processor's plot_params branch draws exactly what the old inline code drew.
+
+from types import SimpleNamespace  # noqa: E402
+
+
+class FakeOpts:
+    def __init__(self):
+        self.values = {("data", "fnames"): ["movie.mmap"], ("patch", "rf"): 12, ("patch", "stride"): 6}
+        self.changes = []
+
+    def get(self, group, key):
+        return self.values[(group, key)]
+
+    def change_params(self, params):
+        self.changes.append(params)
+
+
+@pytest.fixture
+def tuning_run(monkeypatch):
+    from aceneurotools.calcium_imaging import calcium_imaging_processor as module
+    from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor
+
+    calls = {"show": 0}
+    frames, dims = 2500, (8, 10)
+    Yr = np.random.default_rng(2).random((dims[0] * dims[1], frames)).astype(np.float32)
+    correlation = np.linspace(0, 1, 80).reshape(dims)
+    pnr = np.full(dims, 7.0)
+
+    def correlation_pnr(images, gSig, swap_dim):
+        calls["correlation_pnr"] = (images.shape, gSig, swap_dim)
+        return correlation, pnr
+
+    class Axis:
+        def set_title(self, title):
+            calls["title"] = title
+
+    def view_quilt(*args, **kwargs):
+        calls["view_quilt"] = (args, kwargs)
+        return Axis()
+
+    processor = object.__new__(CalciumImagingProcessor)
+    monkeypatch.setattr(processor, "cleanup_tkinter", lambda: None)
+    monkeypatch.setattr(module.cm, "load_memmap", lambda path: (Yr, dims, frames))
+    monkeypatch.setattr(module.cm.summary_images, "correlation_pnr", correlation_pnr)
+    monkeypatch.setattr(
+        module.cm.utils.visualization, "inspect_correlation_pnr", lambda c, p: calls.__setitem__("inspect", (c, p))
+    )
+    monkeypatch.setattr(module.cm.utils.visualization, "view_quilt", view_quilt)
+    monkeypatch.setattr(module.plt, "show", lambda block=None: calls.__setitem__("show", calls["show"] + 1))
+    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=None)
+    return processor, manager, calls, Yr, dims, correlation, pnr
+
+
+def test_plot_params_draws_the_tuning_images_and_patch_quilt(tuning_run, capsys):
+    processor, manager, calls, Yr, dims, correlation, pnr = tuning_run
+    returned, images = processor.cnmfe_parameter_handler(manager, plot_params=True)
+
+    assert returned is manager and manager.opts_caiman.changes == [{"data": {"dims": dims}}]
+    np.testing.assert_array_equal(images, Yr.T.reshape((2500,) + dims, order="F"))
+    assert calls["correlation_pnr"] == ((1250,) + dims, 3, False), "2500 frames sampled every 2nd frame, gSig=3"
+    assert calls["inspect"][0] is correlation and calls["inspect"][1] is pnr
+    args, kwargs = calls["view_quilt"]
+    # rf=12, stride=6 -> width 25, overlap 7, step 18 (the previous inline arithmetic).
+    assert args == (correlation, 18, 7)
+    assert kwargs == {
+        "vmin": np.percentile(correlation, 50),
+        "vmax": np.percentile(correlation, 99.5),
+        "color": "yellow",
+        "figsize": (4, 4),
+    }
+    assert calls["title"] == "CNMFE Patch Width 25, Overlap 7"
+    assert calls["show"] == 2
+    assert "Patch width: 25 , Stride: 18, Overlap: 7" in capsys.readouterr().out
+
+
+def test_without_plot_params_nothing_is_drawn(tuning_run):
+    processor, manager, calls, Yr, dims, _, _ = tuning_run
+    _, images = processor.cnmfe_parameter_handler(manager, plot_params=False)
+    assert images.shape == (2500,) + dims
+    assert set(calls) == {"show"} and calls["show"] == 0
```
