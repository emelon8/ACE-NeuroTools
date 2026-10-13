"""Review-only regression probes. Failures are expected on the reviewed revision.

Only synthetic data; no network calls, credentials, or lab recordings.
"""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import matplotlib.pyplot as plt
import numpy as np
import pytest


def test_109_plotting_spectrogram_does_not_call_boolean(monkeypatch):
    import aceneurotools.miniscope.miniscope_postprocessor as m

    monkeypatch.setattr(
        m, "multitaper_spectrogram", lambda *a: (np.ones((2, 2)), np.array([0.0, 1.0]), np.array([1.0, 2.0]))
    )
    m.MiniscopePostprocessor.compute_miniscope_spectrogram(np.ones(100), 30)


def test_109_control_without_plotting(monkeypatch):
    import aceneurotools.miniscope.miniscope_postprocessor as m

    monkeypatch.setattr(
        m, "multitaper_spectrogram", lambda *a: (np.ones((2, 2)), np.array([0.0, 1.0]), np.array([1.0, 2.0]))
    )
    result = m.MiniscopePostprocessor.compute_miniscope_spectrogram(np.ones(100), 30, plot_spectrogram=False)
    assert len(result) == 4


def test_112_explicit_missing_config_is_an_error(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "aceneurotools.cli", "--config", str(tmp_path / "missing.json")],
        capture_output=True,
        text=True,
    )
    print(f"CLI exit={result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}")
    assert result.returncode != 0, "Explicit nonexistent config silently exits successfully"


@pytest.mark.parametrize("under_artifacts", [False, True], ids=["raw_at_root", "control_under_artifacts"])
def test_114_raw_recording_not_in_revision(tmp_path, under_artifacts):
    from aceneurotools.evc.porcelain import ExperimentVersionControl

    exp = tmp_path / "experiment"
    exp.mkdir()
    evc = ExperimentVersionControl.init(exp, workspace=True)
    (exp / "parameters" / "params.json").write_text('{"example":true}')
    directory = exp / "artifacts" if under_artifacts else exp
    for extension in ("ncs", "nev", "tif", "npy"):
        (directory / f"recording.{extension}").write_bytes(b"synthetic recording placeholder")
    oid = evc.record("Synthetic evidence", author="Review Fixture <fixture@example.invalid>")
    files = evc.show(oid).files
    print(f"Snapshot paths: {list(files)}")
    assert not any("recording." in name for name in files), "Raw files entered the revision"


@pytest.mark.parametrize("event_count", [10, 12], ids=["control_ten", "twelve"])
def test_115_every_event_is_marked(event_count):
    from aceneurotools.ephys.visualizer import Visualizer

    fig, ax = plt.subplots(figsize=(9, 3))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 1)
    Visualizer()._mark_events(
        ax, {"labels": [f"E{i}" for i in range(1, event_count + 1)], "timestamps": list(range(1, event_count + 1))}
    )
    count = len(ax.lines)
    print(f"Input events={event_count}; plotted markers={count}")
    if event_count == 12:
        ax.set_title("Actual output: 12 supplied events, 10 markers drawn", pad=35)
        ax.set_xlabel("Time (synthetic units)")
        fig.tight_layout()
        fig.savefig(Path(__file__).with_name("event-markers.png"), dpi=140)
    plt.close(fig)
    assert count == event_count


@pytest.mark.parametrize("event", ["-CANCEL-", None], ids=["cancel", "close"])
def test_113_cancelling_crop_does_not_return_empty_movie(monkeypatch, event):
    import aceneurotools.miniscope.gui_utils as gui
    from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor

    class Window:
        def __getitem__(self, key):
            return NS(draw_rectangle=lambda *a, **k: None)

        def read(self, **kwargs):
            return event, {}

        def close(self):
            pass

    sg = NS(WINDOW_CLOSED=None, Window=lambda *a, **k: Window())
    for name in ("Text", "Graph", "Combo", "Button"):
        setattr(sg, name, lambda *a, **k: None)
    monkeypatch.setattr(gui, "sg", sg)
    monkeypatch.setattr(gui, "_update_image", lambda *a, **k: None)
    coords = gui.crop_gui(None, NS(max=np.ones((8, 10))), 8, 10)
    print(f"Returned crop: {coords}")
    movie, description = MiniscopePreprocessor.crop_movie(None, np.ones((2, 8, 10)), coords)
    print(f"Original shape=(2, 8, 10); returned shape={movie.shape}")
    assert movie.size > 0


def box_client(entries, download, list_items=None):
    return NS(
        folders=NS(get_folder_items=list_items or (lambda *a, **k: NS(entries=entries))),
        downloads=NS(download_file_to_output_stream=download),
    )


