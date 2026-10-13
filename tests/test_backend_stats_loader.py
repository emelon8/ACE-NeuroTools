"""Real TTL indexing and archive loading with synthetic recording adapters."""

from __future__ import annotations

import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.ephys.channel import Channel
from aceneurotools.shared.exceptions import PipelineExecutionError
from aceneurotools.stats import loader


@pytest.fixture
def recording(monkeypatch):
    clock = 100 + np.arange(20) / 10
    channels = {
        name: Channel(name, np.arange(20.0) + offset, 10, clock.copy(), {})
        for name, offset in [("one", 0), ("two", 100)]
    }
    for channel in channels.values():
        channel.signal_filtered = channel.signal * 2
        channel.phases = channel.signal / 20
    metadata = SimpleNamespace(fr=2.0)
    ephys = SimpleNamespace(get_channel=channels.__getitem__)
    calls = {}

    def open_metadata(**kwargs):
        calls["metadata"] = kwargs
        return metadata

    def open_ephys(**kwargs):
        calls["ephys"] = kwargs
        return ephys

    def synchronize(channel, dm, recording_dm, **kwargs):
        calls["sync"] = kwargs
        assert dm is metadata and recording_dm is ephys
        return np.array([100.01, 100.51, 101.01, 101.51]), [], channel, dm

    monkeypatch.setattr(loader, "_metadata_only_manager", open_metadata)
    monkeypatch.setattr(loader, "load_ephys_for_analysis", open_ephys)
    monkeypatch.setattr(loader, "sync_neuralynx_miniscope_timestamps", synchronize)
    return channels, metadata, calls


@pytest.mark.parametrize("paired", [False, True])
def test_loading_preserves_sample_alignment_for_every_channel_field(recording, tmp_path, paired):
    channels, metadata, calls = recording
    original = {
        name: {
            field: getattr(channel, field).copy() for field in ("signal", "time_vector", "signal_filtered", "phases")
        }
        for name, channel in channels.items()
    }
    if paired:
        result = loader.load_for_stats_two_channels(
            7,
            tmp_path,
            channel_name_1="one",
            channel_name_2="two",
            delete_TTLs=False,
            fix_TTL_gaps=False,
            only_experiment_events=False,
        )
        selected = result[:2]
        assert calls["ephys"]["channel_names"] == ["one", "two"]
    else:
        result = loader.load_for_stats(
            7, tmp_path, channel_name="one", delete_TTLs=False, fix_TTL_gaps=False, only_experiment_events=False
        )
        selected = result[:1]
    assert result[-2] is metadata and result[-1] == 2
    assert calls["metadata"]["auto_import_data"] is False and calls["metadata"]["filenames"] == []
    assert calls["sync"] == dict(delete_TTLs=False, fix_TTL_gaps=False, only_experiment_events=False)
    for channel in selected:
        for field, before in original[channel.name].items():
            np.testing.assert_array_equal(getattr(channel, field), before[[0, 5, 10, 15]])
        assert channel.sampling_rate == 2


@pytest.mark.parametrize("paired", [False, True])
@pytest.mark.parametrize(
    "dependency,stage",
    [
        ("_metadata_only_manager", "miniscope_dm"),
        ("load_ephys_for_analysis", "ephys"),
        ("sync_neuralynx_miniscope_timestamps", "ttl_sync"),
        ("find_ephys_idx_of_TTL_events", "downsample"),
    ],
)
def test_loader_errors_identify_stage_and_preserve_original_cause(
    recording, monkeypatch, tmp_path, paired, dependency, stage
):
    cause = OSError("synthetic recording error")

    def fail(*args, **kwargs):
        raise cause

    monkeypatch.setattr(loader, dependency, fail)
    with pytest.raises(PipelineExecutionError) as caught:
        if paired:
            loader.load_for_stats_two_channels(7, tmp_path, channel_name_1="one", channel_name_2="two")
        else:
            loader.load_for_stats(7, tmp_path, channel_name="one")
    expected = "ephys_pipeline" if stage == "ephys" and not paired else stage
    prefix = "stats_loader_two_ch_" if paired else "stats_loader_"
    assert caught.value.context.stage == prefix + expected
    assert caught.value.context.line_num == 7 and caught.value.__cause__ is cause


