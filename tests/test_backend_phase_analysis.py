"""Phase/event relationships checked against analytic phases and probability mass."""

from __future__ import annotations

from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy.signal import hilbert

from aceneurotools.multimodal.phase_utils import (
    ephys_phase_ca_events,
    miniscope_phase_ca_events,
    phase_ca_events_histogram,
)


@pytest.fixture(autouse=True)
def close_figures():
    yield
    plt.close("all")


@pytest.mark.parametrize("selection,units", [("all", [0, 9]), ([9], [9]), (9, [9]), ("9", [9])])
def test_phase_events_match_analytic_tone_and_selected_units(selection, units):
    time = np.arange(512) / 64
    phases = np.angle(hilbert(np.cos(2 * np.pi * 4 * time)))
    events = {0: np.array([0, 16, 32]), 9: np.array([4, 12, 44])}
    channel = SimpleNamespace(name="EEG", phases=phases)
    before = phases.copy()
    ephys = ephys_phase_ca_events(events, channel, selection)
    calcium = miniscope_phase_ca_events(events, phases, selection)
    assert list(ephys) == list(calcium) == units
    for unit in units:
        expected = np.exp(2j * np.pi * 4 * time[events[unit]])
        np.testing.assert_allclose(np.exp(1j * ephys[unit]), expected, atol=1e-12)
        np.testing.assert_array_equal(calcium[unit], ephys[unit])
    np.testing.assert_array_equal(phases, before)


@pytest.mark.parametrize("indices", [[-1], [10], [1.5], [True]])
def test_phase_mapping_rejects_invalid_event_indices(indices):
    with pytest.raises(ValueError, match="indices"):
        miniscope_phase_ca_events({0: np.array(indices)}, np.arange(10.0))
    with pytest.raises(ValueError, match="indices"):
        ephys_phase_ca_events({0: np.array(indices)}, SimpleNamespace(name="EEG", phases=np.arange(10.0)))


def test_phase_mapping_requires_computed_phases_and_handles_no_events():
    with pytest.raises(ValueError, match="not been calculated"):
        ephys_phase_ca_events({0: np.array([1])}, SimpleNamespace(name="EEG", phases=None))
    assert miniscope_phase_ca_events({}, np.arange(10.0)) == {}
    assert miniscope_phase_ca_events({0: np.array([])}, np.arange(10.0))[0].size == 0


@pytest.fixture
def phase_events():
    return {0: np.array([-np.pi, -np.pi / 2, 0, np.pi / 2, np.pi]), 9: np.array([0.1, 0.2, 0.3])}


@pytest.mark.parametrize("plot", [False, True])
@pytest.mark.parametrize("selection", ["all", [9], 9])
@pytest.mark.parametrize("density", [False, True])
def test_pooled_phase_histogram_matches_counts_and_unit_probability(phase_events, plot, selection, density):
    units = list(phase_events) if selection == "all" else [9]
    values = np.concatenate([phase_events[unit] for unit in units])
    expected, edges = np.histogram(values, bins=4, range=(-np.pi, np.pi), density=density)
    histogram, actual_edges = phase_ca_events_histogram(
        phase_events, selection, bins=4, density=density, plot_histogram=plot
    )
    # Matplotlib's legacy stacked-density result is cumulative; its last row
    # must equal the pooled density returned by the headless API.
    pooled = np.asarray(histogram).reshape(-1, 4)[-1]
    np.testing.assert_allclose(pooled, expected)
    np.testing.assert_array_equal(actual_edges, edges)
    if density:
        assert np.sum(pooled * np.diff(edges)) == pytest.approx(1)
    else:
        assert pooled.sum() == values.size


@pytest.mark.parametrize("plot", [False, True])
@pytest.mark.parametrize("selection", ["all", [9]])
@pytest.mark.parametrize("density", [False, True])
def test_individual_neuron_histograms_preserve_unequal_event_counts(phase_events, plot, selection, density):
    histograms, edges = phase_ca_events_histogram(
        phase_events, selection, bins=4, density=density, combined=False, plot_histogram=plot
    )
    units = [0, 9] if selection == "all" else [9]
    assert list(histograms) == units
    for unit in units:
        expected, expected_edges = np.histogram(phase_events[unit], bins=4, range=(-np.pi, np.pi), density=density)
        np.testing.assert_allclose(histograms[unit], expected)
        np.testing.assert_array_equal(edges[unit], expected_edges)


@pytest.mark.parametrize("plot", [False, True])
def test_mean_density_weights_neurons_equally_and_respects_circular_wrap(plot):
    values = {0: np.array([np.pi - 0.1]), 1: np.repeat(-np.pi + 0.1, 9)}
    hist, edges, theta, radius = phase_ca_events_histogram(values, bins=8, mean_density=True, plot_histogram=plot)
    first, _ = np.histogram(values[0], bins=8, range=(-np.pi, np.pi), density=True)
    second, _ = np.histogram(values[1], bins=8, range=(-np.pi, np.pi), density=True)
    np.testing.assert_allclose(hist, (first + second) / 2)
    assert np.sum(hist * np.diff(edges)) == pytest.approx(1)
    assert abs(theta) == pytest.approx(np.pi)
    assert radius == pytest.approx(np.cos(0.1))


def test_mean_density_selected_neurons_and_empty_neurons_are_explicit():
    values = {0: np.array([]), 9: np.repeat(0.0, 5), 10: np.repeat(np.pi / 2, 2)}
    hist, edges, theta, radius = phase_ca_events_histogram(
        values, [0, 9], bins=4, mean_density=True, plot_histogram=False
    )
    expected, _ = np.histogram(values[9], bins=4, range=(-np.pi, np.pi), density=True)
    np.testing.assert_allclose(hist, expected)
    assert theta == pytest.approx(0) and radius == pytest.approx(1)
    result = phase_ca_events_histogram({0: np.array([])}, bins=4, mean_density=True, plot_histogram=False)
    assert np.isnan(result[0]).all() and np.isnan(result[2]) and np.isnan(result[3])


@pytest.mark.parametrize("bad", [np.array([np.nan]), np.array([np.inf])])
def test_histogram_rejects_nonfinite_phases_instead_of_losing_events(bad):
    with pytest.raises(ValueError, match="finite"):
        phase_ca_events_histogram({0: bad}, plot_histogram=False)


def test_histogram_does_not_modify_inputs(phase_events):
    before = {unit: values.copy() for unit, values in phase_events.items()}
    phase_ca_events_histogram(phase_events, density=True, plot_histogram=False)
    for unit, values in phase_events.items():
        np.testing.assert_array_equal(values, before[unit])
