"""Equivalence tests for the vectorized TTL->ephys alignment.

find_ephys_idx_of_TTL_events was rewritten from a per-frame argmin scan to a
vectorized np.searchsorted nearest-neighbor. These tests pin the new output to
(a) a brute-force argmin reference (the mathematically-correct nearest index)
and (b) a faithful re-implementation of the old forward-scanning loop on
gap-free monotonic data, where the two must agree exactly.
"""

from __future__ import annotations

import numpy as np

from aceneurotools.ephys.channel import Channel
from aceneurotools.multimodal.miniscope_ephys_alignment_utils import (
    _nearest_sorted_index,
    find_ephys_idx_of_TTL_events,
)


def _brute_nn(time_vector: np.ndarray, queries: np.ndarray) -> np.ndarray:
    return np.array([np.abs(time_vector - q).argmin() for q in queries], dtype=int)


def _old_all_ttl_loop(tCaIm, time_vector, sampling_rate, frame_rate) -> np.ndarray:
    """Faithful copy of the pre-refactor forward-scanning loop."""
    out = np.empty(len(tCaIm), dtype=int)
    end_point = round(int(sampling_rate) * 2 / int(frame_rate))
    last_index = 0
    for k, ev in enumerate(tCaIm):
        if k == 0 or len(time_vector[last_index:]) - end_point < 0:
            out[k] = np.abs(time_vector[last_index:] - ev).argmin() + last_index
        else:
            out[k] = np.abs(time_vector[last_index : last_index + end_point] - ev).argmin() + last_index
        last_index = out[k]
    return out


def _make_channel(time_vector: np.ndarray, sampling_rate: float) -> Channel:
    return Channel("test", np.zeros_like(time_vector), sampling_rate, time_vector, {})


# ---------------------------------------------------------------------------
# _nearest_sorted_index primitive
# ---------------------------------------------------------------------------


def test_nearest_sorted_index_matches_brute():
    rng = np.random.default_rng(1)
    tv = np.sort(rng.uniform(0, 100, size=5000))
    q = rng.uniform(-5, 105, size=500)  # includes out-of-range queries
    np.testing.assert_array_equal(_nearest_sorted_index(tv, q), _brute_nn(tv, q))


def test_nearest_sorted_index_tie_breaks_low():
    tv = np.array([0.0, 1.0, 2.0])
    # 0.5 is exactly between indices 0 and 1 -> lower index wins (argmin behavior).
    assert _nearest_sorted_index(tv, np.array([0.5])) == np.array([0])


def test_nearest_sorted_index_single_and_empty():
    assert _nearest_sorted_index(np.array([3.0]), np.array([1.0, 9.0])).tolist() == [0, 0]
    assert _nearest_sorted_index(np.array([]), np.array([1.0])).shape == (0,)


# ---------------------------------------------------------------------------
# find_ephys_idx_of_TTL_events
# ---------------------------------------------------------------------------


def test_all_ttl_matches_brute_and_old_loop():
    fs, fr = 1000.0, 30.0
    time_vector = np.arange(0, 60, 1 / fs)
    rng = np.random.default_rng(2)
    # gap-free ~30 Hz frame times with sub-frame jitter, kept in range.
    tCaIm = np.arange(0.01, 59.0, 1 / fr) + rng.uniform(-0.002, 0.002, size=len(np.arange(0.01, 59.0, 1 / fr)))
    tCaIm = np.clip(np.sort(tCaIm), time_vector[0], time_vector[-1])
    ch = _make_channel(time_vector, fs)

    new_idx, _ = find_ephys_idx_of_TTL_events(tCaIm, ch, fr, all_TTL_events=True)

    np.testing.assert_array_equal(new_idx, _brute_nn(time_vector, tCaIm))
    np.testing.assert_array_equal(new_idx, _old_all_ttl_loop(tCaIm, time_vector, fs, fr))


def test_ca_events_branch_matches_brute():
    fs, fr = 1000.0, 30.0
    time_vector = np.arange(0, 60, 1 / fs)
    tCaIm = np.arange(0.01, 59.0, 1 / fr)
    ch = _make_channel(time_vector, fs)
    ca_events_idx = {
        0: np.array([5, 100, 500, 1200]),
        7: np.array([10, 250, 900]),
    }

    _, ca_res = find_ephys_idx_of_TTL_events(tCaIm, ch, fr, ca_events_idx=ca_events_idx, all_TTL_events=False)

    assert set(ca_res.keys()) == {0, 7}
    for unit, idx in ca_events_idx.items():
        np.testing.assert_array_equal(ca_res[unit], _brute_nn(time_vector, tCaIm[idx]))


def test_all_ttl_disabled_returns_none():
    time_vector = np.arange(0, 10, 0.001)
    ch = _make_channel(time_vector, 1000.0)
    all_idx, ca_res = find_ephys_idx_of_TTL_events(np.array([1.0, 2.0]), ch, 30.0, all_TTL_events=False)
    assert all_idx is None
    assert ca_res is None
