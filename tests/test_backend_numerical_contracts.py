"""Independent numerical oracles and outliers for the backend scientific APIs."""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from aceneurotools.multimodal.alignment import _nearest_sorted_index, find_ephys_idx_of_TTL_events
from aceneurotools.stats.event_correlograms import _cross_correlogram
from aceneurotools.stats.perievent import compute_event_triggered_average, compute_perievent
from aceneurotools.stats.surrogate import (
    jitter_event_times,
    permutation_test,
    shift_event_times,
    shuffle_event_intervals,
)


@pytest.mark.parametrize("fs", [0, -1, float("nan"), float("inf")])
def test_perievent_rejects_invalid_sampling_rate(fs):
    with pytest.raises(ValueError, match="fs"):
        compute_perievent(np.arange(10.0), np.array([1.0]), fs, 1)


@pytest.mark.parametrize("window", [float("nan"), float("inf"), (0, float("inf")), (float("nan"), 1)])
def test_perievent_rejects_nonfinite_window(window):
    with pytest.raises(ValueError, match="[Ww]indow"):
        compute_perievent(np.arange(10.0), np.array([1.0]), 1, window)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_perievent_rejects_nonfinite_events_and_clock_origin(bad):
    with pytest.raises(ValueError, match="event_times"):
        compute_perievent(np.arange(10.0), np.array([bad]), 1, 1)
    with pytest.raises(ValueError, match="t_start"):
        compute_perievent(np.arange(10.0), np.array([1.0]), 1, 1, t_start=bad)


@pytest.mark.parametrize("events", [[-100, 100], [-1e100, 1e100], [0, 4], [2, 2]])
@pytest.mark.parametrize("drop", [True, False])
def test_perievent_outliers_match_sample_by_sample_oracle(events, drop):
    signal = np.arange(5.0)
    before = signal.copy()
    with np.errstate(all="raise"):
        result = compute_perievent(signal, np.array(events), fs=1, window=(1, 2), drop_boundary_events=drop)
    expected = []
    kept = []
    for event in events:
        indices = [int(event) + offset for offset in (-1, 0, 1, 2)]
        if drop and any(index < 0 or index >= signal.size for index in indices):
            continue
        expected.append([signal[index] if 0 <= index < signal.size else np.nan for index in indices])
        kept.append(event)
    np.testing.assert_equal(result["matrix"], np.array(expected).reshape(-1, 4))
    np.testing.assert_equal(result["event_times"], kept)
    np.testing.assert_array_equal(signal, before)


def test_eta_sem_uses_contributing_count_for_each_padded_sample():
    signal = np.arange(10.0)
    result = compute_event_triggered_average(signal, np.array([0.0, 1.0, 5.0]), 1, 1, drop_boundary_events=False)
    # Before-event column: only events at 1 and 5 contribute values [0, 4].
    assert result["mean"][0] == 2
    assert result["std"][0] == pytest.approx(np.sqrt(8))
    assert result["sem"][0] == pytest.approx(2)
    assert result["sem"][1] == pytest.approx(np.std([0, 1, 5], ddof=1) / np.sqrt(3))


def test_eta_without_any_available_samples_is_explicitly_nan():
    result = compute_event_triggered_average(np.arange(5.0), np.array([-100.0]), 1, 1, drop_boundary_events=False)
    assert np.isnan(result["mean"]).all()
    assert np.isnan(result["std"]).all()
    assert np.isnan(result["sem"]).all()


@settings(deadline=None)
@given(
    samples=st.lists(st.integers(-100, 100), min_size=1, max_size=40).map(sorted),
    queries=st.lists(st.integers(-200, 200), max_size=30),
)
def test_nearest_timestamp_matches_brute_force_including_duplicates(samples, queries):
    values, query = np.array(samples, dtype=float), np.array(queries, dtype=float)
    expected = np.array([np.abs(values - q).argmin() for q in query], dtype=int)
    np.testing.assert_array_equal(_nearest_sorted_index(values, query), expected)


@pytest.mark.parametrize("values, query", [([2, 1], [1]), ([0, float("nan")], [1]), ([0, 1], [float("inf")])])
def test_alignment_rejects_invalid_clocks(values, query):
    with pytest.raises(ValueError):
        _nearest_sorted_index(np.array(values), np.array(query))


