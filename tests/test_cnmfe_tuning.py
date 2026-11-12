"""Window-free CNMF-E tuning helpers match the interactive plot_params step."""

from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.calcium_imaging.cnmfe_tuning import (
    TUNING_GSIG,
    TUNING_MAX_FRAMES,
    CNMFEPatchGeometry,
    cnmfe_patch_geometry,
    compute_cnmfe_tuning_images,
    quilt_display_limits,
    tuning_frame_step,
)


def test_defaults_match_the_previous_inline_values():
    assert (TUNING_GSIG, TUNING_MAX_FRAMES) == (3, 1000)


def test_importing_the_module_does_not_import_caiman():
    import os
    import subprocess
    import sys
    from pathlib import Path

    import aceneurotools

    # Import the same source tree the tests use (a worktree's src, not an editable install elsewhere).
    source_root = str(Path(aceneurotools.__file__).resolve().parents[1])
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([source_root, os.environ.get("PYTHONPATH", "")])}
    code = "import sys, aceneurotools.calcium_imaging.cnmfe_tuning; print('caiman' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=environment)
    assert result.stdout.strip() == "False"


# --- patch geometry -------------------------------------------------------------


@pytest.mark.parametrize(
    ("rf", "stride", "expected"),
    [
        (40, 20, CNMFEPatchGeometry(81, 60, 21)),
        (12, 6, CNMFEPatchGeometry(25, 18, 7)),
        (1, 0, CNMFEPatchGeometry(3, 2, 1)),
        (5, 9, CNMFEPatchGeometry(11, 1, 10)),  # largest valid stride: step of one pixel
        (np.int64(12), np.int32(6), CNMFEPatchGeometry(25, 18, 7)),
    ],
)
def test_patch_geometry_matches_previous_inline_arithmetic(rf, stride, expected):
    width = int(rf) * 2 + 1
    overlap = int(stride) + 1
    geometry = cnmfe_patch_geometry(rf, stride)
    assert geometry == expected == CNMFEPatchGeometry(width, width - overlap, overlap)
    assert all(type(value) is int for value in (geometry.width, geometry.stride, geometry.overlap))


@pytest.mark.parametrize(
    ("rf", "stride", "message"),
    [
        (0, 0, "rf"),
        (-3, 1, "rf"),
        (None, 6, "rf"),
        ([12, 12], 6, "rf"),
        (12.0, 6, "rf"),
        (True, 0, "rf"),
        (12, -1, "stride"),
        (12, None, "stride"),
        (12, [6, 6], "stride"),
        (12, 6.0, "stride"),
        (5, 10, "2 \\* rf"),  # overlap equals the width: patches would not advance
        (3, 10, "2 \\* rf"),  # previously returned a negative step
    ],
)
def test_patch_geometry_rejects_invalid_settings(rf, stride, message):
    with pytest.raises(ValueError, match=message):
        cnmfe_patch_geometry(rf, stride)


# --- frame subsampling ----------------------------------------------------------


