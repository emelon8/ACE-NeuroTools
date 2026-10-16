import numpy as np
import pytest

from aceneurotools.multimodal.perievent import compute_event_triggered_average, compute_perievent


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