@pytest.mark.parametrize("rate", [None, 0])
def test_legacy_missing_frame_rate_retains_thirty_hz_fallback(recording, tmp_path, rate):
    recording[1].fr = rate
    _, _, fr = loader.load_for_stats(7, tmp_path, channel_name="one")
    assert fr == 30


@pytest.mark.parametrize("rate", [True, -2, np.nan, np.inf])
def test_invalid_frame_rate_does_not_create_an_invalid_analysis(recording, tmp_path, rate):
    recording[1].fr = rate
    with pytest.raises(PipelineExecutionError, match="MiniscopeDataManager"):
        loader.load_for_stats(7, tmp_path, channel_name="one")


def test_mismatched_paired_clock_fails_without_partially_downsampling(recording, tmp_path):
    channels, _, _ = recording
    channels["two"].time_vector += 1
    with pytest.raises(PipelineExecutionError, match="downsampling"):
        loader.load_for_stats_two_channels(7, tmp_path, channel_name_1="one", channel_name_2="two")
    assert channels["one"].signal.size == channels["two"].signal.size == 20


def test_archive_values_remain_available_after_the_file_is_closed(tmp_path, monkeypatch):
    source = np.arange(20.0)
    path = tmp_path / "meanFluorescence_7.npz"
    np.savez(path, meanFluorescence=source, frame_count=20)
    opened = []
    real_load = np.load

    def track_load(*args, **kwargs):
        archive = real_load(*args, **kwargs)
        opened.append(archive)
        return archive

    monkeypatch.setattr(loader.np, "load", track_load)
    dm = SimpleNamespace()
    actual = loader.load_calcium_signal(dm, tmp_path, 7)
    np.testing.assert_array_equal(actual, source)
    np.testing.assert_array_equal(dm.mean_fluorescence_dict["meanFluorescence"], source)
    assert dm.mean_fluorescence_dict["frame_count"] == 20
    assert opened[0].zip is None


def test_absent_archive_or_key_has_explicit_warning_and_no_state_change(tmp_path):
    dm = SimpleNamespace(mean_fluorescence_dict={"previous": 1})
    with pytest.warns(UserWarning, match="not found"):
        assert loader.load_calcium_signal(dm, tmp_path, 7) is None
    np.savez(tmp_path / "meanFluorescence_7.npz", other=np.ones(3))
    with pytest.warns(UserWarning, match="Available keys"):
        assert loader.load_calcium_signal(dm, tmp_path, 7) is None
    assert dm.mean_fluorescence_dict == {"previous": 1}


@pytest.mark.parametrize("values", [np.ones((2, 3)), np.array(["text"]), np.array([{"unsafe": True}], dtype=object)])
def test_archive_rejects_non_numeric_or_non_vector_signals(tmp_path, values):
    np.savez(tmp_path / "meanFluorescence_7.npz", meanFluorescence=values)
    with pytest.raises(ValueError):
        loader.load_calcium_signal(SimpleNamespace(), tmp_path, 7)


def test_statistics_public_pipeline_import_does_not_require_movie_stack():
    code = """
import sys
class RejectMovieStack:
    def find_spec(self, fullname, *args):
        if fullname == 'caiman' or fullname.startswith('caiman.'):
            raise AssertionError('statistics imported CaImAn')
sys.meta_path.insert(0, RejectMovieStack())
import aceneurotools.pipelines as api
from aceneurotools.pipelines import StatsPipeline, EphysPipeline
from aceneurotools.pipelines.stats import StatsPipeline as direct
assert StatsPipeline is direct
assert set(api.__all__) <= set(dir(api))
try:
    api.unknown_pipeline
except AttributeError:
    pass
else:
    raise AssertionError('missing attribute did not raise')
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
