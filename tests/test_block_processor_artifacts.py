"""Tests for BlockProcessor artifact Hann-window smoothing.

The per-sample multiply loop was replaced with a single distance-transform
envelope. For isolated artifacts this is identical to the old behavior; for
overlapping/contiguous artifacts it applies the taper once instead of
multiplying overlapping regions repeatedly (the old over-attenuation bug).
"""

from __future__ import annotations

import numpy as np
from scipy.signal.windows import hann

from aceneurotools.ephys.block_processor import BlockProcessor
from aceneurotools.ephys.channel import Channel

HANN_NUM = 75


def _inv_hann(size: int) -> np.ndarray:
    return np.abs(hann(size) - 1)


def _old_multiply(signal: np.ndarray, mask: np.ndarray, window: np.ndarray) -> np.ndarray:
    """Pre-refactor per-sample multiply loop."""
    s = signal.copy()
    half = len(window) // 2
    for idx in np.where(mask)[0]:
        start = max(0, idx - half)
        end = min(len(s), idx + half + 1)
        seg = s[start:end]
        s[start:end] = seg * window[: len(seg)]
    return s


def _ref_min(signal: np.ndarray, mask: np.ndarray, window: np.ndarray) -> np.ndarray:
    """Intended single-application semantics: nearest artifact taper wins."""
    n = len(signal)
    half = len(window) // 2
    env = np.ones(n)
    for idx in np.where(mask)[0]:
        start = max(0, idx - half)
        end = min(n, idx + half + 1)
        woff = start - (idx - half)
        w = window[woff : woff + (end - start)]
        np.minimum(env[start:end], w, out=env[start:end])
    return signal * env


def _apply(signal: np.ndarray, mask: np.ndarray, window: np.ndarray) -> np.ndarray:
    bp = object.__new__(BlockProcessor)  # method uses no instance state
    ch = Channel("c", signal.copy(), 1000.0, np.arange(len(signal)) / 1000.0, {})
    bp._apply_hann_window(ch, mask, window, dt=1 / 1000.0)
    return ch.signal


def test_isolated_artifacts_match_old_behavior():
    rng = np.random.default_rng(0)
    signal = rng.standard_normal(5000)
    mask = np.zeros(5000, dtype=bool)
    for centre in (200, 1000, 2500, 4000):  # spaced further apart than the window
        mask[centre] = True
    window = _inv_hann(HANN_NUM)
    np.testing.assert_allclose(_apply(signal, mask, window), _old_multiply(signal, mask, window))


def test_overlapping_artifacts_apply_taper_once():
    rng = np.random.default_rng(1)
    signal = rng.standard_normal(5000)
    mask = np.zeros(5000, dtype=bool)
    mask[1000:1040] = True  # contiguous run
    mask[3000:3005] = True
    mask[10:15] = True  # near the left boundary
    window = _inv_hann(HANN_NUM)

    result = _apply(signal, mask, window)
    # Matches the correct single-application reference...
    np.testing.assert_allclose(result, _ref_min(signal, mask, window))
    # ...and does not over-attenuate the run flanks the way the old loop did.
    old = _old_multiply(signal, mask, window)
    flank = slice(960, 1000)  # left flank of the 1000:1040 run
    assert np.abs(result[flank]).sum() >= np.abs(old[flank]).sum()


def test_masked_samples_are_zeroed():
    signal = np.ones(200)
    mask = np.zeros(200, dtype=bool)
    mask[100] = True
    window = _inv_hann(HANN_NUM)
    result = _apply(signal, mask, window)
    # inverted-Hann centre is 0 -> the artifact sample itself is zeroed.
    assert result[100] == 0.0


def test_no_artifacts_is_noop():
    signal = np.linspace(-1, 1, 300)
    mask = np.zeros(300, dtype=bool)
    window = _inv_hann(HANN_NUM)
    np.testing.assert_array_equal(_apply(signal, mask, window), signal)
