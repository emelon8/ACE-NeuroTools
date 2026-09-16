"""Verify that the legacy spike_trig_avg still works but emits DeprecationWarning."""

from __future__ import annotations

import warnings

import numpy as np

from aceneurotools.stats.perievent import spike_trig_avg


def test_spike_trig_avg_emits_deprecation_warning():
    data = np.arange(100, dtype=float)
    events = np.array([[10], [20], [30]])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = spike_trig_avg(events, data, framesb=5, framesa=5)
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) >= 1
    assert "compute_event_triggered_average" in str(deprecations[0].message)
    # Still returns the legacy shape
    assert 0 in result
    assert result[0].shape == (11,)


def test_spike_trig_avg_legacy_behavior_unchanged_1d():
    data = np.arange(100, dtype=float)
    events = np.array([[10], [50]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        out = spike_trig_avg(events, data, framesb=2, framesa=2)
    # Average of windows [8..12] and [48..52] -> [28, 29, 30, 31, 32]
    expected = (np.array([8, 9, 10, 11, 12]) + np.array([48, 49, 50, 51, 52])) / 2.0
    np.testing.assert_allclose(out[0], expected)
