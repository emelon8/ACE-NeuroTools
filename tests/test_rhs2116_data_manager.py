"""Regression tests for RHS2116DataManager loading.

Guards the fix for the silent 3M-sample truncation: the full recording is now
loaded by default, and an explicit ``max_samples`` cap truncates *with a
warning* instead of dropping data silently.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager

ACQ_CLK_HZ = 30000
TARGET_FS = 30
N_SAMPLES = 5000
NUM_CHANNELS = 32


@pytest.fixture
def rhs2116_dir(tmp_path: Path) -> Path:
    """Build a minimal synthetic RHS2116 recording (clock + ac + dc + start-time)."""
    suffix = "0"
    (tmp_path / f"start-time_{suffix}.csv").write_text(
        f"2024-01-01T00:00:00,{ACQ_CLK_HZ},1024,1024\n"
    )
    # Clock ticks increment by acq/target so the effective rate resolves to TARGET_FS.
    clock = np.arange(N_SAMPLES, dtype=np.uint64) * (ACQ_CLK_HZ // TARGET_FS)
    clock.tofile(tmp_path / f"rhs2116pair-clock_{suffix}.raw")
    # AC: (N, 32) uint16, interleaved sample-major.
    rng = np.random.default_rng(0)
    ac = rng.integers(0, 65535, size=(N_SAMPLES, NUM_CHANNELS)).astype(np.uint16)
    ac.tofile(tmp_path / f"rhs2116pair-ac_{suffix}.raw")
    # DC file must exist (validated on import) but is not read during processing.
    (tmp_path / f"rhs2116pair-dc_{suffix}.raw").write_bytes(b"\x00" * 16)
    return tmp_path


def _manager(directory: Path) -> RHS2116DataManager:
    return RHS2116DataManager(
        ephys_directory=str(directory),
        auto_import_ephys_block=False,
        auto_process_block=False,
        auto_compute_phases=False,
        level="WARNING",
    )


def test_full_recording_loaded_by_default(rhs2116_dir: Path):
    m = _manager(rhs2116_dir)
    m.import_ephys_block(str(rhs2116_dir))
    m.process_ephys_block_to_channels()

    assert len(m.channels) == NUM_CHANNELS
    ch = m.channels["RHS2116_AC_0"]
    # Every available sample is read — nothing is dropped.
    assert ch.signal.shape[0] == N_SAMPLES
    assert ch.time_vector.shape[0] == N_SAMPLES
    assert ch.sampling_rate == pytest.approx(TARGET_FS, rel=1e-6)


def test_max_samples_caps_and_warns(rhs2116_dir: Path):
    m = _manager(rhs2116_dir)
    m.import_ephys_block(str(rhs2116_dir))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        m.process_ephys_block_to_channels(max_samples=1000)

    ch = m.channels["RHS2116_AC_0"]
    assert ch.signal.shape[0] == 1000
    assert ch.time_vector.shape[0] == 1000
    messages = [str(w.message) for w in caught]
    assert any("Truncating RHS2116" in msg for msg in messages)


def test_max_samples_above_length_is_noop(rhs2116_dir: Path):
    m = _manager(rhs2116_dir)
    m.import_ephys_block(str(rhs2116_dir))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        m.process_ephys_block_to_channels(max_samples=10 * N_SAMPLES)
    ch = m.channels["RHS2116_AC_0"]
    assert ch.signal.shape[0] == N_SAMPLES
    # No truncation warning when the cap exceeds the recording length.
    assert not any("Truncating RHS2116" in str(w.message) for w in caught)


def test_single_channel_selection_by_index(rhs2116_dir: Path):
    m = _manager(rhs2116_dir)
    m.import_ephys_block(str(rhs2116_dir))
    m.process_ephys_block_to_channels(channels=[0])
    assert list(m.channels.keys()) == ["RHS2116_AC_0"]
