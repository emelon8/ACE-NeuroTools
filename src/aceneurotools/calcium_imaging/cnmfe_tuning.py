"""Non-blocking CNMF-E parameter-tuning computations.

These functions compute the values shown by the interactive ``plot_params``
step of :meth:`CalciumImagingProcessor.cnmfe_parameter_handler` without
opening windows, so command-line, notebook and GUI callers share one
implementation. CaImAn is imported only by the function that needs it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: Gaussian kernel half-size (``gSig``, pixels) used for the tuning correlation/PNR images.
#: The legacy code wrote ``gsig_tmp = (3, 3)`` but passed only its first element.
TUNING_GSIG = 3

#: Subsampling target for tuning images: the frame step is ``n_frames // TUNING_MAX_FRAMES``
#: (at least 1), so between ``TUNING_MAX_FRAMES`` and ``2 * TUNING_MAX_FRAMES - 1`` frames
#: are used for movies longer than the target, and every frame for shorter movies.
TUNING_MAX_FRAMES = 1000


@dataclass(frozen=True)
class CNMFEPatchGeometry:
    """Patch layout derived from CaImAn ``rf`` and ``stride`` parameters (pixels)."""

    width: int
    stride: int
    overlap: int


def cnmfe_patch_geometry(rf: int, stride: int) -> CNMFEPatchGeometry:
    """Return the patch width, step and overlap drawn by the tuning quilt plot."""
    width = rf * 2 + 1
    overlap = stride + 1
    return CNMFEPatchGeometry(width=width, stride=width - overlap, overlap=overlap)


def tuning_frame_step(n_frames: int, max_frames: int = TUNING_MAX_FRAMES) -> int:
    """Return the legacy frame step ``max(n_frames // max_frames, 1)``.

    ``max_frames`` is a target, not a bound: 1999 frames with a target of 1000 gives
    a step of 1, so all 1999 frames are used. This matches the previous inline code.
    """
    if isinstance(max_frames, bool) or not isinstance(max_frames, (int, np.integer)) or max_frames < 1:
        raise ValueError("max_frames must be a positive whole number.")
    return max(n_frames // max_frames, 1)


def compute_cnmfe_tuning_images(
    images: np.ndarray,
    gsig: int = TUNING_GSIG,
    max_frames: int = TUNING_MAX_FRAMES,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the correlation and peak-to-noise-ratio images used for tuning.

    Args:
        images: Movie with frames on the first axis, shape ``(T, height, width)``.
        gsig: Gaussian kernel half-size in pixels, passed to CaImAn as ``gSig``.
        max_frames: Subsampling target; see :func:`tuning_frame_step`.

    Returns:
        ``(correlation_image, peak_to_noise_ratio)`` from
        ``caiman.summary_images.correlation_pnr``.
    """
    if isinstance(gsig, bool) or not isinstance(gsig, (int, np.integer)) or gsig < 1:
        raise ValueError("gsig must be a positive whole number of pixels.")
    import caiman as cm

    step = tuning_frame_step(images.shape[0], max_frames)
    return cm.summary_images.correlation_pnr(images[::step], gSig=int(gsig), swap_dim=False)


def quilt_display_limits(correlation_image: np.ndarray) -> tuple[float, float]:
    """Return the ``(vmin, vmax)`` percentiles used to display the patch quilt."""
    values = np.ravel(correlation_image)
    return float(np.percentile(values, 50)), float(np.percentile(values, 99.5))
