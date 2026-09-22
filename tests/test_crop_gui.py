"""Regression coverage for cancelling the legacy crop dialog."""

from __future__ import annotations

import importlib
import sys
import types
from collections.abc import Iterator

import numpy as np
import pytest


class _FakeElement:
    def update(self, *args, **kwargs) -> None:
        pass


class _FakeGraph(_FakeElement):
    def draw_rectangle(self, *args, **kwargs) -> int:
        return 1

    def draw_image(self, *args, **kwargs) -> None:
        pass

    def delete_figure(self, *args, **kwargs) -> None:
        pass


class _FakeWindow:
    def __init__(self, events: list[tuple[str, dict]]) -> None:
        self._events = iter(events)
        self._graph = _FakeGraph()

    def __getitem__(self, key: str):
        return self._graph if key == "-GRAPH-" else _FakeElement()

    def read(self, timeout=None):
        return next(self._events)

    def close(self) -> None:
        pass


@pytest.fixture
def crop_modules() -> Iterator[tuple[types.ModuleType, types.ModuleType, types.ModuleType]]:
    """Load the GUI and its caller with lightweight stand-ins for optional UI deps."""
    module_names = (
        "caiman",
        "cv2",
        "tqdm",
        "FreeSimpleGUI",
        "aceneurotools.miniscope.gui_utils",
        "aceneurotools.miniscope.miniscope_preprocessor",
    )
    missing = object()
    originals = {name: sys.modules.get(name, missing) for name in module_names}
    for name in module_names:
        sys.modules.pop(name, None)

    caiman = types.ModuleType("caiman")
    caiman.movie = np.ndarray
    sys.modules["caiman"] = caiman
    sys.modules["cv2"] = types.ModuleType("cv2")

    tqdm_module = types.ModuleType("tqdm")

    def tqdm(iterable, *args, **kwargs):
        return iterable

    tqdm.monitor_interval = 0
    tqdm_module.tqdm = tqdm
    sys.modules["tqdm"] = tqdm_module

    fake_sg = types.ModuleType("FreeSimpleGUI")
    fake_sg.WINDOW_CLOSED = "__WINDOW_CLOSED__"
    fake_sg.Text = fake_sg.Graph = fake_sg.Combo = fake_sg.Button = (
        lambda *args, **kwargs: _FakeElement()
    )
    fake_sg.Window = lambda *args, **kwargs: _FakeWindow([])
    sys.modules["FreeSimpleGUI"] = fake_sg

    try:
        gui_utils = importlib.import_module("aceneurotools.miniscope.gui_utils")
        preprocessor = importlib.import_module(
            "aceneurotools.miniscope.miniscope_preprocessor"
        )
        gui_utils._update_image = lambda *args, **kwargs: None
        yield gui_utils, preprocessor, fake_sg
    finally:
        for name in module_names:
            sys.modules.pop(name, None)
            if originals[name] is not missing:
                sys.modules[name] = originals[name]


def _projection() -> types.SimpleNamespace:
    return types.SimpleNamespace(max=np.zeros((48, 64)))


@pytest.mark.parametrize("event", ["-CANCEL-", "__WINDOW_CLOSED__"])
def test_cancel_returns_none_without_mutating_saved_coordinates(crop_modules, event):
    gui_utils, _, fake_sg = crop_modules
    saved = {"x0": 4, "y0": 5, "x1": 40, "y1": 30}
    fake_sg.Window = lambda *args, **kwargs: _FakeWindow(
        [
            ("-GRAPH-", {"-GRAPH-": (12, 15)}),
            (event, {}),
        ]
    )

    result = gui_utils.crop_gui(saved, _projection(), 48, 64)

    assert result is None
    assert saved == {"x0": 4, "y0": 5, "x1": 40, "y1": 30}


def test_submit_returns_the_accepted_coordinates(crop_modules):
    gui_utils, _, fake_sg = crop_modules
    fake_sg.Window = lambda *args, **kwargs: _FakeWindow(
        [
            ("-GRAPH-", {"-GRAPH-": (10, 12)}),
            ("-GRAPH-", {"-GRAPH-": (40, 35)}),
            ("-SUBMIT-", {}),
        ]
    )

    result = gui_utils.crop_gui(None, _projection(), 48, 64)

    assert result == {"x0": 10, "y0": 12, "x1": 40, "y1": 35}


@pytest.mark.parametrize("event", ["-CANCEL-", "__WINDOW_CLOSED__"])
def test_preprocessor_skips_crop_after_dialog_cancellation(
    crop_modules, monkeypatch, event
):
    _, preprocessor_module, fake_sg = crop_modules
    fake_sg.Window = lambda *args, **kwargs: _FakeWindow([(event, {})])

    class _Movie(np.ndarray):
        pass

    movie = np.zeros((5, 48, 64)).view(_Movie)
    movie.fr = 30.0
    data_manager = types.SimpleNamespace(
        movie=movie,
        projections=None,
        coords=None,
        preprocessed_movie_filepath=None,
    )
    preprocessor = preprocessor_module.MiniscopePreprocessor(data_manager)
    preprocessor.compute_projections = lambda _movie: _projection()

    def unexpected_crop(*args, **kwargs):
        raise AssertionError("crop_movie must not run after cancellation")

    preprocessor.crop_movie = unexpected_crop
    monkeypatch.setattr(
        preprocessor_module.MovieIO,
        "save_movie",
        lambda *args, **kwargs: "full-frame.avi",
    )

    result = preprocessor.preprocess_calcium_movie(crop=True)

    assert result.movie is movie
    assert result.movie.shape == (5, 48, 64)
    assert result.coords is None
