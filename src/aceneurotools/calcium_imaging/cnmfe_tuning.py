"""Window-free CNMF-E parameter-tuning computations.

These functions compute the values shown by the interactive ``plot_params``
step of :meth:`CalciumImagingProcessor.cnmfe_parameter_handler` without
opening windows, so command-line, notebook and GUI callers share one
implementation. They run synchronously: computing the tuning images on a long
movie can take a while, and ``plot_params=True`` itself still waits for each
window to be closed. Importing this module does not import CaImAn; only
:func:`compute_cnmfe_tuning_images` does.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

#: Gaussian kernel half-size (``gSig``, pixels) used for the tuning correlation/PNR images.
#: The legacy code wrote ``gsig_tmp = (3, 3)`` but passed only its first element.
TUNING_GSIG = 3

#: Subsampling target for tuning images: the frame step is ``n_frames // TUNING_MAX_FRAMES``
#: (at least 1), so between ``TUNING_MAX_FRAMES`` and ``2 * TUNING_MAX_FRAMES - 1`` frames
#: are used for movies longer than the target, and every frame for shorter movies.
TUNING_MAX_FRAMES = 1000


def _is_whole_number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, np.integer))


@dataclass(frozen=True)
class CNMFEPatchGeometry:
    """Patch layout derived from CaImAn ``rf`` and ``stride`` parameters (pixels)."""

    width: int
    stride: int
    overlap: int


def cnmfe_patch_geometry(rf: int, stride: int) -> CNMFEPatchGeometry:
    """Return the patch width, step and overlap drawn by the tuning quilt plot.

    ``rf`` is CaImAn's patch half-size and ``stride`` its patch overlap, both single
    whole numbers of pixels. The width is ``2 * rf + 1``, the overlap ``stride + 1``
    and the step between patches ``width - overlap``.

    Raises:
        ValueError: If ``rf`` is not a positive whole number, ``stride`` is not a
            non-negative whole number, or ``stride >= 2 * rf`` (the overlap would be
            at least the patch width, so patches could not advance).
    """
    if not _is_whole_number(rf) or rf < 1:
        raise ValueError("rf must be a positive whole number of pixels.")
    if not _is_whole_number(stride) or stride < 0:
        raise ValueError("stride must be a non-negative whole number of pixels.")
    if stride >= 2 * rf:
        raise ValueError("stride must be smaller than 2 * rf so that patches advance.")
    width = int(rf) * 2 + 1
    overlap = int(stride) + 1
    return CNMFEPatchGeometry(width=width, stride=width - overlap, overlap=overlap)


def tuning_frame_step(n_frames: int, max_frames: int = TUNING_MAX_FRAMES) -> int:
    """Return the legacy frame step ``max(n_frames // max_frames, 1)``.

    ``max_frames`` is a target, not a bound: 1999 frames with a target of 1000 gives
    a step of 1, so all 1999 frames are used. This matches the previous inline code.

    Raises:
        ValueError: If ``n_frames`` is not a non-negative whole number or
            ``max_frames`` is not a positive whole number.
    """
    if not _is_whole_number(n_frames) or n_frames < 0:
        raise ValueError("n_frames must be a non-negative whole number.")
    if not _is_whole_number(max_frames) or max_frames < 1:
        raise ValueError("max_frames must be a positive whole number.")
    return max(int(n_frames) // int(max_frames), 1)


def _caiman_gsig(gsig: int | Sequence[int]) -> int | list[int]:
    if _is_whole_number(gsig) and gsig >= 1:
        return int(gsig)
    if (
        isinstance(gsig, (list, tuple, np.ndarray))
        and len(gsig) == 2
        and all(_is_whole_number(value) and value >= 1 for value in gsig)
    ):
        return [int(value) for value in gsig]
    raise ValueError("gsig must be a positive whole number of pixels or a pair of them, such as 3 or [3, 3].")


def compute_cnmfe_tuning_images(
    images: np.ndarray,
    gsig: int | Sequence[int] = TUNING_GSIG,
    max_frames: int = TUNING_MAX_FRAMES,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the correlation and peak-to-noise-ratio images used for tuning.

    Args:
        images: Movie with frames on the first axis, shape ``(T, height, width)``.
        gsig: Gaussian kernel half-size in pixels, passed to CaImAn as ``gSig``.
            Either one whole number (the ``plot_params`` step uses
            :data:`TUNING_GSIG`) or a ``(rows, columns)`` pair such as the CNMF-E
            ``gSig`` setting.
        max_frames: Subsampling target; see :func:`tuning_frame_step`.

    Returns:
        ``(correlation_image, peak_to_noise_ratio)`` from
        ``caiman.summary_images.correlation_pnr``.

    Raises:
        ValueError: If ``gsig`` or ``max_frames`` is not valid.
    """
    caiman_gsig = _caiman_gsig(gsig)
    step = tuning_frame_step(images.shape[0], max_frames)
    import caiman as cm

    return cm.summary_images.correlation_pnr(images[::step], gSig=caiman_gsig, swap_dim=False)


def quilt_display_limits(correlation_image: np.ndarray) -> tuple[float, float]:
    """Return the ``(vmin, vmax)`` percentiles used to display the patch quilt."""
    values = np.ravel(correlation_image)
    return float(np.percentile(values, 50)), float(np.percentile(values, 99.5))
