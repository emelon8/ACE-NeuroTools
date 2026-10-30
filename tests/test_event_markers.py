"""Spectrograms display every supplied event without changing axis limits."""

import matplotlib.pyplot as plt
import numpy as np
import pytest

from aceneurotools.ephys.visualizer import Visualizer


@pytest.mark.parametrize("count", [0, 10, 12, 25])
def test_spectrogram_draws_all_event_markers(monkeypatch, count):
    monkeypatch.setattr(plt, "show", lambda: None)
    labels = [f"Event {index}" for index in range(count)]
    timestamps = list(range(count))
    figure, axes = Visualizer().plot_spectrogram_helper(
        np.ones((4, 30)),
        np.arange(30) * 60,
        np.arange(1, 5),
        events={"labels": labels, "timestamps": timestamps},
    )
    try:
        assert [line.get_xdata()[0] for line in axes.lines] == timestamps
        assert [text.get_text() for text in axes.texts] == labels
        assert axes.get_xlim() == (0.0, 29.0)
    finally:
        plt.close(figure)


@pytest.mark.parametrize("events", [{"labels": ["A"]}, {"timestamps": [1]}])
def test_spectrogram_ignores_incomplete_event_metadata(monkeypatch, events):
    monkeypatch.setattr(plt, "show", lambda: None)
    figure, axes = Visualizer().plot_spectrogram_helper(
        np.ones((4, 30)),
        np.arange(30) * 60,
        np.arange(1, 5),
        events=events,
    )
    try:
        assert not axes.lines
        assert not axes.texts
    finally:
        plt.close(figure)