@pytest.mark.parametrize("bad_indices", [[-1], [3], [1.5]])
def test_alignment_cannot_wrap_or_truncate_bad_frame_indices(bad_indices):
    from types import SimpleNamespace

    channel = SimpleNamespace(time_vector=np.arange(10.0))
    with pytest.raises(ValueError, match="frame"):
        find_ephys_idx_of_TTL_events(np.array([1.0, 2.0, 3.0]), channel, 30, ca_events_idx={7: np.array(bad_indices)})


@settings(deadline=None)
@given(
    references=st.lists(st.integers(-10, 10), max_size=15).map(sorted),
    targets=st.lists(st.integers(-10, 10), max_size=15).map(sorted),
)
def test_correlogram_matches_pairwise_counting_oracle(references, targets):
    # Exactly representable bin edges avoid accidental float-boundary assertions.
    counts, centers = _cross_correlogram(np.array(references), np.array(targets), binsize=2, windowsize=4)
    expected = np.zeros(5)
    for reference in references:
        for target in targets:
            lag = target - reference
            if -5 <= lag < 5:  # left inclusive, right exclusive
                expected[(lag + 5) // 2] += 1
    if references:
        expected /= 2 * len(references)
    np.testing.assert_array_equal(counts, expected)
    np.testing.assert_array_equal(centers, [-4, -2, 0, 2, 4])


@pytest.mark.parametrize("alternative", ["two-sided", "less", "greater"])
def test_permutation_p_value_matches_manual_count_including_ties(alternative):
    null = [-2, -1, 0, 1, 2]
    draws = iter(null)
    result = permutation_test(1, lambda rng: next(draws), n_surrogates=5, alternative=alternative)
    count = {"two-sided": 4, "greater": 2, "less": 4}[alternative]
    assert result.p_value == (1 + count) / 6
    np.testing.assert_array_equal(result.null_distribution, null)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_permutation_rejects_invalid_observed_or_null_statistics(bad):
    with pytest.raises(ValueError, match="finite"):
        permutation_test(bad, lambda rng: 0, n_surrogates=2)
    with pytest.raises(ValueError, match="finite"):
        permutation_test(0, lambda rng: bad, n_surrogates=2)


def test_permutation_is_reproducible_and_p_value_never_zero():
    one = permutation_test(1e6, lambda rng: rng.normal(), 30, rng=np.random.default_rng(734))
    two = permutation_test(1e6, lambda rng: rng.normal(), 30, rng=np.random.default_rng(734))
    np.testing.assert_array_equal(one.null_distribution, two.null_distribution)
    assert one.p_value == two.p_value == 1 / 31


@settings(deadline=None)
@given(events=st.lists(st.integers(0, 100), max_size=30).map(sorted))
def test_surrogates_preserve_their_documented_invariants(events):
    original = np.array(events, dtype=float)
    before = original.copy()
    first = jitter_event_times(original, 0.25, rng=np.random.default_rng(71))
    second = jitter_event_times(original, 0.25, rng=np.random.default_rng(71))
    np.testing.assert_array_equal(first, second)
    assert first.size == original.size
    assert np.all(np.diff(first) >= 0)
    assert np.all(np.abs(first - original) <= 0.25)
    wrapped = shift_event_times(original, 0, 101, mode="wrap", rng=np.random.default_rng(8))
    assert wrapped.size == original.size
    assert np.all((wrapped >= 0) & (wrapped < 101))
    shuffled = shuffle_event_intervals(original, rng=np.random.default_rng(8))
    np.testing.assert_array_equal(np.sort(np.diff(shuffled)), np.sort(np.diff(original)))
    np.testing.assert_array_equal(original, before)


@pytest.mark.parametrize("start,end", [(float("nan"), 1), (0, float("inf")), (-float("inf"), 1)])
def test_surrogate_time_support_must_be_finite(start, end):
    with pytest.raises(ValueError, match="finite"):
        shift_event_times(np.array([0.5]), start, end, rng=np.random.default_rng(1))
