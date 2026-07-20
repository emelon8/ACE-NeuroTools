"""Morlet continuous wavelet transform (CWT) for time-frequency analysis.

Complements the existing Welch / multitaper spectral tools (which trade time
resolution for frequency resolution) with a CWT that resolves transient
oscillations — useful for spindle bursts, K-complexes, and short propofol-
alpha epochs under anesthesia.

All functions operate on plain 1-D numpy arrays + a sampling rate in Hz.
"""

from __future__ import annotations

import numpy as np
from scipy.fft import fft, ifft, next_fast_len


def _morlet(
    M: int = 1024,
    gaussian_width: float = 1.5,
    window_length: float = 1.0,
    precision: int = 8,
) -> np.ndarray:
    """Complex Morlet wavelet kernel sampled at ``M`` points.

    Parameters
    ----------
    M : int
        Number of kernel samples.
    gaussian_width : float
        Width of the Gaussian envelope (larger = wider in time, narrower in freq).
    window_length : float
        Centre frequency multiplier; controls the number of oscillations under
        the envelope.
    precision : int
        Half-extent of the kernel domain (kernel spans ``[-precision, +precision]``).

    Returns
    -------
    np.ndarray, dtype=complex128
        Complex Morlet wavelet kernel, length ``M``.
    """
    x = np.linspace(-precision, precision, M)
    return (
        ((np.pi * gaussian_width) ** (-0.25))
        * np.exp(-(x ** 2) / gaussian_width)
        * np.exp(1j * 2 * np.pi * window_length * x)
    )


def generate_morlet_filterbank(
    freqs: np.ndarray,
    fs: float,
    gaussian_width: float = 1.5,
    window_length: float = 1.0,
    precision: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a bank of Morlet filters scaled to each frequency in ``freqs``.

    The same mother wavelet is finely sampled once at ``2**precision`` points
    and then resampled (subsampled) to obtain each filter at the requested
    target frequency.

    Parameters
    ----------
    freqs : np.ndarray
        Target frequencies in Hz (strictly positive, 1-D).
    fs : float
        Sampling rate in Hz.
    gaussian_width, window_length, precision : float / int
        See :func:`_morlet`. ``precision`` here is the log2 of the mother-
        wavelet sample count (``2**precision`` total samples).

    Returns
    -------
    filters : np.ndarray, shape (n_freqs, kernel_len), dtype=complex128
        One Morlet kernel per row. All rows zero-padded to the same length.
    time : np.ndarray, shape (kernel_len,)
        Time axis (seconds) corresponding to the kernel samples.
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    if freqs.ndim != 1:
        raise ValueError("freqs must be 1D.")
    if freqs.size == 0:
        raise ValueError("freqs is empty.")
    if np.min(freqs) <= 0:
        raise ValueError("All frequencies must be strictly positive.")
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("fs must be a positive finite number.")
    if gaussian_width <= 0:
        raise ValueError("gaussian_width must be > 0.")
    if window_length <= 0:
        raise ValueError("window_length must be > 0.")
    if not isinstance(precision, int) or precision <= 0:
        raise ValueError("precision must be a positive int.")

    cutoff = 8
    mother = np.conj(
        _morlet(int(2 ** precision),
                gaussian_width=gaussian_width,
                window_length=window_length)
    )
    x = np.linspace(-cutoff, cutoff, int(2 ** precision))

    kernels: list[np.ndarray] = []
    max_len = -1
    time_axis: np.ndarray | None = None
    for freq in freqs:
        scale = window_length / (freq / fs)
        j = np.arange(scale * (x[-1] - x[0]) + 1) / (scale * (x[1] - x[0]))
        j = np.ceil(j).astype(int)
        if j.size > 0 and j[-1] >= mother.size:
            j = j[j < mother.size]
        scaled = mother[j][::-1]
        if scaled.size > max_len:
            max_len = scaled.size
            time_axis = np.linspace(
                -cutoff * window_length / float(freq),
                cutoff * window_length / float(freq),
                max_len,
            )
        kernels.append(scaled)

    padded = [
        np.pad(
            k,
            ((max_len - k.size) // 2, (max_len - k.size + 1) // 2),
            constant_values=0.0,
        )
        for k in kernels
    ]
    filters = np.stack(padded, axis=0)
    if time_axis is None:
        time_axis = np.zeros(filters.shape[1], dtype=np.float64)
    return filters, time_axis


def compute_wavelet_transform(
    signal: np.ndarray,
    freqs: np.ndarray,
    fs: float,
    gaussian_width: float = 1.5,
    window_length: float = 1.0,
    precision: int = 16,
    norm: str | None = "l1",
) -> np.ndarray:
    """Continuous wavelet transform of a 1-D signal at the requested frequencies.

    Parameters
    ----------
    signal : np.ndarray, shape (N,)
        1-D continuous time series.
    freqs : np.ndarray
        Target frequencies in Hz (strictly positive, 1-D).
    fs : float
        Sampling rate in Hz.
    gaussian_width, window_length, precision :
        Morlet parameters; see :func:`generate_morlet_filterbank`.
    norm : ``'l1'``, ``'l2'``, or None
        Coefficient normalization:

        * ``'l1'`` (default) — divide by ``fs / freqs`` (per-frequency
          amplitude normalization)
        * ``'l2'`` — divide by ``fs / sqrt(freqs)`` (energy normalization)
        * None — return raw convolution

    Returns
    -------
    np.ndarray, shape (len(freqs), N), dtype=complex128
        Complex CWT coefficients. Take ``np.abs(cwt)`` for amplitude and
        ``np.abs(cwt) ** 2`` for power.

    Examples
    --------
    Decompose a 50 Hz tone with 10 frequency bins from 10–100 Hz::

        fs = 1000.0
        t = np.arange(0, 1, 1 / fs)
        signal = np.sin(2 * np.pi * 50.0 * t)
        freqs = np.linspace(10, 100, 10)
        cwt = compute_wavelet_transform(signal, freqs, fs)
        # power = np.abs(cwt) ** 2
    """
    if signal.ndim != 1:
        raise ValueError("signal must be 1D.")
    if norm not in ("l1", "l2", None):
        raise ValueError("norm must be 'l1', 'l2', or None.")

    filters, _ = generate_morlet_filterbank(
        freqs, fs, gaussian_width, window_length, precision
    )

    n_samples = signal.size
    kernel_len = filters.shape[1]

    # FFT the signal once and reuse its spectrum for every filter, rather than
    # re-transforming it inside 2*n_freqs separate fftconvolve calls. Because
    # the signal is real, conv(s, re) + 1j*conv(s, im) == conv(s, kernel), so a
    # single complex convolution per frequency (vectorized here) suffices.
    n_fft = next_fast_len(n_samples + kernel_len - 1)
    signal_fft = fft(signal, n=n_fft)
    filters_fft = fft(filters, n=n_fft, axis=1)
    full = ifft(filters_fft * signal_fft[None, :], axis=1)
    # scipy's "same" mode keeps the central n_samples of the full convolution.
    start = (kernel_len - 1) // 2
    cwt = np.ascontiguousarray(full[:, start:start + n_samples])

    freqs_arr = np.asarray(freqs, dtype=np.float64)
    if norm == "l1":
        cwt = cwt / (fs / freqs_arr)[:, None]
    elif norm == "l2":
        cwt = cwt / (fs / np.sqrt(freqs_arr))[:, None]
    return cwt