def test_box_retry_replaces_interrupted_file(tmp_path):
    from aceneurotools.shared.file_downloader import download_file

    destination = tmp_path / "recording"
    destination.mkdir()
    entry = NS(type="file", id="2", name="trace.ncs")

    def interrupted(file_id, output_stream):
        output_stream.write(b"PART")
        raise OSError("Synthetic interrupted transfer")

    first = download_file(box_client([entry], interrupted), "recording", 1, base_file_path=tmp_path)
    calls = []

    def complete(file_id, output_stream):
        calls.append(file_id)
        output_stream.write(b"COMPLETE")

    second = download_file(box_client([entry], complete), "recording", 1, base_file_path=tmp_path)
    content = (destination / "trace.ncs").read_bytes()
    print(f"First status={first}; retry status={second}; retry downloads={calls}; final bytes={content!r}")
    assert second and content == b"COMPLETE", "Retry reported success but retained truncated bytes"


def test_box_recursive_failure_reaches_caller(tmp_path):
    from aceneurotools.shared.file_downloader import download_file

    def items(folder_id, **kwargs):
        if folder_id == "1":
            return NS(entries=[NS(type="folder", name="child", id="2")])
        raise OSError("Synthetic child listing failure")

    result = download_file(box_client([], None, items), "recording", 1, base_file_path=tmp_path)
    print(f"Root status after failed child={result}")
    assert result is False


def test_box_folder_listing_consumes_second_page(tmp_path):
    from aceneurotools.shared.file_downloader import download_file

    (tmp_path / "recording").mkdir()
    pages = []

    def items(folder_id, **kwargs):
        pages.append(kwargs)
        second = kwargs.get("marker") == "page2" or kwargs.get("offset", 0) > 0
        return NS(
            entries=[NS(type="file", name="second.ncs" if second else "first.ncs", id="3" if second else "2")],
            next_marker=None if second else "page2",
            total_count=2,
            offset=1 if second else 0,
            limit=1,
        )

    client = box_client([], lambda file_id, output_stream: output_stream.write(b"fixture"), items)
    result = download_file(client, "recording", 1, base_file_path=tmp_path)
    names = sorted(p.name for p in (tmp_path / "recording").iterdir())
    print(f"Status={result}; listing calls={pages}; downloaded files={names}")
    assert names == ["first.ncs", "second.ncs"]


def synthetic_loader(monkeypatch):
    """Use the real stats loader; replace disk readers and TTL alignment only."""
    import aceneurotools.pipelines.stats as pipeline
    import aceneurotools.stats.loader as loader

    rate = 100.0
    t = np.arange(12000) / rate
    signal = np.sin(2 * np.pi * 2 * t) + np.sin(2 * np.pi * 20 * t)
    channel = NS(signal=signal.copy())
    dm = NS(fr=rate)
    calls = []

    def load_ephys(**kwargs):
        calls.append(kwargs)
        return NS(get_channel=lambda name: channel)

    monkeypatch.setattr(loader.MiniscopeDataManager, "create", lambda **k: dm)
    monkeypatch.setattr(loader, "load_ephys_for_analysis", load_ephys)
    monkeypatch.setattr(loader, "sync_neuralynx_miniscope_timestamps", lambda *a, **k: (t, None, channel, dm))
    monkeypatch.setattr(loader, "find_ephys_idx_of_TTL_events", lambda *a, **k: (np.arange(len(t)), None))
    monkeypatch.setattr(pipeline, "load_calcium_signal", lambda *a, **k: signal.copy())
    return calls


