"""Regression tests for miniscope projection filtering.

Guards the fix for the no-op ``filter_object.filter_miniscope_data`` (missing
parentheses) in the post-processor: filtering must actually run and, with
``inline=True``, replace ``projections.time`` with a real filtered array rather
than an empty list.
"""

from __future__ import annotations

import types

import numpy as np
import pytest

from aceneurotools.miniscope.filtered_miniscope_data import FilterMiniscopeData
from aceneurotools.miniscope.projections import Projections


def _projections_with_time(time: np.ndarray) -> Projections:
    zero = np.zeros((2, 2))
    return Projections(zero, zero, zero, zero, zero, zero, time)


def _bandpass_test_signal(fs: float = 30.0, n: int = 600) -> np.ndarray:
    t = np.arange(n) / fs
    # 0.5 Hz component is in [0.1, 1.5] band; 5 Hz component is out of band.
    return np.sin(2 * np.pi * 0.5 * t) + 0.5 * np.sin(2 * np.pi * 5.0 * t)


def test_filter_miniscope_data_populates_filtered_data():
    sig = _bandpass_test_signal()
    fobj = FilterMiniscopeData(
        _projections_with_time(sig), frame_rate=30.0, cut=[0.1, 1.5], btype="bandpass"
    )
    assert fobj.filtered_data == []  # not filtered yet

    fobj.filter_miniscope_data()

    assert isinstance(fobj.filtered_data, np.ndarray)
    assert fobj.filtered_data.shape == sig.shape
    # A real bandpass changes the signal (attenuates the 5 Hz component).
    assert not np.allclose(fobj.filtered_data, sig)


def test_postprocessor_filter_branch_replaces_time_inline():
    """The post-processor's filter branch must run the filter and, inline,
    replace projections.time with a real ndarray (not the buggy empty list)."""
    pytest.importorskip("caiman")
    from aceneurotools.miniscope.miniscope_postprocessor import MiniscopePostprocessor

    rng = np.random.default_rng(0)
    n_frames = 400
    movie = rng.random((n_frames, 4, 4)).astype(np.float32)
    dm = types.SimpleNamespace(
        movie=movie,
        fr=30.0,
        dview=None,
        projections=None,
        CNMFE_obj=None,
        ca_events_idx=None,
        PSD_spect=None,
        t_spect=None,
        freqs_spect=None,
        p_spect=None,
        miniscope_phases=None,
        filter_object=None,
    )

    post = MiniscopePostprocessor(dm)  # computes projections from the movie
    original_len = dm.projections.time.shape[0]

    post.postprocess_calcium_movie(
        remove_components_with_gui=False,
        find_calcium_events=False,
        compute_miniscope_phase=False,
        compute_miniscope_spectrogram=False,
        filter_miniscope_data=True,
        inline=True,
        cut=[0.1, 1.5],
    )

    assert isinstance(dm.filter_object.filtered_data, np.ndarray)
    assert dm.filter_object.filtered_data.shape[0] == original_len
    # With the bug this would be an empty list; after the fix it is a real array.
    assert isinstance(dm.projections.time, np.ndarray)
    assert dm.projections.time.shape[0] == original_len
