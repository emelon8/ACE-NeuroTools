"""Cancelling a provisional crop preserves the movie and saved coordinates."""

from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.calcium_imaging import gui_utils
from aceneurotools.calcium_imaging.calcium_imaging_preprocessor import CalciumImagingPreprocessor


@pytest.fixture
def crop_dialog(monkeypatch):
    class Element:
        def update(self, *args, **kwargs):
            pass

        def draw_rectangle(self, *args, **kwargs):
            return 1

        def delete_figure(self, *args, **kwargs):
            pass

    class Window:
        def __init__(self, events):
            self.events = iter(events)
            self.closed = False

        def __getitem__(self, key):
            return Element()

        def read(self, **kwargs):
            return next(self.events)

        def close(self):
            self.closed = True

    def show(events):
        window = Window(events)
        sg = SimpleNamespace(WINDOW_CLOSED=None, Window=lambda *a, **kw: window)
        for name in ("Text", "Graph", "Combo", "Button"):
            setattr(sg, name, lambda *a, **kw: Element())
        monkeypatch.setattr(gui_utils, "sg", sg)
        monkeypatch.setattr(gui_utils, "_update_image", lambda *a, **kw: None)
        return window

    return show


@pytest.mark.parametrize("event", ["-CANCEL-", None], ids=["cancel", "close"])
def test_cancel_keeps_provisional_edits_out_of_saved_coordinates(crop_dialog, event):
    window = crop_dialog([("-GRAPH-", {"-GRAPH-": (12, 15)}), (event, {})])
    saved = {"x0": 4, "y0": 5, "x1": 40, "y1": 30}
    result = gui_utils.crop_gui(saved, SimpleNamespace(max=np.zeros((48, 64))), 48, 64)
    assert result is None
    assert saved == {"x0": 4, "y0": 5, "x1": 40, "y1": 30}
    assert window.closed


@pytest.mark.parametrize("event", ["-CANCEL-", None], ids=["cancel", "close"])
def test_preprocessing_cancel_preserves_full_movie(crop_dialog, monkeypatch, event):
    crop_dialog([(event, {})])

    class Movie(np.ndarray):
        pass

    movie = np.arange(5 * 48 * 64).reshape((5, 48, 64)).view(Movie)
    movie.fr = 30.0
    dm = SimpleNamespace(movie=movie, coords=None)
    processor = CalciumImagingPreprocessor(dm)
    monkeypatch.setattr(processor, "compute_projections", lambda _: SimpleNamespace(max=movie.max(axis=0)))
    monkeypatch.setattr(
        "aceneurotools.calcium_imaging.calcium_imaging_preprocessor.MovieIO.save_movie",
        lambda *a, **kw: "full-frame.avi",
    )
    result = processor.preprocess_calcium_movie(crop=True)
    assert result.movie is movie
    assert result.movie.shape == (5, 48, 64)
    assert result.coords is None
    assert processor.result.coords is None


def test_submit_accepts_the_selected_crop(crop_dialog):
    crop_dialog(
        [
            ("-GRAPH-", {"-GRAPH-": (10, 12)}),
            ("-GRAPH-", {"-GRAPH-": (40, 35)}),
            ("-SUBMIT-", {}),
        ]
    )
    result = gui_utils.crop_gui(None, SimpleNamespace(max=np.zeros((48, 64))), 48, 64)
    assert result == {"x0": 10, "y0": 12, "x1": 40, "y1": 35}


@pytest.mark.parametrize("saved", [None, {}])
def test_submit_without_selection_uses_full_frame(crop_dialog, saved):
    crop_dialog([("-SUBMIT-", {})])
    result = gui_utils.crop_gui(saved, SimpleNamespace(max=np.zeros((48, 64))), 48, 64)
    assert result == {"x0": 0, "y0": 0, "x1": 64, "y1": 48}