@pytest.mark.parametrize(
    "explicit_band,config_band",
    [([10.0, 30.0], [0.5, 4.0]), (None, [0.5, 4.0]), ([10.0, 30.0], [10.0, 30.0])],
    ids=["override", "control_defaults", "control_matching_config"],
)
def test_110_logged_band_matches_real_filter(monkeypatch, tmp_path, explicit_band, config_band):
    import aceneurotools.pipelines.stats as pipeline
    import aceneurotools.stats.coherence_analysis as coherence
    from aceneurotools.config.stats_config import StatsConfig, StudyMetadata

    calls = synthetic_loader(monkeypatch)
    bands = []
    original = coherence.filter_signals

    def record_filter(a, b, fr, freq_range, order):
        bands.append(list(freq_range))
        return original(a, b, fr, freq_range, order)

    monkeypatch.setattr(coherence, "filter_signals", record_filter)
    # Heavy downstream metrics/population reporting are outside this parameter-flow proof.
    monkeypatch.setattr(coherence, "compute_signal_stats", lambda *a: [1.0, 1.0, 1.0, 1.0, 1.0])
    monkeypatch.setattr(coherence.CoherenceAnalysis, "run_population", lambda *a, **k: None)
    p = pipeline.StatsPipeline()
    p.run(
        project_path=tmp_path,
        calcium_signal_dir=tmp_path,
        analyses=["coherence_ephys_calcium"],
        study_metadata=StudyMetadata({"synthetic": [1]}, {1: [[0.0, 1.0], [1.0, 2.0]]}),
        stats_config=StatsConfig(lowcut=config_band[0], highcut=config_band[1]),
        freq_range=explicit_band,
        headless=True,
    )
    log = json.loads((tmp_path / "stats_results" / "run_log.json").read_text())
    recorded = log["params"]["freq_range_hz"]
    print(
        f"Logged band={recorded}; actual filter bands={bands}; loader filter_type={calls[0]['filter_type']}; completed={log['completed']}"
    )
    assert log["completed"] and not log["skipped"]
    assert bands and all(band == recorded for band in bands)


def test_111_pipeline_writes_all_drug_summary(monkeypatch, tmp_path, capsys):
    import aceneurotools.pipelines.stats as pipeline
    import aceneurotools.stats.scatter_analysis as scatter
    from aceneurotools.config.stats_config import StatsConfig, StudyMetadata

    synthetic_loader(monkeypatch)

    # Supply successful subject stats; run the actual collector and summary caller.
    def subject(self, **kwargs):
        kwargs["collector"].add_subject(kwargs["line_num"], {"r": 0.2}, {"r": 0.4})
        return True, {}, {}

    monkeypatch.setattr(scatter.ScatterAnalysis, "run_subject", subject)
    monkeypatch.setattr(scatter, "create_population_violin_plot", lambda **k: None)
    p = pipeline.StatsPipeline()
    p.run(
        project_path=tmp_path,
        calcium_signal_dir=tmp_path,
        analyses=["scatter_correlation"],
        study_metadata=StudyMetadata({"synthetic": [1]}, {1: [[0.0, 1.0], [1.0, 2.0]]}),
        stats_config=StatsConfig(headless=True, plot_formats=["png"], color_dpi=60),
        headless=True,
    )
    out = capsys.readouterr().out
    print(out)
    outputs = list((tmp_path / "stats_results").rglob("population_all_drugs_summary_*.png"))
    print(f"All-drugs summary files={outputs}; completed subjects={p.run_log.completed}; skipped={p.run_log.skipped}")
    assert outputs, "Successful subjects but final summary missing"


def test_111_control_mapping_writes_summary(tmp_path):
    from aceneurotools.config.stats_config import StatsConfig
    from aceneurotools.stats.scatter_analysis import PopulationCorrelationCollector, create_all_drugs_summary_plot

    collector = PopulationCorrelationCollector("synthetic")
    collector.add_subject(1, {"r": 0.2}, {"r": 0.4})
    fig, stats = create_all_drugs_summary_plot(
        {"synthetic": collector}, tmp_path, "channel", StatsConfig(headless=True, plot_formats=["png"], color_dpi=60)
    )
    assert (tmp_path / "population_all_drugs_summary_channel.png").is_file()


def test_box_control_clean_single_page_download(tmp_path):
    from aceneurotools.shared.file_downloader import download_file

    (tmp_path / "recording").mkdir()
    client = box_client(
        [NS(type="file", name="trace.ncs", id="2")], lambda file_id, output_stream: output_stream.write(b"COMPLETE")
    )
    assert download_file(client, "recording", 1, base_file_path=tmp_path)
    assert (tmp_path / "recording" / "trace.ncs").read_bytes() == b"COMPLETE"


def test_box_partial_folder_not_considered_complete(tmp_path):
    from aceneurotools.shared.file_downloader import verify_path

    (tmp_path / "recording").mkdir()
    (tmp_path / "recording" / "README.txt").write_text("No recording data is present")
    status = verify_path("recording", base_file_path=tmp_path)
    print(f"Folder with only README verified={status}")
    assert not status


def test_112_control_help_exits_successfully():
    result = subprocess.run([sys.executable, "-m", "aceneurotools.cli", "--help"], capture_output=True, text=True)
    assert result.returncode == 0 and "--config" in result.stdout


def test_113_control_full_frame_keeps_movie():
    from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor

    movie, _ = MiniscopePreprocessor.crop_movie(None, np.ones((2, 8, 10)), {"x0": 0, "y0": 0, "x1": 10, "y1": 8})
    assert movie.shape == (2, 8, 10)
