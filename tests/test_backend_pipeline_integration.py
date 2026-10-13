"""Real backend pipeline checks against synthetic inputs with known answers."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

pytestmark = pytest.mark.requires_caiman


@pytest.fixture
def movie_project(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    # FFV1 is lossless: expected pixels are defined before encoding.
    frames = np.stack([(np.arange(24)[:, None] * 5 + np.arange(32)[None, :] + i).astype(np.uint8) for i in range(20)])
    for name, start, stop in [("2.avi", 0, 7), ("10.avi", 7, 20)]:
        writer = cv2.VideoWriter(str(raw / name), cv2.VideoWriter_fourcc(*"FFV1"), 10, (32, 24), False)
        assert writer.isOpened(), "The lossless synthetic-video codec is unavailable."
        try:
            for frame in frames[start:stop]:
                writer.write(frame)
        finally:
            writer.release()
    (raw / "metaData.json").write_text(json.dumps({"frameRate": 10}))
    (raw / "timeStamps.csv").write_text(
        "Frame Number,Time Stamp (ms),Buffer Index\n" + "".join(f"{i},{i * 100},0\n" for i in range(20))
    )
    with (tmp_path / "experiments.csv").open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows(
            [["line number", "id", "date (YYMMDD)", "calcium imaging directory"], [1, "001", "261001", "raw"]]
        )
    return tmp_path, frames


@pytest.mark.integration
@pytest.mark.parametrize("coords", [None, [2, 3, 20, 15]])
def test_mean_fluorescence_api_and_real_cli_match_pixels_and_preserve_inputs(movie_project, tmp_path, coords):
    from aceneurotools.miniscope import ucla_data_manager  # noqa: F401 — register the recording adapter
    from aceneurotools.pipelines.compute import ComputePipeline

    project, frames = movie_project
    with (project / "analysis_parameters.csv").open("w", newline="") as handle:
        csv.writer(handle).writerows([["line number", "crop", "crop_coords"], [1, bool(coords), coords or ""]])
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in project.rglob("*") if path.is_file()}
    output = tmp_path / "api-output"
    result = ComputePipeline().run(
        project_path=project,
        data_path=project,
        lab_config=None,
        calcium_signal_dir=output,
        line_nums=[1],
        headless=True,
    )
    assert set(result) == {1}
    values = frames if coords is None else frames[:, 24 - coords[3] : 24 - coords[1], coords[0] : coords[2]]
    expected = values.mean(axis=(1, 2))
    with np.load(result[1], allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive["meanFluorescence"], expected)
    config = tmp_path / "lab_config.json"
    config.write_text(
        json.dumps(
            {
                "primary_channel": "EEG",
                "freq_range": [0.5, 4],
                "conditions": {"control": {"subjects": [1], "is_drug": False}},
                "time_windows": {"1": [[0, 0.5], [0.5, 1]]},
            }
        )
    )
    cli_output = tmp_path / "cli-output"
    command = [
        sys.executable,
        "-m",
        "aceneurotools.pipelines.compute",
        "--project-path",
        str(project),
        "--data-path",
        str(project),
        "--lab-config",
        str(config),
        "--calcium-signal-dir",
        str(cli_output),
        "--line-nums",
        "1",
        "--headless",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"), "MPLBACKEND": "Agg"},
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    with np.load(cli_output / "meanFluorescence_1.npz", allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive["meanFluorescence"], expected)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items())


@pytest.mark.integration
def test_real_ephys_pipeline_filters_and_phases_a_synthetic_hardware_recording(tmp_path):
    from scipy.signal import butter, filtfilt, hilbert

    from aceneurotools.pipelines.ephys import EphysPipeline

    raw = tmp_path / "raw"
    raw.mkdir()
    count, rate = 600, 30
    waveform = np.round(32768 + 1000 * np.sin(2 * np.pi * np.arange(count) / rate)).astype(np.uint16)
    np.tile(waveform[:, None], (1, 32)).tofile(raw / "rhs2116pair-ac_0.raw")
    (np.arange(count, dtype=np.uint64) * 1000).tofile(raw / "rhs2116pair-clock_0.raw")
    (raw / "rhs2116pair-dc_0.raw").write_bytes(b"\0" * 16)
    (raw / "start-time_0.csv").write_text("2024-01-01T00:00:00,30000,1024,1024\n")
    (tmp_path / "experiments.csv").write_text("line number,id,ephys directory\n1,R1,raw\n")
    before = {p: p.read_bytes() for p in raw.iterdir()}
    pipeline = EphysPipeline()
    pipeline.run(
        line_num=1,
        project_path=tmp_path,
        data_path=tmp_path,
        channel_name="RHS2116_AC_0",
        filter_type="butter",
        filter_range=[0.5, 4],
        compute_phases=True,
        headless=True,
    )
    channel = pipeline.ephys_data_manager.get_channel("RHS2116_AC_0")
    assert channel.signal.shape == channel.time_vector.shape == (count,)
    assert channel.sampling_rate == pytest.approx(rate)
    np.testing.assert_allclose(channel.time_vector, np.arange(count) / rate, atol=1e-12)
    b, a = butter(2, [0.5, 4], btype="band", fs=rate)
    expected = filtfilt(b, a, channel.signal)
    np.testing.assert_allclose(channel.signal_filtered, expected, rtol=1e-5, atol=1e-5)
    # The current backend defines phases on the acquired signal. Keep that
    # scientific contract visible separately from optional bandpass filtering.
    np.testing.assert_allclose(channel.phases, np.angle(hilbert(channel.signal)), rtol=1e-5, atol=1e-5)
    assert all(p.read_bytes() == data for p, data in before.items())
