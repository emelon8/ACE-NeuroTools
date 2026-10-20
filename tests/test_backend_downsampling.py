"""Downsampling changes every sample-aligned field atomically."""
from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.ephys.channel import Channel
from aceneurotools.multimodal import stats_loader as loader


def channels():
    result = [Channel(name, np.arange(20.0) + i, 10, 100 + np.arange(20) / 10, {}) for i, name in enumerate(['one', 'two'])]
    for channel in result:
        channel.signal_filtered = 2 * channel.signal
        channel.phases = channel.signal / 20
    return result


def test_downsampling_preserves_all_sample_fields():
    selected = channels()
    originals = [{name: getattr(channel, name).copy() for name in ('signal', 'time_vector', 'signal_filtered', 'phases')} for channel in selected]
    indices = np.array([0, 5, 10, 15])
    loader._downsample_channels(selected, indices, 2)
    for channel, original in zip(selected, originals):
        assert channel.sampling_rate == 2
        for name, values in original.items():
            np.testing.assert_array_equal(getattr(channel, name), values[indices])


@pytest.mark.parametrize('bad_field', ['time_vector', 'signal_filtered', 'phases'])
def test_invalid_paired_fields_do_not_partially_modify_channels(bad_field):
    selected = channels()
    if bad_field == 'time_vector':
        selected[1].time_vector += 1
    else:
        setattr(selected[1], bad_field, np.arange(3))
    before = selected[0].signal.copy()
    with pytest.raises(ValueError):
        loader._downsample_channels(selected, np.array([0, 5, 10]), 2)
    np.testing.assert_array_equal(selected[0].signal, before)
    assert selected[0].sampling_rate == 10


@pytest.mark.parametrize('paired', [False, True])
def test_public_loaders_use_shared_downsampling(monkeypatch, tmp_path, paired):
    selected = channels()
    monkeypatch.setattr(loader.CalciumImagingDataManager, 'create', lambda **kw: SimpleNamespace(fr=2))
    monkeypatch.setattr(loader, 'load_ephys_for_analysis', lambda **kw: SimpleNamespace(get_channel=lambda name: selected[name == 'two']))
    monkeypatch.setattr(loader, 'sync_neuralynx_miniscope_timestamps', lambda ch, dm, ep, **kw: (np.array([100, 100.5, 101]), [], ch, dm))
    monkeypatch.setattr(loader, 'find_ephys_idx_of_TTL_events', lambda *args, **kw: (np.array([0, 5, 10]), None))
    if paired:
        loader.load_for_stats_two_channels(7, tmp_path, channel_name_1='one', channel_name_2='two')
    else:
        loader.load_for_stats(7, tmp_path, channel_name='one')
    for channel in selected[:2 if paired else 1]:
        assert len(channel.signal) == len(channel.time_vector) == len(channel.phases) == len(channel.signal_filtered) == 3
        assert channel.sampling_rate == 2
