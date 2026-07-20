"""Canonical signal filtering for ACE-NeuroTools.

This module is the single authoritative implementation of FIR and Butterworth
filtering used across the package.  Both ``shared/misc_functions.py:filter_data``
and ``ephys/ephys_data_manager.py:EphysDataManager._filter_data`` delegate to
:func:`filter_signal` so that any fix or improvement is applied everywhere at once.

Usage example::

    from aceneurotools.shared.signal_processing import filter_signal
    filtered = filter_signal(raw, n=2, cut=[0.5, 4.0], ftype='butter', btype='band', fs=2000.0)
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.signal import bode as scipy_bode
from scipy.signal import butter, filtfilt, firwin, freqz  # type: ignore

logger = logging.getLogger(__name__)


def filter_signal(
    data: np.ndarray,
    n: int,
    cut: float | list[float] | np.ndarray,
    ftype: str,
    btype: str,
    fs: float,
    bode_plot: bool = False,
) -> np.ndarray:
    """Apply a zero-phase FIR or Butterworth filter to *data*.

    This is the single canonical implementation shared by
    ``shared/misc_functions.py:filter_data`` and
    ``ephys/ephys_data_manager.py:EphysDataManager._filter_data``.

    Args:
        data: 1-D NumPy array of signal values.
        n: Filter order (Butterworth) or number of taps (FIR).
            A good value for FIR is 10 000; default Butterworth is 2.
        cut: Cutoff frequency in Hz, or ``[low, high]`` for band types.
        ftype: Filter family — ``'fir'``, ``'butter'``, or ``'butterworth'``.
            Case-insensitive.
        btype: Band type — ``'low'``, ``'high'``, ``'band'``, ``'bandpass'``,
            ``'lowpass'``, ``'highpass'`` (scipy / firwin conventions).
        fs: Sampling frequency in Hz.
        bode_plot: When ``True``, display Bode magnitude and phase diagrams.
            Requires a matplotlib GUI backend; do not use in headless mode.

    Returns:
        Zero-phase filtered signal as a 1-D NumPy array with the same length
        as *data*.

    Raises:
        ValueError: If *ftype* is not ``'fir'``, ``'butter'``, or
            ``'butterworth'``.

    Notes:
        For FIR filters, *btype* is passed as ``pass_zero`` to
        :func:`scipy.signal.firwin` (``'lowpass'`` / ``'highpass'`` /
        ``'bandpass'`` / ``'bandstop'`` are all accepted).

        For Butterworth filters, *btype* is passed directly to
        :func:`scipy.signal.butter` (``'low'``, ``'high'``, ``'band'``, etc.).
    """
    ftype_lower = ftype.lower()

    if ftype_lower == "fir":
        h = firwin(n, cut, pass_zero=btype, fs=fs)
        filtered_data: np.ndarray = filtfilt(h, 1, data)

        if bode_plot:
            import matplotlib.pyplot as plt

            w, a = freqz(h, worN=10_000, fs=fs)
            plt.figure()
            plt.semilogx(w, abs(a))
            plt.title("FIR frequency response")

            w_b, mag, phase = scipy_bode((h, 1), w=2 * np.pi * w)
            plt.figure()
            plt.semilogx(w_b, mag)
            plt.figure()
            plt.semilogx(w_b, phase)

    elif ftype_lower in ("butterworth", "butter"):
        b, a_filt = butter(n, cut, btype=btype, fs=fs)
        filtered_data = filtfilt(b, a_filt, data)

        if bode_plot:
            import matplotlib.pyplot as plt

            w, h_resp = freqz(b, a_filt, worN=10_000, fs=fs)
            plt.figure()
            plt.semilogx(w, abs(h_resp))
            plt.title("Butterworth frequency response")

            w_b, mag, phase = scipy_bode((b, a_filt), w=2 * np.pi * w)
            plt.figure()
            plt.semilogx(w_b, mag)
            plt.figure()
            plt.semilogx(w_b, phase)

    else:
        raise ValueError(
            f"Unknown filter type: {ftype!r}.  "
            "Supported values: 'fir', 'butter', 'butterworth'."
        )

    return filtered_data


def filter_data(
    data: np.ndarray,
    n: int,
    cut: float | list[float] | np.ndarray,
    ftype: str,
    btype: str,
    fs: float,
    bodePlot: bool = False,
) -> np.ndarray:
    """Backward-compatible alias for :func:`filter_signal`.

    Kept so existing callers (``from aceneurotools.shared import filter_data``)
    keep working. Lives here rather than in ``shared/misc_functions`` so that
    importing :mod:`aceneurotools.shared` does not pull in that module's heavy
    (cv2 / matplotlib) import surface. All logic is in :func:`filter_signal`.
    """
    return filter_signal(data, n=n, cut=cut, ftype=ftype, btype=btype, fs=fs, bode_plot=bodePlot)
