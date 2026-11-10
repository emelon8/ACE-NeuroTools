"""The calcium + ephys movie export finds the right movie, renders it and runs without windows."""

import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

pytest.importorskip("caiman")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from aceneurotools.multimodal import calcium_ephys_visualizer as visualizer  # noqa: E402
from aceneurotools.multimodal.miniscope_ephys_alignment_utils import (  # noqa: E402
    find_ca_movie_filenums,
    find_numbered_movies,
)

FRAMES = 20


# Exact movie lookup


def touch(path, age=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    os.utime(path, (1_000_000 + age, 1_000_000 + age))
    return path


def test_numbered_movies_match_whole_names_regardless_of_file_times(tmp_path):
    touch(tmp_path / "10.avi", age=0)  # Oldest: the previous prefix lookup would have picked this for movie 1.
    touch(tmp_path / "12.avi", age=1)
    one = touch(tmp_path / "1.avi", age=50)
    two = touch(tmp_path / "2.avi", age=60)
    touch(tmp_path / "saved_movies" / "1.avi", age=-5)  # Outputs are never inputs.

    assert find_numbered_movies(str(tmp_path), [1]) == [str(one)]
    assert find_numbered_movies(str(tmp_path), [2, 1]) == [str(two), str(one)]


def test_numbered_movies_report_missing_and_ambiguous_names(tmp_path):
    touch(tmp_path / "Miniscope" / "1.avi")
    with pytest.raises(FileNotFoundError, match="3.avi, 4.avi"):
        find_numbered_movies(str(tmp_path), [1, 3, 4])
    touch(tmp_path / "BehavCam_0" / "1.avi")
    with pytest.raises(ValueError, match="more than one folder"):
        find_numbered_movies(str(tmp_path), [1])


def test_time_ranges_load_their_movies_in_numeric_order(tmp_path):
    for name in ["2.avi", "3.avi", "20.avi", "30.avi", "23.avi"]:
        touch(tmp_path / name, age=-int(name.split(".")[0]))
    ttl = np.arange(0, 2000, 25)  # 80 frames over 2 s
    channel = SimpleNamespace(time_vector=np.linspace(0, 2, 2000))
    dm = SimpleNamespace(metadata={"calcium imaging directory": str(tmp_path), "framesPerFile": 20}, analysis_params={})

    paths, frames = find_ca_movie_filenums(channel, ttl, dm, [1.1, 1.9])
    assert [Path(path).name for path in paths] == ["2.avi", "3.avi"]
    assert frames.tolist() == [44, 75]
    dm.metadata["calcium imaging directory"] = ""
    assert find_ca_movie_filenums(channel, ttl, dm, [1.1, 1.9])[0] == []


# Rendering and saving


class Recorder:
    """Stands in for FuncAnimation: save() renders every frame, then writes a placeholder file."""

    instances: list = []
    fail = None

    def __init__(self, fig, func, frames, interval, repeat):
        self.fig, self.func, self.frames = fig, func, frames
        Recorder.instances.append(self)

    def save(self, path, dpi):
        for frame in range(self.frames):
            self.func(frame)
        if Recorder.fail:
            raise Recorder.fail
        Path(path).write_bytes(b"movie")


@pytest.fixture
def export(tmp_path, monkeypatch):
    Recorder.instances, Recorder.fail = [], None
    movie = np.random.default_rng(0).random((FRAMES, 12, 16))
    dm = SimpleNamespace(
        metadata={
            "calcium imaging directory": str(tmp_path),
            "framesPerFile": FRAMES,
            "frameRate": 20.0,
            "total systemic time (min)": 1,
            "systemic drug": "Ketamine",
        },
        analysis_params={},
    )
    channel = SimpleNamespace(
        events={"labels": np.array(["start infusion"]), "timestamps": np.array([0.5])},
        time_vector=np.linspace(0, 2, 2000),
        signal=np.sin(np.linspace(0, 20, 2000)),
        sampling_rate=1000.0,
    )
    ttl = np.arange(0, 2000, 100)
    touch(tmp_path / "Miniscope" / "0.avi")
    touch(tmp_path / "Miniscope" / "10.avi", age=-10)
    loaded = []
    monkeypatch.setattr(visualizer.cm, "load", lambda path: loaded.append(path) or movie.copy())
    monkeypatch.setattr(visualizer.animation, "FuncAnimation", Recorder)
    monkeypatch.setattr(visualizer.plt, "subplots", lambda *a, **k: pytest.fail("a headless export used pyplot"))
    monkeypatch.setattr(visualizer.plt, "show", lambda *a, **k: pytest.fail("a headless export opened a window"))
    plt.close("all")
    return SimpleNamespace(dm=dm, channel=channel, ttl=ttl, movie=movie, loaded=loaded, root=tmp_path)


def draw(recorder, frame):
    recorder.func(frame)
    return recorder.fig.axes[0]


def test_headless_export_renders_every_frame_and_saves_it(export):
    saved = visualizer.create_ca_ephys_movie(
        export.dm, export.ttl, export.channel, movie_num=0, save_movie=True, headless=True
    )

    expected = export.root / "saved_movies" / "miniscope_ephys_movie0.mp4"
    assert saved == str(expected) and expected.read_bytes() == b"movie"
    assert export.loaded == [str(export.root / "Miniscope" / "0.avi")], "exact movie, not 10.avi"
    assert plt.get_fignums() == [], "no pyplot figure was created"
    (recorder,) = Recorder.instances
    assert recorder.frames == FRAMES

    ax = draw(recorder, 12)
    np.testing.assert_array_equal(ax.images[0].get_array(), export.movie[12])
    (trace,) = [line for line in ax.lines if line.get_color() == "red"]
    segment = export.channel.signal[export.ttl[2]:export.ttl[12]]
    scaling = 12 / np.max(np.abs(export.channel.signal))
    np.testing.assert_allclose(trace.get_ydata(), segment * scaling + 2)
    elapsed = export.channel.time_vector[export.ttl[12]] - export.channel.time_vector[export.ttl[0]]
    texts = [text.get_text() for text in ax.texts]
    assert f"{elapsed:.2f} s" in texts
    assert "Ketamine infusion" in texts, "frame 12 (1.2 s) is inside the infusion window that starts at 0.5 s"
    assert "Ketamine infusion" not in [text.get_text() for text in draw(recorder, 2).texts], "0.2 s is before it"


def test_exports_are_named_after_their_selection_or_output_path(export, monkeypatch):
    monkeypatch.setattr(
        visualizer, "find_ca_movie_filenums",
        lambda channel, ttl, dm, time_range: ([str(export.root / "Miniscope" / "0.avi")], np.array([0, FRAMES - 1])),
    )
    monkeypatch.setattr(visualizer.cm, "load_movie_chain", lambda paths: export.movie.copy())
    by_range = visualizer.create_ca_ephys_movie(
        export.dm, export.ttl, export.channel, time_range=[0.25, 1.5], save_movie=True, headless=True
    )
    assert Path(by_range).name == "miniscope_ephys_0.25-1.5s.mp4"
    chosen = export.root / "exports" / "baseline.mp4"
    assert visualizer.create_ca_ephys_movie(
        export.dm, export.ttl, export.channel, movie_num=0, save_movie=True, headless=True, output_path=str(chosen)
    ) == str(chosen)
    assert chosen.read_bytes() == b"movie"


@pytest.mark.parametrize("events", [{"labels": [], "timestamps": []}, None, {"labels": np.array(["TTL Input"])}])
def test_recordings_without_a_start_event_export_without_the_marker(export, events, capsys):
    export.channel.events = events
    visualizer.create_ca_ephys_movie(export.dm, export.ttl, export.channel, movie_num=0, save_movie=True, headless=True)
    assert 'no event label starts with "start"' in capsys.readouterr().out
    assert "Ketamine infusion" not in [text.get_text() for text in draw(Recorder.instances[0], 12).texts]


def test_a_failed_save_is_raised_and_leaves_no_figure(export):
    Recorder.fail = OSError("ffmpeg is not installed")
    with pytest.raises(OSError, match="ffmpeg"):
        visualizer.create_ca_ephys_movie(export.dm, export.ttl, export.channel, movie_num=0, save_movie=True, headless=True)
    assert plt.get_fignums() == []


@pytest.mark.parametrize(
    "change,message",
    [
        ({"dm_metadata": None}, "metadata is missing"),
        ({"plot_ephys": False}, "not to overlay"),
        ({"movie_num": None}, "either a time range or a movie number"),
    ],
)
def test_invalid_requests_raise_when_headless_and_print_otherwise(export, change, message, capsys):
    if "dm_metadata" in change:
        export.dm.metadata = None
    kwargs = {"movie_num": change.get("movie_num", 0), "plot_ephys": change.get("plot_ephys", True)}
    with pytest.raises(ValueError, match=message):
        visualizer.create_ca_ephys_movie(export.dm, export.ttl, export.channel, headless=True, **kwargs)
    assert visualizer.create_ca_ephys_movie(export.dm, export.ttl, export.channel, headless=False, **kwargs) is None
    assert message in capsys.readouterr().out


def test_interactive_export_shows_the_movie_with_pyplot(export, monkeypatch):
    shown = []
    monkeypatch.undo()  # Restore pyplot.subplots/show for the interactive path, then re-patch the rest.
    monkeypatch.setattr(visualizer.cm, "load", lambda path: export.movie.copy())
    monkeypatch.setattr(visualizer.animation, "FuncAnimation", Recorder)
    monkeypatch.setattr(visualizer.plt, "show", lambda *a, **k: shown.append(True))
    assert visualizer.create_ca_ephys_movie(export.dm, export.ttl, export.channel, movie_num=0, play_movie=True) is None
    assert shown == [True] and len(plt.get_fignums()) == 1
    plt.close("all")


def test_crop_uses_supplied_coordinates_without_a_crop_window(export, monkeypatch):
    calls = {}

    class Preprocessor:
        def __init__(self, manager):
            pass

        def compute_projections(self, movie):
            return None

        def get_crop_coordinates(self, coords, projections, height, width, headless=False):
            calls["coords"], calls["headless"] = coords, headless
            return coords

        def crop_movie(self, movie, coords):
            return movie[:, coords["y0"]:coords["y1"], coords["x0"]:coords["x1"]], ""

    monkeypatch.setattr(visualizer, "CalciumImagingPreprocessor", Preprocessor)
    visualizer.create_ca_ephys_movie(
        export.dm, export.ttl, export.channel, movie_num=0, crop=True, crop_coords=[2, 1, 10, 9],
        save_movie=True, headless=True,
    )
    assert calls == {"coords": {"x0": 2, "y0": 1, "x1": 10, "y1": 9}, "headless": True}
    ax = draw(Recorder.instances[0], 5)
    np.testing.assert_array_equal(ax.images[0].get_array(), export.movie[5, 1:9, 2:10])
