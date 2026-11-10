"""Motion-correction shifts are saved during processing and read back unchanged."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.calcium_imaging import calcium_imaging_processor as processor_module
from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor
from aceneurotools.calcium_imaging.motion_correction_record import (
    MOTION_CORRECTION_SHIFTS_FILENAME,
    load_motion_correction_shifts,
    motion_correction_arrays,
    save_motion_correction_shifts,
)
from aceneurotools.calcium_imaging.pipeline_results import ProcessingResult


def fake_mc(pw_rigid, fname=("movie.tif",)):
    rng = np.random.default_rng(0)
    return SimpleNamespace(
        shifts_rig=[tuple(row) for row in rng.normal(size=(50, 2))],
        x_shifts_els=rng.normal(size=(50, 4)).tolist() if pw_rigid else [],
        y_shifts_els=rng.normal(size=(50, 4)).tolist() if pw_rigid else [],
        total_template_rig=rng.random((16, 16)),
        total_template_els=rng.random((16, 16)) if pw_rigid else None,
        strides=(8, 8),
        overlaps=(4, 4),
        max_shifts=(3, 3),
        coord_shifts_els=[None] * 50,  # What CaImAn 1.13 stores; must be skipped, not crash.
        border_to_0=3,
        fname=list(fname),
    )


@pytest.mark.parametrize("pw_rigid", [False, True])
def test_shifts_round_trip_as_float32_with_patch_grid_and_source(tmp_path, pw_rigid):
    mc = fake_mc(pw_rigid)
    path = save_motion_correction_shifts(mc, tmp_path / "saved_movies", pw_rigid=pw_rigid, frame_rate=20.0)

    assert path == str(tmp_path / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME)
    saved = load_motion_correction_shifts(path)
    for name in ["shifts_rig", "total_template_rig"]:
        assert saved[name].dtype == np.float32
        np.testing.assert_allclose(saved[name], np.asarray(getattr(mc, name)), rtol=1e-6)
    np.testing.assert_array_equal(saved["strides"], [8, 8])
    np.testing.assert_array_equal(saved["overlaps"], [4, 4])
    np.testing.assert_array_equal(saved["max_shifts"], [3, 3])
    assert saved["source_movie"].tolist() == ["movie.tif"]
    assert bool(saved["pw_rigid"]) is pw_rigid
    assert float(saved["frame_rate"]) == 20.0
    assert int(saved["border_to_0"]) == 3
    assert "coord_shifts_els" not in saved
    if pw_rigid:
        for name in ["x_shifts_els", "y_shifts_els", "total_template_els"]:
            assert saved[name].dtype == np.float32
            np.testing.assert_allclose(saved[name], np.asarray(getattr(mc, name)), rtol=1e-6)
    else:
        # Empty piecewise lists and missing templates are omitted rather than saved as empty arrays.
        assert {"x_shifts_els", "y_shifts_els", "total_template_els"}.isdisjoint(saved)


def test_missing_and_unconvertible_attributes_are_skipped():
    assert set(motion_correction_arrays(SimpleNamespace(), pw_rigid=False)) == {"pw_rigid"}
    odd = SimpleNamespace(shifts_rig=["left", "right"], strides="wide", fname="single.tif")
    arrays = motion_correction_arrays(odd, pw_rigid=True)
    assert set(arrays) == {"pw_rigid", "source_movie"}
    assert arrays["source_movie"].tolist() == ["single.tif"]


def test_processing_result_keeps_positional_compatibility():
    result = ProcessingResult(None, None, None, None, None)
    assert result.motion_correction_shifts_filepath is None


# Real CaImAn motion correction on a synthetic movie with known shifts.


def synthetic_movie(path):
    import tifffile

    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[:64, :64]
    base = sum(np.exp(-((yy - y) ** 2 + (xx - x) ** 2) / 8.0) for y, x in rng.uniform(10, 54, size=(12, 2)))
    known = np.array([(int(2 * np.sin(t / 10)), int(2 * np.cos(t / 13))) for t in range(120)])
    frames = [np.roll(base, tuple(shift), axis=(0, 1)) * 100 + 5 + rng.normal(0, 0.5, (64, 64)) for shift in known]
    tifffile.imwrite(path, np.asarray(frames, dtype=np.float32))
    return known


@pytest.mark.parametrize("pw_rigid", [False, True])
def test_real_motion_correction_shifts_recover_the_injected_motion(tmp_path, monkeypatch, pw_rigid):
    monkeypatch.setenv("CAIMAN_TEMP", str(tmp_path / "caiman-temp"))
    (tmp_path / "caiman-temp").mkdir()
    from caiman.motion_correction import MotionCorrect

    movie = str(tmp_path / "synthetic.tif")
    known = synthetic_movie(movie)
    mc = MotionCorrect(
        movie, dview=None, max_shifts=(4, 4), strides=(32, 32), overlaps=(16, 16),
        max_deviation_rigid=3, pw_rigid=pw_rigid, border_nan="copy",
    )
    mc.motion_correct(save_movie=False)
    saved = load_motion_correction_shifts(save_motion_correction_shifts(mc, tmp_path, pw_rigid=pw_rigid, frame_rate=20))

    # CaImAn reports the correction, which is the negative of the injected displacement.
    assert saved["shifts_rig"].shape == (120, 2)
    assert np.max(np.abs(saved["shifts_rig"] + known)) < 0.5
    assert saved["source_movie"].tolist() == [movie]
    if pw_rigid:
        assert saved["x_shifts_els"].shape[0] == 120 and saved["x_shifts_els"].shape == saved["y_shifts_els"].shape
        assert saved["total_template_els"].shape == saved["total_template_rig"].shape == (64, 64)
    else:
        assert "x_shifts_els" not in saved


# The processor writes the file during motion correction and reports it.


class FakeOpts:
    def __init__(self, pw_rigid=False):
        self.values = {("motion", "pw_rigid"): pw_rigid, ("patch", "border_pix"): 0, ("data", "fnames"): ["movie.mmap"]}

    def get(self, group, key):
        return self.values[(group, key)]

    def change_params(self, params):
        pass


def bare_processor(tmp_path, monkeypatch, metadata=True, pw_rigid=False):
    manager = SimpleNamespace(
        metadata={"calcium imaging directory": str(tmp_path / "recording")} if metadata else None,
        opts_caiman=FakeOpts(pw_rigid),
        fr=20.0,
        motion_correction_shifts_filepath=None,
        motion_corrected_movie_filepath=None,
        movie=None,
        CNMFE_obj=None,
        estimates_filepath=None,
    )
    processor = object.__new__(CalciumImagingProcessor)
    processor.data_manager = manager
    processor.preprocessed_movie = None
    calls = []
    mc = fake_mc(pw_rigid)
    mc.mmap_file = ["corrected.mmap"]

    def apply(opts, dview=None):
        calls.append("apply")
        return mc, opts

    monkeypatch.setattr(processor, "_apply_motion_correction", apply)
    monkeypatch.setattr(processor, "_add_temp_mmap_to_opts_caiman", lambda *args, **kwargs: manager.opts_caiman)
    return processor, manager, calls


def test_motion_correction_writes_shifts_next_to_the_estimates(tmp_path, monkeypatch, capsys):
    processor, manager, calls = bare_processor(tmp_path, monkeypatch, pw_rigid=True)
    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)

    expected = tmp_path / "recording" / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME
    assert calls == ["apply"]
    assert manager.motion_correction_shifts_filepath == str(expected)
    saved = load_motion_correction_shifts(expected)
    assert bool(saved["pw_rigid"]) is True and float(saved["frame_rate"]) == 20.0
    assert "x_shifts_els" in saved
    assert f"Saved motion-correction shifts to {expected}" in capsys.readouterr().out


def test_no_shifts_file_without_motion_correction(tmp_path, monkeypatch):
    processor, manager, calls = bare_processor(tmp_path, monkeypatch)
    processor.motion_correction_manager(manager, None, apply_motion_correction=False, inspect_motion_correction=False)
    assert calls == [] and manager.motion_correction_shifts_filepath is None
    assert not (tmp_path / "recording").exists()


def test_no_shifts_file_without_metadata(tmp_path, monkeypatch):
    processor, manager, calls = bare_processor(tmp_path, monkeypatch, metadata=False)
    processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
    assert calls == ["apply"] and manager.motion_correction_shifts_filepath is None


def test_a_failed_shifts_write_warns_and_processing_continues(tmp_path, monkeypatch, capsys):
    processor, manager, calls = bare_processor(tmp_path, monkeypatch)

    def refuse(*args, **kwargs):
        raise PermissionError("read-only recording folder")

    monkeypatch.setattr(processor_module, "save_motion_correction_shifts", refuse)
    returned = processor.motion_correction_manager(manager, None, apply_motion_correction=True, inspect_motion_correction=False)
    assert returned is manager and manager.motion_correction_shifts_filepath is None
    assert "Warning: motion-correction shifts could not be saved: read-only recording folder" in capsys.readouterr().out


def test_processing_result_reports_the_shifts_file(tmp_path, monkeypatch):
    processor, manager, _ = bare_processor(tmp_path, monkeypatch)
    monkeypatch.setattr(processor, "cnmfe_parameter_handler", lambda dm, plot_params=False: (dm, np.zeros((3, 4, 4))))
    monkeypatch.setattr(processor, "_save_processed_data", lambda dm, *args: dm)
    monkeypatch.setattr(processor_module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(processor_module.cm, "stop_server", lambda dview=None: None)

    processor.process_calcium_movie(parallel=False, apply_motion_correction=True, run_CNMFE=False, save_estimates=False)
    expected = str(Path(tmp_path) / "recording" / "saved_movies" / MOTION_CORRECTION_SHIFTS_FILENAME)
    assert processor.result.motion_correction_shifts_filepath == expected
    assert manager.motion_correction_shifts_filepath == expected
