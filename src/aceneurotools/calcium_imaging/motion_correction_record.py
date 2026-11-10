"""Persist motion-correction shifts so they can be inspected after a run.

CaImAn's ``MotionCorrect`` object holds the per-frame shifts and templates only
in memory. This module copies them to a small ``.npz`` file without importing
CaImAn, so reports can be drawn later without re-running motion correction.

Shifts and templates are stored as float32 to keep piecewise-rigid files small
(per-frame, per-patch shifts dominate the size). The file also records the
motion settings that define the patch grid (``strides``, ``overlaps``,
``max_shifts``; with a template's shape they locate each patch), and the movie
the shifts were computed from, so a report can check that a file in
``saved_movies/`` belongs to the run it is describing. Attributes that are
missing, empty or not numeric are skipped rather than failing the run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

MOTION_CORRECTION_SHIFTS_FILENAME = "motion_correction_shifts.npz"

#: Float ``MotionCorrect`` arrays copied when present and non-empty (stored as float32).
_FLOAT_ATTRIBUTES = (
    "shifts_rig",
    "x_shifts_els",
    "y_shifts_els",
    "total_template_rig",
    "total_template_els",
)
#: Integer ``MotionCorrect`` settings describing the patch grid (stored as int64).
#: (``coord_shifts_els`` is not saved: CaImAn 1.13 fills it with ``None`` per frame.)
_INTEGER_ATTRIBUTES = (
    "strides",
    "overlaps",
    "max_shifts",
)


def motion_correction_arrays(mc: Any, *, pw_rigid: bool, frame_rate: float | None = None) -> dict[str, np.ndarray]:
    """Return the shift and template arrays held by a CaImAn ``MotionCorrect`` object.

    Args:
        mc: Object with CaImAn ``MotionCorrect`` attributes.
        pw_rigid: Whether piecewise-rigid correction was requested.
        frame_rate: Movie frame rate in Hz, recorded for plotting against time.
    """
    arrays: dict[str, np.ndarray] = {}
    for names, dtype in ((_FLOAT_ATTRIBUTES, np.float32), (_INTEGER_ATTRIBUTES, np.int64)):
        for name in names:
            value = getattr(mc, name, None)
            if value is None:
                continue
            try:
                array = np.asarray(value, dtype=dtype)
            except (TypeError, ValueError):
                continue
            if array.size:
                arrays[name] = array
    arrays["pw_rigid"] = np.asarray(bool(pw_rigid))
    border = getattr(mc, "border_to_0", None)
    if border is not None:
        arrays["border_to_0"] = np.asarray(border)
    if frame_rate is not None:
        arrays["frame_rate"] = np.asarray(float(frame_rate))
    source = getattr(mc, "fname", None)
    if source:
        names = [source] if isinstance(source, (str, Path)) else list(source)
        arrays["source_movie"] = np.asarray([str(name) for name in names])
    return arrays


def save_motion_correction_shifts(
    mc: Any,
    directory: str | Path,
    *,
    pw_rigid: bool,
    frame_rate: float | None = None,
    filename: str = MOTION_CORRECTION_SHIFTS_FILENAME,
) -> str:
    """Write the motion-correction shifts and templates to ``directory/filename``.

    Returns:
        The written file path.
    """
    target = Path(directory) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(target, **motion_correction_arrays(mc, pw_rigid=pw_rigid, frame_rate=frame_rate))
    return str(target)


def load_motion_correction_shifts(path: str | Path) -> dict[str, np.ndarray]:
    """Read a file written by :func:`save_motion_correction_shifts`."""
    with np.load(path) as data:
        return {name: data[name] for name in data.files}