@pytest.mark.parametrize(("frames", "step"), [(0, 1), (1, 1), (999, 1), (1000, 1), (1999, 1), (2000, 2), (30000, 30)])
def test_frame_step_matches_previous_subsampling(frames, step):
    assert tuning_frame_step(frames) == max(frames // 1000, 1) == step


def test_frame_step_uses_the_given_target_and_numpy_integers():
    assert tuning_frame_step(np.int64(2500), np.int32(500)) == 5
    assert type(tuning_frame_step(np.int64(2500), np.int32(500))) is int


@pytest.mark.parametrize("max_frames", [0, -1, 1.5, True, None])
def test_frame_step_rejects_invalid_targets(max_frames):
    with pytest.raises(ValueError, match="max_frames"):
        tuning_frame_step(100, max_frames)


@pytest.mark.parametrize("n_frames", [-1, 2500.0, True, None])
def test_frame_step_rejects_invalid_frame_counts(n_frames):
    with pytest.raises(ValueError, match="n_frames"):
        tuning_frame_step(n_frames)


# --- quilt limits ---------------------------------------------------------------


def test_quilt_limits_match_previous_percentiles():
    image = np.random.default_rng(0).random((32, 48))
    limits = quilt_display_limits(image)
    assert limits == (np.percentile(np.ravel(image), 50), np.percentile(np.ravel(image), 99.5))
    assert all(type(value) is float for value in limits)


# --- tuning images --------------------------------------------------------------


@pytest.fixture
def recorded_correlation_pnr(monkeypatch):
    caiman = pytest.importorskip("caiman")
    calls = []
    correlation, pnr = np.ones((8, 8)), np.full((8, 8), 2.0)

    def correlation_pnr(images, gSig, swap_dim):
        calls.append({"images": images, "gSig": gSig, "swap_dim": swap_dim})
        return correlation, pnr

    monkeypatch.setattr(caiman.summary_images, "correlation_pnr", correlation_pnr)
    return calls, correlation, pnr


def test_tuning_images_forward_the_kernel_size_and_frame_target(recorded_correlation_pnr):
    calls, correlation, pnr = recorded_correlation_pnr
    images = np.arange(2500 * 2 * 2, dtype=np.float32).reshape(2500, 2, 2)

    result = compute_cnmfe_tuning_images(images, gsig=np.int64(4), max_frames=500)

    assert result[0] is correlation and result[1] is pnr
    (call,) = calls
    np.testing.assert_array_equal(call["images"], images[::5])
    assert call["gSig"] == 4 and type(call["gSig"]) is int
    assert call["swap_dim"] is False


@pytest.mark.parametrize("gsig", [[5, 5], (5, 7), np.array([5, 7])])
def test_tuning_images_pass_a_kernel_pair_to_caiman_as_a_list(recorded_correlation_pnr, gsig):
    calls, _, _ = recorded_correlation_pnr
    compute_cnmfe_tuning_images(np.zeros((10, 8, 8), dtype=np.float32), gsig=gsig)
    assert calls[0]["gSig"] == [int(value) for value in gsig]
    assert type(calls[0]["gSig"]) is list and all(type(value) is int for value in calls[0]["gSig"])


def test_tuning_images_match_direct_caiman_call():
    cm = pytest.importorskip("caiman")
    images = np.random.default_rng(1).random((2000, 10, 10)).astype(np.float32)
    expected = cm.summary_images.correlation_pnr(images[::2], gSig=3, swap_dim=False)

    for actual in (compute_cnmfe_tuning_images(images), compute_cnmfe_tuning_images(images, gsig=[3, 3])):
        for left, right in zip(actual, expected):
            np.testing.assert_array_equal(left, right)


@pytest.mark.parametrize(
    "gsig", [0, -3, 2.5, True, None, "3", (3,), [3, 3, 3], [0, 3], [3, 2.5], [True, 3], np.array(3), np.ones((2, 2), int)]
)
def test_tuning_images_reject_invalid_kernel_sizes(gsig):
    with pytest.raises(ValueError, match="gsig"):
        compute_cnmfe_tuning_images(np.zeros((4, 8, 8), dtype=np.float32), gsig=gsig)


def test_tuning_images_reject_invalid_frame_targets():
    with pytest.raises(ValueError, match="max_frames"):
        compute_cnmfe_tuning_images(np.zeros((4, 8, 8), dtype=np.float32), max_frames=0)


# --- the processor's plot_params branch draws what the old inline code drew ------


class FakeOpts:
    def __init__(self, rf=12, stride=6):
        self.values = {("data", "fnames"): ["movie.mmap"], ("patch", "rf"): rf, ("patch", "stride"): stride}
        self.changes = []

    def get(self, group, key):
        return self.values[(group, key)]

    def change_params(self, params):
        self.changes.append(params)


class FakeTimer:
    def __init__(self, events):
        self.events = events

    def pause_timer(self):
        self.events.append("pause")

    def resume_timer(self):
        self.events.append("resume")


@pytest.fixture
def tuning_run(monkeypatch):
    caiman = pytest.importorskip("caiman")

    from aceneurotools.calcium_imaging import calcium_imaging_processor as module
    from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor

    events = []
    details = {}
    frames, dims = 2500, (8, 10)
    Yr = np.random.default_rng(2).random((dims[0] * dims[1], frames)).astype(np.float32)
    correlation = np.linspace(0, 1, 80).reshape(dims)
    pnr = np.full(dims, 7.0)

    def correlation_pnr(images, gSig, swap_dim):
        events.append("correlation_pnr")
        details["correlation_pnr"] = (images.shape, gSig, swap_dim)
        return correlation, pnr

    class Axis:
        def set_title(self, title):
            events.append("set_title")
            details["title"] = title

    def view_quilt(*args, **kwargs):
        events.append("view_quilt")
        details["view_quilt"] = (args, kwargs)
        return Axis()

    def inspect(c, p):
        events.append("inspect_correlation_pnr")
        details["inspect"] = (c, p)

    def show(*args, **kwargs):
        events.append(f"show(block={kwargs.get('block')!r})")

    processor = object.__new__(CalciumImagingProcessor)
    monkeypatch.setattr(processor, "cleanup_tkinter", lambda: events.append("cleanup_tkinter"))
    monkeypatch.setattr(module.cm, "load_memmap", lambda path: (Yr, dims, frames))
    # compute_cnmfe_tuning_images imports caiman itself, so patch the shared module object.
    monkeypatch.setattr(caiman.summary_images, "correlation_pnr", correlation_pnr)
    monkeypatch.setattr(module.cm.utils.visualization, "inspect_correlation_pnr", inspect)
    monkeypatch.setattr(module.cm.utils.visualization, "view_quilt", view_quilt)
    monkeypatch.setattr(module.plt, "show", show)
    return SimpleNamespace(
        processor=processor, events=events, details=details, Yr=Yr, dims=dims, correlation=correlation, pnr=pnr
    )


def test_plot_params_draws_the_tuning_images_and_patch_quilt_in_order(tuning_run, capsys):
    run = tuning_run
    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=FakeTimer(run.events))

    returned, images = run.processor.cnmfe_parameter_handler(manager, plot_params=True)

    assert returned is manager and manager.opts_caiman.changes == [{"data": {"dims": run.dims}}]
    np.testing.assert_array_equal(images, run.Yr.T.reshape((2500,) + run.dims, order="F"))
    assert run.events == [
        "cleanup_tkinter",
        "correlation_pnr",
        "pause",
        "inspect_correlation_pnr",
        "show(block=True)",
        "resume",
        "pause",
        "view_quilt",
        "set_title",
        "show(block=True)",
        "resume",
    ]
    assert run.details["correlation_pnr"] == ((1250,) + run.dims, 3, False), "2500 frames, every 2nd, gSig=3"
    assert run.details["inspect"][0] is run.correlation and run.details["inspect"][1] is run.pnr
    args, kwargs = run.details["view_quilt"]
    # rf=12, stride=6 -> width 25, overlap 7, step 18 (the previous inline arithmetic).
    assert args == (run.correlation, 18, 7)
    assert kwargs == {
        "vmin": np.percentile(run.correlation, 50),
        "vmax": np.percentile(run.correlation, 99.5),
        "color": "yellow",
        "figsize": (4, 4),
    }
    assert run.details["title"] == "CNMFE Patch Width 25, Overlap 7"
    assert capsys.readouterr().out == "Patch width: 25 , Stride: 18, Overlap: 7\n"


def test_plot_params_without_a_timer_still_shows_both_windows(tuning_run):
    run = tuning_run
    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=None)
    run.processor.cnmfe_parameter_handler(manager, plot_params=True)
    assert "pause" not in run.events and run.events.count("show(block=True)") == 2


def test_plot_params_stops_on_invalid_patch_settings_after_the_first_window(tuning_run):
    run = tuning_run
    manager = SimpleNamespace(opts_caiman=FakeOpts(rf=3, stride=10), diag_logger=FakeTimer(run.events))
    with pytest.raises(ValueError, match="2 \\* rf"):
        run.processor.cnmfe_parameter_handler(manager, plot_params=True)
    assert run.events[-1] == "resume" and "view_quilt" not in run.events


def test_without_plot_params_nothing_is_drawn(tuning_run):
    run = tuning_run
    manager = SimpleNamespace(opts_caiman=FakeOpts(), diag_logger=FakeTimer(run.events))
    _, images = run.processor.cnmfe_parameter_handler(manager, plot_params=False)
    assert images.shape == (2500,) + run.dims
    assert run.events == ["cleanup_tkinter"]
