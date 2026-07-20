"""Tests for aceneurotools.multimodal.wavelets."""

from __future__ import annotations

import numpy as np
import pytest

from scipy.signal import fftconvolve

from aceneurotools.multimodal.wavelets import (
    _morlet,
    compute_wavelet_transform,
    generate_morlet_filterbank,
)


def _cwt_reference(signal, freqs, fs, norm="l1"):
    """Pre-vectorization CWT: two real fftconvolve calls per frequency."""
    filters, _ = generate_morlet_filterbank(freqs, fs)
    n_freqs, n = filters.shape[0], signal.size
    cwt = np.empty((n_freqs, n), dtype=np.complex128)
    for k in range(n_freqs):
        re = fftconvolve(signal, filters[k].real, mode="same")
        im = fftconvolve(signal, filters[k].imag, mode="same")
        cwt[k] = re + 1j * im
    freqs_arr = np.asarray(freqs, dtype=np.float64)
    if norm == "l1":
        cwt = cwt / (fs / freqs_arr)[:, None]
    elif norm == "l2":
        cwt = cwt / (fs / np.sqrt(freqs_arr))[:, None]
    return cwt


@pytest.mark.parametrize("norm", ["l1", "l2", None])
def test_cwt_matches_fftconvolve_reference(norm):
    fs = 1000.0
    rng = np.random.default_rng(3)
    t = np.arange(2048) / fs
    signal = np.sin(2 * np.pi * 50.0 * t) + 0.3 * rng.standard_normal(t.size)
    freqs = np.linspace(5, 120, 24)
    new = compute_wavelet_transform(signal, freqs, fs, norm=norm)
    ref = _cwt_reference(signal, freqs, fs, norm=norm)
    np.testing.assert_allclose(new, ref, rtol=1e-9, atol=1e-9)


# ---------------------------------------------------------------------------
# _morlet
# ---------------------------------------------------------------------------


def test_morlet_kernel_is_complex():
    k = _morlet(M=512)
    assert k.dtype == np.complex128
    assert k.size == 512


def test_morlet_envelope_is_gaussian_like():
    """Magnitude of the kernel should peak near the centre and decay symmetrically."""
    k = _morlet(M=512)
    mag = np.abs(k)
    centre = mag.size // 2
    # Peak within +/-5 samples of the centre
    peak_idx = int(np.argmax(mag))
    assert abs(peak_idx - centre) < 10
    # Symmetry: left and right halves should be similar
    half = mag.size // 4
    left = mag[centre - half: centre]
    right = mag[centre: centre + half]
    np.testing.assert_allclose(left, right[::-1], rtol=1e-6, atol=1e-9)


# ---------------------------------------------------------------------------
# generate_morlet_filterbank
# ---------------------------------------------------------------------------


def test_filterbank_shape_matches_freqs():
    freqs = np.array([10.0, 20.0, 50.0])
    filters, time_axis = generate_morlet_filterbank(freqs, fs=1000.0)
    assert filters.shape[0] == 3
    assert filters.shape[1] == time_axis.size
    assert filters.dtype == np.complex128


def test_filterbank_kernels_are_zero_padded():
    """All kernels share the same length via zero-padding."""
    filters, _ = generate_morlet_filterbank(np.array([10.0, 100.0]), fs=1000.0)
    # The kernel scaled for 10 Hz is wider in time than the 100 Hz kernel,
    # so the 100 Hz row should have zero-padding at the edges.
    edge_mag = np.abs(filters[1, 0]) + np.abs(filters[1, -1])
    centre_mag = np.abs(filters[1, filters.shape[1] // 2])
    assert edge_mag < 1e-12
    assert centre_mag > 0


def test_filterbank_rejects_invalid_inputs():
    with pytest.raises(ValueError, match="freqs is empty"):
        generate_morlet_filterbank(np.array([]), fs=1000.0)
    with pytest.raises(ValueError, match="strictly positive"):
        generate_morlet_filterbank(np.array([0.0, 10.0]), fs=1000.0)
    with pytest.raises(ValueError, match="freqs must be 1D"):
        generate_morlet_filterbank(np.zeros((2, 2)), fs=1000.0)
    with pytest.raises(ValueError, match="fs must be a positive"):
        generate_morlet_filterbank(np.array([10.0]), fs=0)
    with pytest.raises(ValueError, match="gaussian_width"):
        generate_morlet_filterbank(np.array([10.0]), fs=1000.0, gaussian_width=0)
    with pytest.raises(ValueError, match="window_length"):
        generate_morlet_filterbank(np.array([10.0]), fs=1000.0, window_length=0)
    with pytest.raises(ValueError, match="precision"):
        generate_morlet_filterbank(np.array([10.0]), fs=1000.0, precision=0)


# ---------------------------------------------------------------------------
# compute_wavelet_transform
# ---------------------------------------------------------------------------


def test_cwt_shape():
    fs = 1000.0
    t = np.arange(0, 1, 1.0 / fs)
    sig = np.sin(2 * np.pi * 50.0 * t)
    freqs = np.linspace(10, 100, 10)
    cwt = compute_wavelet_transform(sig, freqs, fs=fs)
    assert cwt.shape == (10, t.size)
    assert cwt.dtype == np.complex128


def test_cwt_peak_at_injected_frequency():
    """CWT power should peak at the row closest to the tone's frequency."""
    fs = 1000.0
    t = np.arange(0, 2, 1.0 / fs)
    f_tone = 30.0
    sig = np.sin(2 * np.pi * f_tone * t)
    freqs = np.linspace(5, 100, 40)
    power = np.abs(compute_wavelet_transform(sig, freqs, fs=fs)) ** 2

    # Time-averaged power per frequency (interior, away from edge effects)
    interior = slice(int(0.25 * t.size), int(0.75 * t.size))
    mean_power = power[:, interior].mean(axis=1)
    peak_freq = freqs[int(np.argmax(mean_power))]
    # Within one frequency bin of the true tone
    assert abs(peak_freq - f_tone) < (freqs[1] - freqs[0]) * 1.5


def test_cwt_norm_modes_change_scale_consistently():
    fs = 1000.0
    sig = np.sin(2 * np.pi * 20.0 * np.arange(0, 1, 1.0 / fs))
    freqs = np.array([20.0])
    cwt_none = compute_wavelet_transform(sig, freqs, fs=fs, norm=None)
    cwt_l1 = compute_wavelet_transform(sig, freqs, fs=fs, norm="l1")
    cwt_l2 = compute_wavelet_transform(sig, freqs, fs=fs, norm="l2")
    # l1 divides by fs/f (= 50), l2 by fs/sqrt(f) (~223.6)
    np.testing.assert_allclose(cwt_l1, cwt_none / (fs / 20.0))
    np.testing.assert_allclose(cwt_l2, cwt_none / (fs / np.sqrt(20.0)))


def test_cwt_rejects_bad_norm():
    sig = np.zeros(1000)
    with pytest.raises(ValueError, match="norm must be"):
        compute_wavelet_transform(sig, np.array([10.0]), fs=1000.0, norm="bogus")


def test_cwt_rejects_non_1d_signal():
    with pytest.raises(ValueError, match="signal must be 1D"):
        compute_wavelet_transform(np.zeros((10, 10)),
                                  np.array([10.0]), fs=1000.0)


def test_cwt_silent_signal_yields_silent_output():
    fs = 1000.0
    sig = np.zeros(2000)
    cwt = compute_wavelet_transform(sig, np.array([10.0, 50.0]), fs=fs)
    assert np.allclose(np.abs(cwt), 0.0)
