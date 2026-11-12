"""Persist motion-correction shifts so they can be inspected after a run.

CaImAn's ``MotionCorrect`` object holds the per-frame shifts and templates only
in memory. This module copies them to a small ``.npz`` file without importing
CaImAn, so reports can be drawn later without re-running motion correction.

Shifts and templates are stored as float32 to keep piecewise-rigid files small
(per-frame, per-patch shifts dominate the size). The file also records the
motion settings that define the patch grid (``strides``, ``overlaps``,
``max_shifts``, ``upsample_factor_grid`` and ``shifts_opencv``; with a
template's shape they locate each patch), the movie the shifts were computed
from and the time the file was written (UTC). Attributes that are missing or
empty are left out. Values that cannot be stored as numbers are also left out,
and their names are listed in ``skipped_attributes``; neither fails the run.

The file is written to a temporary file in the same directory, flushed to disk
and then renamed over the destination, so a save that fails with an error leaves
any earlier file intact. A process killed outright during the save can leave a
hidden ``.motion_correction_shifts.npz.*.tmp`` file behind.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from datetime import datetime, timezone
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
    "upsample_factor_grid",
    "border_to_0",
)
#: Boolean ``MotionCorrect`` settings. With ``shifts_opencv=False``, CaImAn returns
#: piecewise shifts on a grid refined by ``upsample_factor_grid``.
_BOOLEAN_ATTRIBUTES = ("shifts_opencv",)


def motion_correction_arrays(mc: Any, *, pw_rigid: bool, frame_rate: float | None = None) -> dict[str, np.ndarray]:
    """Return the shift and template arrays held by a CaImAn ``MotionCorrect`` object.

    Args:
        mc: Object with CaImAn ``MotionCorrect`` attributes.
        pw_rigid: Whether piecewise-rigid correction was requested.
        frame_rate: Movie frame rate in Hz, recorded for plotting against time.
    """
    arrays: dict[str, np.ndarray] = {}
    skipped: list[str] = []
    for names, dtype in (
        (_FLOAT_ATTRIBUTES, np.float32),
        (_INTEGER_ATTRIBUTES, np.int64),
        (_BOOLEAN_ATTRIBUTES, np.bool_),
    ):
        for name in names:
            value = getattr(mc, name, None)
            if value is None:
                continue
            try:
                array = np.asarray(value, dtype=dtype)
            except (TypeError, ValueError, OverflowError):
                skipped.append(name)
                continue
            if array.size:
                arrays[name] = array
    arrays["pw_rigid"] = np.asarray(bool(pw_rigid))
    if frame_rate is not None:
        try:
            arrays["frame_rate"] = np.asarray(float(frame_rate))
        except (TypeError, ValueError):
            skipped.append("frame_rate")
    source = getattr(mc, "fname", None)
    if source is not None:
        names = [source] if isinstance(source, (str, Path)) else np.ravel(np.asarray(source, dtype=object)).tolist()
        names = [str(name) for name in names if name is not None]
        if names:
            arrays["source_movie"] = np.asarray(names)
    arrays["saved_at"] = np.asarray(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if skipped:
        arrays["skipped_attributes"] = np.asarray(skipped)
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

    The file is written to a temporary file first, flushed to disk and then
    renamed, so a save that fails with an error never leaves a partial file at
    ``directory/filename``. The name is used exactly as given (no ``.npz`` suffix
    is added).

    Returns:
        The written file path.
    """
    arrays = motion_correction_arrays(mc, pw_rigid=pw_rigid, frame_rate=frame_rate)
    target = Path(directory) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    # A unique name opened with open() (not mkstemp) keeps the umask's usual permissions.
    temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(temporary, "xb") as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temporary)
        raise
    return str(target)


def load_motion_correction_shifts(path: str | Path) -> dict[str, np.ndarray]:
    """Read a file written by :func:`save_motion_correction_shifts`."""
    with np.load(path) as data:
        return {name: data[name] for name in data.files}
