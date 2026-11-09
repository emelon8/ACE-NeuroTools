"""The worked examples in docs/guides/loader_definitions.md must keep working.

The guide includes these files verbatim, so a change that breaks them breaks
the documentation:

* examples/loaders/*.json -- loader definitions for systems without a built-in loader
* examples/custom_ephys_loader.py -- a Python loader, used through the real ephys loader
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from aceneurotools.shared.loader_definitions import (
    definition_matches,
    load_definition,
    load_project_definitions,
    resolve_files,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_LOADERS = sorted((ROOT / "examples" / "loaders").glob("*.json"))
PYTHON_EXAMPLE = ROOT / "examples" / "custom_ephys_loader.py"
GUIDE = ROOT / "docs" / "guides" / "loader_definitions.md"


def _touch(folder: Path, *names: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(b"")
    return folder


# ── definition examples ──────────────────────────────────────────────────────

def test_there_are_examples_for_both_backends() -> None:
    backends = {load_definition(path).backend for path in EXAMPLE_LOADERS}
    assert backends == {"neo", "raw_binary"}


@pytest.mark.parametrize("path", EXAMPLE_LOADERS, ids=lambda p: p.stem)
def test_example_definition_is_valid_and_included_in_the_guide(path: Path) -> None:
    definition = load_definition(path)  # raises on any problem, checks name == file stem
    assert definition.name == path.stem
    assert f'--8<-- "examples/loaders/{path.name}"' in GUIDE.read_text(encoding="utf-8")


def test_examples_work_as_project_definitions(tmp_path: Path) -> None:
    from aceneurotools.cli import _builtin_ephys_loaders

    folder = tmp_path / "loaders"
    folder.mkdir()
    for path in EXAMPLE_LOADERS:
        (folder / path.name).write_bytes(path.read_bytes())
    reserved = [name for name, _ in _builtin_ephys_loaders()]
    definitions, problems = load_project_definitions(tmp_path, reserved_names=reserved)
    assert problems == {}
    assert sorted(d.name for d in definitions) == sorted(p.stem for p in EXAMPLE_LOADERS)


def test_intan_example_detects_and_resolves(tmp_path: Path) -> None:
    definition = load_definition(ROOT / "examples" / "loaders" / "intan-rhd.json")
    rec = _touch(tmp_path / "rec", "session.rhd", "notes.txt")
    assert definition_matches(definition, rec)
    assert resolve_files(definition, rec).files == {"recording": rec / "session.rhd"}
    assert not definition_matches(definition, _touch(tmp_path / "nlx", "Events.nev"))
    # Channels are named per signal only when neo splits the streams.
    assert definition.reader.read_block == {"signal_group_mode": "split-all"}

    two = _touch(tmp_path / "two", "a.rhd", "b.rhd")
    with pytest.raises(ValueError, match="matches several files"):
        resolve_files(definition, two)


def test_flat_binary_example_detects_and_names_channels(tmp_path: Path) -> None:
    definition = load_definition(ROOT / "examples" / "loaders" / "flat-binary-16ch.json")
    rec = _touch(tmp_path / "rec", "recording.dat")
    assert definition_matches(definition, rec)
    assert resolve_files(definition, rec).files == {"signal": rec / "recording.dat"}
    assert not definition_matches(definition, _touch(tmp_path / "mixed", "x.dat", "Events.nev"))
    assert [definition.channels.name_for(i) for i in (0, 15)] == ["CH0", "CH15"]
    assert definition.time.sampling_rate_hz == 30000


# ── Python loader example ────────────────────────────────────────────────────

@pytest.fixture
def numpy_loader():
    """Import the example module, and unregister its loader afterwards."""
    from aceneurotools.ephys.ephys_data_manager import EphysDataManager

    before = list(EphysDataManager._registry)
    spec = importlib.util.spec_from_file_location("custom_ephys_loader_example", PYTHON_EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        yield module.NumpyExportDataManager
    finally:
        EphysDataManager._registry[:] = before


def _numpy_recording(folder: Path, *, n: int = 2000, fs: float = 1000.0, sync: bool = True) -> Path:
    (folder / "channels").mkdir(parents=True)
    times = np.arange(n) / fs
    np.save(folder / "timestamps.npy", times)
    np.save(folder / "channels" / "LFP1.npy", np.sin(2 * np.pi * 5 * times))
    np.save(folder / "channels" / "EEG1.npy", np.cos(2 * np.pi * 3 * times))
    if sync:
        np.save(folder / "sync.npy", np.array([0.1, 0.2, 0.3]))
    return folder


def test_python_example_registers_last_and_is_chosen_for_its_folders(numpy_loader, tmp_path: Path) -> None:
    from aceneurotools.ephys.ephys_data_manager import EphysDataManager

    assert EphysDataManager._registry[-1] is numpy_loader  # tried after the built-ins
    rec = _numpy_recording(tmp_path / "rec")
    manager = EphysDataManager.create(ephys_directory=rec, auto_compute_phases=False)
    assert isinstance(manager, numpy_loader)
    assert sorted(manager.channels) == ["EEG1", "LFP1"]  # all channels when none are requested
    assert not numpy_loader.can_handle(_touch(tmp_path / "nlx", "Events.nev"))


def test_python_example_loads_through_the_pipeline_loader(numpy_loader, tmp_path: Path) -> None:
    """The documented route: import the module, then run the normal ephys loading."""
    from aceneurotools.ephys.ephys_loader import load_ephys_for_analysis

    project = tmp_path / "project"
    project.mkdir()
    (project / "experiments.csv").write_text(
        "line number,calcium imaging directory,ephys directory,LFP and EEG CSCs\n1,,rec,LFP1\n"
    )
    _numpy_recording(tmp_path / "data" / "rec")

    manager = load_ephys_for_analysis(
        line_num=1, project_path=project, data_path=tmp_path / "data", channel_names=["LFP1"]
    )
    assert isinstance(manager, numpy_loader)
    assert list(manager.channels) == ["LFP1"]
    channel = manager.get_channel("LFP1")
    assert channel.signal.shape == channel.time_vector.shape == (2000,)
    assert channel.sampling_rate == pytest.approx(1000.0)
    np.testing.assert_array_equal(manager.get_sync_timestamps(), [0.1, 0.2, 0.3])


def test_python_example_reports_mismatched_lengths_and_missing_sync(numpy_loader, tmp_path: Path) -> None:
    rec = _numpy_recording(tmp_path / "rec", sync=False)
    np.save(rec / "channels" / "BAD.npy", np.zeros(5))
    manager = numpy_loader(ephys_directory=rec, auto_process_block=False, auto_compute_phases=False)
    assert manager.get_sync_timestamps().size == 0
    with pytest.raises(ValueError, match="BAD.npy has 5 samples but timestamps.npy has 2000"):
        manager.process_ephys_block_to_channels(channels=["BAD"])


def test_python_example_is_included_in_the_guide() -> None:
    assert '--8<-- "examples/custom_ephys_loader.py"' in GUIDE.read_text(encoding="utf-8")
