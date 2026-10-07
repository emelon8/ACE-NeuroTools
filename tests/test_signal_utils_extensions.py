"""Tests for the hilbert envelope + filter frequency response additions to signal_utils."""

from __future__ import annotations

import numpy as np
import pytest
from scipy.signal import butter, freqz

from aceneurotools.multimodal.signal_utils import (
    compute_hilbert_envelope,
    get_filter_frequency_response,
)

# ---------------------------------------------------------------------------
# compute_hilbert_envelope
# ---------------------------------------------------------------------------


def test_envelope_constant_for_pure_tone():
    fs = 1000.0
    t = np.arange(0, 5, 1 / fs)
    f0 = 10.0
    x = np.cos(2 * np.pi * f0 * t)
    env = compute_hilbert_envelope(x)
    # Trim the edge transients
    interior = env[int(fs) // 2 : -int(fs) // 2]
    assert interior.mean() == pytest.approx(1.0, rel=0.05)
    assert interior.std() < 0.05


def test_envelope_tracks_am_modulation():
    fs = 2000.0
    t = np.arange(0, 4, 1 / fs)
    carrier = np.cos(2 * np.pi * 50 * t)
    modulator = 1 + 0.5 * np.cos(2 * np.pi * 2 * t)
    x = modulator * carrier
    env = compute_hilbert_envelope(x)
    # Envelope should be close to |modulator| in the interior
    interior = slice(int(fs), -int(fs))
    err = np.abs(env[interior] - modulator[interior])
    assert err.mean() < 0.1


def test_envelope_shape_preserved():
    x = np.random.default_rng(0).standard_normal(500)
    env = compute_hilbert_envelope(x)
    assert env.shape == x.shape
    assert (env >= 0).all()


# ---------------------------------------------------------------------------
# get_filter_frequency_response
# ---------------------------------------------------------------------------


def test_freq_response_matches_scipy_directly():
    fr = 1000.0
    freqs, mag = get_filter_frequency_response(
        freq_range=(5.0, 50.0),
        fr=fr,
        filter_type="bandpass",
        order=2,
    )
    b, a = butter(2, (5.0, 50.0), btype="bandpass", fs=fr)
    w, h = freqz(b, a, worN=1024, fs=fr)
    np.testing.assert_allclose(freqs, w)
    np.testing.assert_allclose(mag, np.abs(h))


def test_freq_response_bandpass_passes_centre_attenuates_edges():
    fr = 1000.0
    low, high = 10.0, 100.0
    freqs, mag = get_filter_frequency_response(
        freq_range=(low, high),
        fr=fr,
        filter_type="bandpass",
        order=4,
    )
    centre_freq = (low + high) / 2
    centre_idx = int(np.argmin(np.abs(freqs - centre_freq)))
    # At DC and Nyquist, magnitude should be small
    assert mag[0] < 0.1
    assert mag[-1] < 0.1
    # At centre, magnitude should be near unity
    assert mag[centre_idx] > 0.9


def test_freq_response_lowpass_attenuates_above_cutoff():
    fr = 1000.0
    cutoff = 50.0
    freqs, mag = get_filter_frequency_response(
        freq_range=cutoff,
        fr=fr,
        filter_type="lowpass",
        order=4,
    )
    # below cutoff: pass; above 2*cutoff: significant attenuation
    below = freqs < cutoff / 2
    above = freqs > 2 * cutoff
    assert mag[below].mean() > 0.95
    assert mag[above].mean() < 0.5


def test_freq_response_returns_ndarrays():
    freqs, mag = get_filter_frequency_response((1.0, 10.0), fr=100.0)
    assert isinstance(freqs, np.ndarray)
    assert isinstance(mag, np.ndarray)
    assert freqs.shape == mag.shape


# ---------------------------------------------------------------------------
# filter_signals delegates to the canonical filter
# ---------------------------------------------------------------------------


def test_filter_signals_matches_canonical_and_manual():
    from scipy.signal import filtfilt

    from aceneurotools.multimodal.signal_utils import filter_signals
    from aceneurotools.shared.signal_processing import filter_signal

    rng = np.random.default_rng(0)
    s1 = rng.standard_normal(4000)
    s2 = rng.standard_normal(4000)
    fr, freq_range, order = 200.0, [4.0, 12.0], 2

    out1, out2 = filter_signals(s1, s2, fr, freq_range, order)

    # Matches the canonical filter_signal ...
    np.testing.assert_array_equal(out1, filter_signal(s1, n=order, cut=freq_range, ftype="butter", btype="band", fs=fr))
    # ... and the old manual Nyquist-normalized butter/filtfilt.
    nyq = 0.5 * fr
    b, a = butter(order, [freq_range[0] / nyq, freq_range[1] / nyq], btype="band")
    np.testing.assert_allclose(out1, filtfilt(b, a, s1))
    np.testing.assert_allclose(out2, filtfilt(b, a, s2))
