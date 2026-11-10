"""Non-blocking CNMF-E tuning helpers match the interactive plot_params step."""

import numpy as np
import pytest

from aceneurotools.calcium_imaging.cnmfe_tuning import (
    CNMFEPatchGeometry,
    cnmfe_patch_geometry,
    quilt_display_limits,
    tuning_frame_step,
)


@pytest.mark.parametrize(
    ("rf", "stride", "expected"),
    [(40, 20, CNMFEPatchGeometry(81, 60, 21)), (12, 6, CNMFEPatchGeometry(25, 18, 7)), (0, 0, CNMFEPatchGeometry(1, 0, 1))],
)
def test_patch_geometry_matches_previous_inline_arithmetic(rf, stride, expected):
    width = rf * 2 + 1
    overlap = stride + 1
    assert cnmfe_patch_geometry(rf, stride) == expected == CNMFEPatchGeometry(width, width - overlap, overlap)


@pytest.mark.parametrize(("frames", "step"), [(1, 1), (999, 1), (1000, 1), (1999, 1), (2000, 2), (30000, 30)])
def test_frame_step_matches_previous_subsampling(frames, step):
    assert tuning_frame_step(frames) == max(frames // 1000, 1) == step


def test_quilt_limits_match_previous_percentiles():
    image = np.random.default_rng(0).random((32, 48))
    assert quilt_display_limits(image) == (np.percentile(np.ravel(image), 50), np.percentile(np.ravel(image), 99.5))


def test_tuning_images_match_direct_caiman_call():
    cm = pytest.importorskip("caiman")
    from aceneurotools.calcium_imaging.cnmfe_tuning import compute_cnmfe_tuning_images

    images = np.random.default_rng(1).random((2500, 24, 24)).astype(np.float32)
    expected = cm.summary_images.correlation_pnr(images[::2], gSig=3, swap_dim=False)
    actual = compute_cnmfe_tuning_images(images)
    for left, right in zip(actual, expected):
        np.testing.assert_array_equal(left, right)


@pytest.mark.parametrize("gsig", [0, -3, 2.5, True, (3, 3)])
def test_tuning_images_reject_invalid_kernel_sizes(gsig):
    from aceneurotools.calcium_imaging.cnmfe_tuning import compute_cnmfe_tuning_images

    with pytest.raises(ValueError, match="gsig"):
        compute_cnmfe_tuning_images(np.zeros((4, 8, 8), dtype=np.float32), gsig=gsig)


@pytest.mark.parametrize("max_frames", [0, -1, 1.5, True])
def test_frame_step_rejects_invalid_targets(max_frames):
    with pytest.raises(ValueError, match="max_frames"):
        tuning_frame_step(100, max_frames)


# The processor's plot_params branch draws exactly what the old inline code drew.

from types import SimpleNamespace  # noqa: E402


class FakeOpts:
    def __init__(self):
        self.values = {("data", "fnames"): ["movie.mmap"], ("patch", "rf"): 12, ("patch", "stride"): 6}
        self.changes = []

    def get(self, group, key):
        return self.values[(group, key)]

    def change_params(self, params):
        self.changes.append(params)


@pytest.fixture
def tuning_run(monkeypatch):
    from aceneurotools.calcium_imaging import calcium_imaging_processor as module
    from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor

    calls = {"show": 0}
    frames, dims = 2500, (8, 10)
    Yr = np.random.default_rng(2).random((dims[0] * dims[1], frames)).astype(np.float32)
    correlation = np.linspace(0, 1, 80).reshape(dims)
    pnr = np.full(dims, 7.0)

    def correlation_pnr(images, gSig, swap_dim):
        calls["correlation_pnr"] = (images.shape, gSig, swap_dim)
        return correlation, pnr

    class Axis:
        def set_title(self, title):
            calls["title"] = title

    def view_quilt(*args, **kwargs):
        calls["view_quilt"] = (args, kwargs)
        return Axis()

    processor = object.__new__(CalciumImagingProcessor)
    monkeypatch.setattr(processor, "cleanup_tkinter", lambda: None)
    monkeypatch.setattr(module.cm, "load_memmap", lambda path: (Yr, dims, frames))
    monkeypatch.setattr(module.cm.summary_images, "correlation_pnr", correlation_pnr)
    monkeypatch.setattr(
        module.cm.utils.visualization, "inspect_correlation_pnr", lambda c, p: calls.__setitem__("inspect", (c, p))
    )
    monkeypatch.setattr(module.cm.utils.visualization, "view_quilt", view_quilt)
    monkeypatch.setattr(module.plt, "show", lambda block=None: calls.__setitem__("show", calls["show"] + 1))
    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=None)
    return processor, manager, calls, Yr, dims, correlation, pnr


def test_plot_params_draws_the_tuning_images_and_patch_quilt(tuning_run, capsys):
    processor, manager, calls, Yr, dims, correlation, pnr = tuning_run
    returned, images = processor.cnmfe_parameter_handler(manager, plot_params=True)

    assert returned is manager and manager.opts_caiman.changes == [{"data": {"dims": dims}}]
    np.testing.assert_array_equal(images, Yr.T.reshape((2500,) + dims, order="F"))
    assert calls["correlation_pnr"] == ((1250,) + dims, 3, False), "2500 frames sampled every 2nd frame, gSig=3"
    assert calls["inspect"][0] is correlation and calls["inspect"][1] is pnr
    args, kwargs = calls["view_quilt"]
    # rf=12, stride=6 -> width 25, overlap 7, step 18 (the previous inline arithmetic).
    assert args == (correlation, 18, 7)
    assert kwargs == {
        "vmin": np.percentile(correlation, 50),
        "vmax": np.percentile(correlation, 99.5),
        "color": "yellow",
        "figsize": (4, 4),
    }
    assert calls["title"] == "CNMFE Patch Width 25, Overlap 7"
    assert calls["show"] == 2
    assert "Patch width: 25 , Stride: 18, Overlap: 7" in capsys.readouterr().out


def test_without_plot_params_nothing_is_drawn(tuning_run):
    processor, manager, calls, Yr, dims, _, _ = tuning_run
    _, images = processor.cnmfe_parameter_handler(manager, plot_params=False)
    assert images.shape == (2500,) + dims
    assert set(calls) == {"show"} and calls["show"] == 0
