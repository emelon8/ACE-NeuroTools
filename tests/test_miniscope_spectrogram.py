"""Regression coverage for the plotting-switch/function collision in #109."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import numpy as np
import pytest

from aceneurotools.shared import plotting


@pytest.fixture
def spectrogram_module(monkeypatch):
    # Load the real module, including its plotting import, without requiring
    # CaImAn or a GUI. These dependencies are unused by the static method.
    caiman = ModuleType("caiman")
    caiman.movie = np.ndarray
    gui = ModuleType("aceneurotools.miniscope.gui_utils")
    gui.component_gui = Mock()
    monkeypatch.setitem(sys.modules, "caiman", caiman)
    monkeypatch.setitem(sys.modules, gui.__name__, gui)
    draw = Mock(return_value=(None, None))
    monkeypatch.setattr(plotting, "plot_spectrogram", draw)

    path = Path(__file__).resolve().parents[1] / "src/aceneurotools/miniscope/miniscope_postprocessor.py"
    # A private module instance keeps stubbed dependencies out of other tests.
    spec = importlib.util.spec_from_file_location("_spectrogram_regression", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, draw


@pytest.mark.parametrize(
    "plot_options",
    [{}, {"plot_spectrogram": True}, {"plot_spectrogram": False}],
    ids=["default", "enabled", "disabled"],
)
def test_spectrogram_plotting_switch(spectrogram_module, monkeypatch, plot_options):
    module, draw = spectrogram_module
    data = np.ones(120)
    psd = np.array([[1.0, 10.0], [100.0, 1000.0]])
    times = np.array([60.0, 120.0])
    frequencies = np.array([1.0, 2.0])
    expected_db = np.array([[0.0, 10.0], [20.0, 30.0]])
    # Stub only the expensive transform; dispatch, array conversion, and the
    # return path all execute the production method.
    transform = Mock(return_value=(psd, times, frequencies))
    monkeypatch.setattr(module, "multitaper_spectrogram", transform)

    result = module.MiniscopePostprocessor.compute_miniscope_spectrogram(data, 30, **plot_options)

    transform.assert_called_once()
    assert transform.call_args.args[0] is data
    assert len(result) == 4
    assert result[0] is psd
    assert result[1] is times
    assert result[2] is frequencies
    np.testing.assert_array_equal(result[3], expected_db)
    if plot_options.get("plot_spectrogram", True):
        draw.assert_called_once()
        plot_times, plot_frequencies, plot_db = draw.call_args.args
        np.testing.assert_array_equal(plot_times, [1.0, 2.0])
        assert plot_frequencies is frequencies
        np.testing.assert_array_equal(plot_db, expected_db)
        assert draw.call_args.kwargs == {"xLabel": "Time (min)"}
    else:
        draw.assert_not_called()
