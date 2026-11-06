"""Tests for ephys loader definitions (``aceneurotools.shared.loader_definitions``).

The example definitions in ``tests/data/loaders`` describe the two built-in
ephys loaders. Besides format checks, these tests compare them with the
built-in managers so that the examples, and the schema they exercise, stay
able to express those loaders exactly.
"""

from __future__ import annotations

import copy
import json
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aceneurotools.shared import loader_definitions as ld
from aceneurotools.shared.loader_definitions import (
    SCHEMA,
    DefinitionError,
    DefinitionProblem,
    LoaderDefinition,
    check_relative_glob,
    definition_json_schema,
    definition_matches,
    load_definition,
    load_project_definitions,
    matching_files,
    parse_definition,
    resolve_files,
    validate_definition,
)

EXAMPLES = Path(__file__).parent / "data" / "loaders"
NEURALYNX = EXAMPLES / "neuralynx.json"
RHS2116 = EXAMPLES / "rhs2116.json"


def _raw(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _paths(problems: list[DefinitionProblem]) -> list[str]:
    return [p.path for p in problems]


# ─────────────────────────────────────────────────────────────────────────────
# Examples
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [NEURALYNX, RHS2116], ids=["neuralynx", "rhs2116"])
def test_examples_validate_and_load(path: Path) -> None:
    assert validate_definition(_raw(path)) == []
    definition = load_definition(path)
    assert definition.name == path.stem
    assert definition.schema == SCHEMA
    assert definition.modality == "ephys"
    assert definition.source == path
    assert definition.raw == _raw(path)


def test_neuralynx_example_fields() -> None:
    d = load_definition(NEURALYNX)
    assert isinstance(d.reader, ld.NeoReader)
    assert d.backend == "neo"
    assert d.reader.io == "NeuralynxIO"
    assert d.reader.path_argument == "dirname"
    assert d.reader.path_from == ld.PathFrom("file_parent", "events")
    assert d.reader.read_block == {"signal_group_mode": "split-all"}
    assert d.reader.args == {}
    (events,) = d.files
    assert events.pattern == "**/Events*.nev"
    assert events.pick == "oldest_modified"
    assert events.exclude_dirs == ("saved_movies",)
    assert d.time.source == "reader"
    assert d.channels == ld.ChannelSpec(source="reader", default="none")
    assert d.sync.strategy == "event_labels"
    assert len(d.sync.labels) == 2


def test_rhs2116_example_matches_manager_constants() -> None:
    from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager as M

    d = load_definition(RHS2116)
    assert isinstance(d.reader, ld.RawBinaryReader)
    assert d.reader.dtype == "uint16"
    assert d.reader.channel_count == M.NUM_CHANNELS
    assert d.reader.gain == M.AC_UV_MULTIPLIER
    # The manager computes the offset; the definition stores the same float.
    assert d.reader.offset == -(M.AC_OFFSET * M.AC_UV_MULTIPLIER)
    assert d.reader.byte_offset == 0
    assert d.reader.output_dtype == "float32"
    assert d.time.clock_dtype == "uint64"
    assert d.time.ticks_per_second == ld.CsvValue("start_time", 1, 0)
    assert d.time.effective_rate == ld.EffectiveRate("median_interval", 10000)
    assert d.channels.name_for(7) == "RHS2116_AC_7"
    assert d.channels.select_by_index is True
    assert d.channels.default == "all"
    assert d.sync.strategy == "shared_clock"


# ─────────────────────────────────────────────────────────────────────────────
# Parity with the built-in managers
# ─────────────────────────────────────────────────────────────────────────────

LAYOUTS: dict[str, list[str]] = {
    "empty": [],
    "neuralynx": ["Events.nev", "CSC1.ncs"],
    "other_nev": ["Other.nev"],
    "nev_in_subfolder": ["sub/Events.nev"],
    "rhs2116": [
        "start-time_0.csv",
        "rhs2116pair-ac_0.raw",
        "rhs2116pair-dc_0.raw",
        "rhs2116pair-clock_0.raw",
    ],
    "any_raw": ["something.raw"],
    "both": ["Events.nev", "x.raw"],
    "unrelated": ["notes.txt", "movie.avi"],
}


def _make_layout(root: Path, files: list[str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for rel in files:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"")
    return root


@pytest.mark.parametrize("layout", sorted(LAYOUTS))
def test_example_detection_matches_builtin_can_handle(tmp_path: Path, layout: str) -> None:
    from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
    from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager

    folder = _make_layout(tmp_path / layout, LAYOUTS[layout])
    assert definition_matches(load_definition(NEURALYNX), folder) == NeuralynxDataManager.can_handle(folder)
    assert definition_matches(load_definition(RHS2116), folder) == RHS2116DataManager.can_handle(folder)


def test_missing_folder_matches_nothing(tmp_path: Path) -> None:
    from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager

    missing = tmp_path / "missing"
    assert definition_matches(load_definition(NEURALYNX), missing) is False
    assert NeuralynxDataManager.can_handle(missing) is False
    assert all(v == [] for v in matching_files(load_definition(NEURALYNX), missing).values())


def test_neuralynx_events_file_resolves_like_manager(tmp_path: Path) -> None:
    from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager

    folder = _make_layout(
        tmp_path / "rec",
        ["saved_movies/Events.nev", "sub/Events_old.nev", "Events.nev", "EventsX.txt", "CSC1.ncs"],
    )
    # Oldest overall is excluded (saved_movies); next oldest is in a subfolder.
    os.utime(folder / "saved_movies" / "Events.nev", (500, 500))
    os.utime(folder / "sub" / "Events_old.nev", (1_000, 1_000))
    os.utime(folder / "Events.nev", (2_000, 2_000))

    manager = NeuralynxDataManager.__new__(NeuralynxDataManager)
    expected = Path(manager._find_ephys_file_path(folder))

    resolved = resolve_files(load_definition(NEURALYNX), folder)
    assert resolved.files["events"] == expected == folder / "sub" / "Events_old.nev"
    # path_from file_parent -> NeuralynxIO(dirname=<folder holding the events file>)
    assert resolved.files["events"].parent == folder / "sub"


def test_neuralynx_sync_labels_select_same_events_as_manager() -> None:
    from aceneurotools.ephys.channel import Channel
    from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager

    labels = load_definition(NEURALYNX).sync.labels
    events = {
        "labels": np.array([labels[0], "Starting Recording", labels[1], "TTL Input on AcqSystem1_0 board 0 port 1 value (0x0001).", labels[0]]),
        "timestamps": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
    }
    manager = NeuralynxDataManager.__new__(NeuralynxDataManager)
    manager.channels = {"CSC1": Channel("CSC1", np.zeros(3), 1.0, np.arange(3.0), events)}

    expected = manager.get_sync_timestamps()
    mask = np.isin(events["labels"].astype(str), labels)
    np.testing.assert_array_equal(events["timestamps"][mask], expected)
    np.testing.assert_array_equal(expected, [1.0, 3.0, 5.0])


@pytest.fixture
def rhs2116_dir(tmp_path: Path) -> Path:
    """Synthetic RHS2116 recording, as in test_rhs2116_data_manager.py."""
    folder = tmp_path / "rhs"
    folder.mkdir()
    (folder / "start-time_7.csv").write_text("2024-01-01T00:00:00,30000,1024,1024\n")
    (folder / "start-time_miniscope_9.csv").write_text("2024-01-01T00:00:00,30000,1024,1024\n")
    n = 3000
    (np.arange(n, dtype=np.uint64) * 1000).tofile(folder / "rhs2116pair-clock_7.raw")
    rng = np.random.default_rng(0)
    rng.integers(0, 65535, size=(n, 32)).astype(np.uint16).tofile(folder / "rhs2116pair-ac_7.raw")
    (folder / "rhs2116pair-dc_7.raw").write_bytes(b"\x00" * 16)
    return folder


def _reference_raw_binary_load(definition: LoaderDefinition, folder: Path) -> dict[str, tuple[np.ndarray, float, np.ndarray]]:
    """Read channels the way the definition says, as a generic loader would.

    This is a test-only interpretation used to prove the format can express
    the built-in RHS2116 loader exactly; it is not library code.
    """
    from neo.rawio import RawBinarySignalRawIO

    reader = definition.reader
    time = definition.time
    assert isinstance(reader, ld.RawBinaryReader)
    files = resolve_files(definition, folder).files

    assert isinstance(time.ticks_per_second, ld.CsvValue)
    row = np.genfromtxt(
        files[time.ticks_per_second.csv_file], delimiter=",", dtype=str,
        skip_header=time.ticks_per_second.header_rows,
    )
    ticks_per_second = float(int(row[time.ticks_per_second.column]))

    assert time.clock_file is not None and time.clock_dtype is not None
    times = np.fromfile(files[time.clock_file], dtype=time.clock_dtype) / ticks_per_second
    raw = RawBinarySignalRawIO(
        filename=str(files[reader.signal_file]), dtype=reader.dtype, sampling_rate=ticks_per_second,
        nb_channel=reader.channel_count, bytesoffset=reader.byte_offset,
        signal_gain=reader.gain, signal_offset=reader.offset,
    )
    raw.parse_header()
    n = min(int(raw.get_signal_size(block_index=0, seg_index=0, stream_index=0)), len(times))
    chunk = raw.get_analogsignal_chunk(block_index=0, seg_index=0, i_start=0, i_stop=n, stream_index=0)
    values = raw.rescale_signal_raw_to_float(chunk, dtype=np.dtype(reader.output_dtype), stream_index=0)

    assert time.effective_rate is not None
    k = min(time.effective_rate.first_samples, len(times))
    rate = float(1.0 / np.median(np.diff(times[:k]))) if k > 1 else ticks_per_second
    times = times[: values.shape[0]]
    return {definition.channels.name_for(i): (values[:, i], rate, times) for i in range(reader.channel_count)}


def test_rhs2116_definition_reproduces_manager_channels(rhs2116_dir: Path) -> None:
    from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager

    manager = RHS2116DataManager(
        ephys_directory=str(rhs2116_dir), auto_import_ephys_block=True, auto_process_block=True,
        auto_compute_phases=False, level="WARNING",
    )
    definition = load_definition(RHS2116)

    resolved = resolve_files(definition, rhs2116_dir)
    assert resolved.variables == {"suffix": manager.suffix}
    assert resolved.files["clock"] == manager.clock_path
    assert resolved.files["ac"] == manager.ac_path
    assert resolved.files["dc"] == manager.dc_path

    reference = _reference_raw_binary_load(definition, rhs2116_dir)
    assert list(reference) == list(manager.channels)
    for name, (signal, rate, times) in reference.items():
        channel = manager.channels[name]
        assert signal.dtype == channel.signal.dtype
        np.testing.assert_array_equal(signal, channel.signal)
        assert rate == channel.sampling_rate
        np.testing.assert_array_equal(times, channel.time_vector)
        assert channel.events == {"labels": [], "timestamps": []}
    assert manager.get_sync_timestamps().size == 0  # shared_clock: no TTL


# ─────────────────────────────────────────────────────────────────────────────
# Validation rules: each has a failing case
# ─────────────────────────────────────────────────────────────────────────────

Mutation = Callable[[dict[str, Any]], None]


def _set(path: str, value: Any) -> Mutation:
    def apply(doc: dict[str, Any]) -> None:
        *parents, last = _split(path)
        target: Any = doc
        for key in parents:
            target = target[key]
        target[last] = value
    return apply


def _delete(path: str) -> Mutation:
    def apply(doc: dict[str, Any]) -> None:
        *parents, last = _split(path)
        target: Any = doc
        for key in parents:
            target = target[key]
        del target[last]
    return apply


def _split(path: str) -> list[str | int]:
    return [int(p) if p.isdigit() else p for p in re.split(r"\.|\[|\]\.?", path) if p != ""]


def _mutated(base: Path, *mutations: Mutation) -> dict[str, Any]:
    doc = copy.deepcopy(_raw(base))
    for m in mutations:
        m(doc)
    return doc


# (id, base example, mutations, expected problem path, message fragment, schema can express it)
INVALID_CASES: list[tuple[str, Path, list[Mutation], str, str, bool]] = [
    ("missing-required", NEURALYNX, [_delete("sync")], "sync", "required", True),
    ("unknown-top-key", NEURALYNX, [_set("lable", "x")], "lable", "did you mean 'label'", True),
    ("unknown-nested-key", RHS2116, [_set("reader.gian", 1.0)], "reader.gian", "did you mean 'gain'", True),
    ("wrong-schema", NEURALYNX, [_set("schema", "loader")], "schema", "must be 'ace-loader/1'", True),
    ("future-schema", NEURALYNX, [_set("schema", "ace-loader/2")], "schema", "unsupported version", True),
    ("name-not-kebab", NEURALYNX, [_set("name", "My_Rig")], "name", "kebab-case", True),
    ("name-too-long", NEURALYNX, [_set("name", "a" * 65)], "name", "at most", True),
    ("empty-label", NEURALYNX, [_set("label", "  ")], "label", "empty", True),
    ("calcium-modality", NEURALYNX, [_set("modality", "calcium")], "modality", "ephys", True),
    ("detect-empty", NEURALYNX, [_set("detect", {})], "detect", "at least one pattern", True),
    ("detect-absolute", NEURALYNX, [_set("detect.any_of", ["/data/*.nev"])], "detect.any_of[0]", "absolute", True),
    ("detect-drive", NEURALYNX, [_set("detect.any_of", ["C:/data/*.nev"])], "detect.any_of[0]", "drive letter", True),
    ("detect-dotdot", NEURALYNX, [_set("detect.any_of", ["../*.nev"])], "detect.any_of[0]", "'..'", True),
    ("detect-backslash", NEURALYNX, [_set("detect.any_of", ["sub\\*.nev"])], "detect.any_of[0]", "backslash", True),
    ("detect-home", NEURALYNX, [_set("detect.any_of", ["~/x.nev"])], "detect.any_of[0]", "home", True),
    ("detect-bad-doublestar", NEURALYNX, [_set("detect.any_of", ["a**/x.nev"])], "detect.any_of[0]", "whole segment", True),
    ("detect-placeholder", NEURALYNX, [_set("detect.any_of", ["{x}.nev"])], "detect.any_of[0]", "placeholder", False),
    ("detect-duplicates", NEURALYNX, [_set("detect.any_of", ["*.nev", "*.nev"])], "detect.any_of", "duplicates", True),
    ("bad-backend", NEURALYNX, [_set("reader.backend", "matlab")], "reader.backend", "neo, raw_binary", True),
    ("neo-unknown-io", NEURALYNX, [_set("reader.io", "NeuralynxIo")], "reader.io", "did you mean 'NeuralynxIO'", False),
    ("neo-denied-io", NEURALYNX, [_set("reader.io", "PickleIO"), _set("reader.path_argument", "filename")],
     "reader.io", "not allowed", False),
    ("neo-bad-path-argument", NEURALYNX, [_set("reader.path_argument", "filename_typo")],
     "reader.path_argument", "no 'filename_typo' argument", False),
    ("neo-path-in-args", NEURALYNX, [_set("reader.args", {"dirname": "x"})], "reader.args.dirname", "path argument", False),
    ("neo-unknown-arg", NEURALYNX, [_set("reader.args", {"use_cash": True})], "reader.args.use_cash", "no argument", False),
    ("neo-machine-path-arg", NEURALYNX, [_set("reader.args", {"cache_path": "/var/cache"})],
     "reader.args.cache_path", "machine path", False),
    ("neo-non-scalar-arg", NEURALYNX, [_set("reader.args", {"include_filenames": ["a.ncs"]})],
     "reader.args.include_filenames", "string, number", True),
    ("neo-unknown-read-block-arg", NEURALYNX, [_set("reader.read_block", {"signal_group": "split-all"})],
     "reader.read_block.signal_group", "no argument", False),
    ("neo-write-mode", NEURALYNX, [_set("reader.io", "NixIO"), _set("reader.path_argument", "filename"),
                                   _set("reader.args", {"mode": "ow"})], "reader.args.mode", "read-only", False),
    ("path-from-unknown-role", NEURALYNX, [_set("reader.path_from.file", "evnts")], "reader.path_from.file",
     "must name a role", False),
    ("path-from-bad-source", NEURALYNX, [_set("reader.path_from", {"source": "cwd"})], "reader.path_from.source",
     "recording_folder", True),
    ("file-absolute", RHS2116, [_set("reader.files[1].pattern", "/x/clock.raw")], "reader.files[1].pattern",
     "absolute", True),
    ("file-unknown-placeholder", RHS2116, [_set("reader.files[1].pattern", "clock_{sufix}.raw")],
     "reader.files[1].pattern", "not captured", False),
    ("file-placeholder-before-capture", RHS2116, [_set("reader.files[0].pattern", "start-time_{suffix}.csv")],
     "reader.files[0].pattern", "not captured", False),
    ("file-unbalanced-brace", RHS2116, [_set("reader.files[1].pattern", "clock_{suffix.raw")],
     "reader.files[1].pattern", "unmatched", False),
    ("file-duplicate-role", RHS2116, [_set("reader.files[2].role", "clock")], "reader.files[2].role",
     "already defined", False),
    ("file-bad-role", RHS2116, [_set("reader.files[2].role", "AC")], "reader.files[2].role", "lowercase", True),
    ("file-bad-pick", RHS2116, [_set("reader.files[0].pick", "newest")], "reader.files[0].pick", "first_listed", True),
    ("file-exclude-with-slash", RHS2116, [_set("reader.files[0].exclude_names", ["a/b"])],
     "reader.files[0].exclude_names[0]", "single name", True),
    ("file-exclude-dotdot-dir", NEURALYNX, [_set("reader.files[0].exclude_dirs", [".."])],
     "reader.files[0].exclude_dirs[0]", "folder name", True),
    ("file-required-not-bool", RHS2116, [_set("reader.files[3].required", "yes")], "reader.files[3].required",
     "true or false", True),
    ("capture-empty-split", RHS2116, [_set("reader.files[0].capture.split", "")], "reader.files[0].capture.split",
     "empty", True),
    ("capture-part-not-int", RHS2116, [_set("reader.files[0].capture.part", 1.5)], "reader.files[0].capture.part",
     "integer", True),
    ("capture-index-reserved", RHS2116, [_set("reader.files[0].capture.variable", "index")],
     "reader.files[0].capture.variable", "reserved", True),
    ("raw-unknown-signal-role", RHS2116, [_set("reader.signal_file", "acc")], "reader.signal_file", "must name a role",
     False),
    ("raw-bad-dtype", RHS2116, [_set("reader.dtype", "u2")], "reader.dtype", "uint16", True),
    ("raw-zero-channels", RHS2116, [_set("reader.channel_count", 0)], "reader.channel_count", "at least 1", True),
    ("raw-bool-channels", RHS2116, [_set("reader.channel_count", True)], "reader.channel_count", "integer", True),
    ("raw-zero-gain", RHS2116, [_set("reader.gain", 0)], "reader.gain", "not be 0", True),
    ("raw-negative-byte-offset", RHS2116, [_set("reader.byte_offset", -1)], "reader.byte_offset", "at least 0", True),
    ("raw-no-files", RHS2116, [_set("reader.files", [])], "reader.files", "at least the signal file", True),
    ("raw-bad-output-dtype", RHS2116, [_set("reader.output_dtype", "float16")], "reader.output_dtype", "float32", True),
    ("time-bad-source", RHS2116, [_set("time.source", "wallclock")], "time.source", "clock_file", True),
    ("time-reader-for-raw", RHS2116, [_set("time", {"source": "reader"})], "time.source", "raw_binary", False),
    ("time-clock-for-neo", NEURALYNX, [_set("time", {"source": "sample_index", "sampling_rate_hz": 1000})],
     "time.source", "neo readers", False),
    ("time-clock-unknown-role", RHS2116, [_set("time.clock_file", "clk")], "time.clock_file", "must name a role", False),
    ("time-bad-clock-dtype", RHS2116, [_set("time.clock_dtype", "uint16")], "time.clock_dtype", "uint64", True),
    ("time-negative-ticks", RHS2116, [_set("time.ticks_per_second", -5)], "time.ticks_per_second", "greater than 0",
     True),
    ("time-csv-negative-column", RHS2116, [_set("time.ticks_per_second.column", -1)], "time.ticks_per_second.column",
     "at least 0", True),
    ("time-rate-one-sample", RHS2116, [_set("time.effective_rate.first_samples", 1)],
     "time.effective_rate.first_samples", "at least 2", True),
    ("time-sample-index-rate", RHS2116, [_set("time", {"source": "sample_index", "sampling_rate_hz": 0})],
     "time.sampling_rate_hz", "greater than 0", True),
    ("channels-bad-default", RHS2116, [_set("channels.default", "first")], "channels.default", "all, none", True),
    ("channels-missing-default", RHS2116, [_delete("channels.default")], "channels.default", "required", True),
    ("channels-template-missing-index", RHS2116, [_set("channels.template", "AC_{i}")], "channels.template",
     "{index}", True),
    ("channels-template-other-placeholder", RHS2116, [_set("channels.template", "{suffix}_{index}")],
     "channels.template", "only '{index}'", False),
    ("channels-template-required", RHS2116, [_delete("channels.template")], "channels.template", "required", False),
    ("channels-reader-for-raw", RHS2116, [_set("channels", {"source": "reader", "default": "all"})],
     "channels.source", "template", False),
    ("channels-template-for-neo", NEURALYNX, [_set("channels.template", "x{index}")], "channels.template",
     "only when source is 'template'", False),
    ("sync-bad-strategy", NEURALYNX, [_set("sync", {"strategy": "ttl"})], "sync.strategy", "event_labels", True),
    ("sync-no-labels", NEURALYNX, [_set("sync.labels", [])], "sync.labels", "empty", True),
    ("sync-events-for-raw", RHS2116, [_set("sync", {"strategy": "event_labels", "labels": ["a"]})], "sync.strategy",
     "no events", False),
    ("sync-threshold-missing", RHS2116, [_set("sync", {"strategy": "digital_threshold", "channel": "RHS2116_AC_0"})],
     "sync.threshold", "required", True),
    ("sync-bad-edge", RHS2116, [_set("sync", {"strategy": "digital_threshold", "channel": "c", "threshold": 1,
                                              "edge": "up"})], "sync.edge", "rising", True),
    ("sync-shared-clock-extra", RHS2116, [_set("sync.labels", ["a"])], "sync.labels", "unknown key", True),
]


@pytest.mark.parametrize(
    "base,mutations,path,fragment",
    [case[1:5] for case in INVALID_CASES],
    ids=[case[0] for case in INVALID_CASES],
)
def test_invalid_definitions_are_reported(base: Path, mutations: list[Mutation], path: str, fragment: str) -> None:
    doc = _mutated(base, *mutations)
    problems = validate_definition(doc)
    matching = [p for p in problems if p.path == path]
    assert matching, f"no problem at {path!r}; got {problems}"
    assert any(fragment in p.message for p in matching), matching
    with pytest.raises(DefinitionError) as info:
        parse_definition(doc)
    assert info.value.problems == problems


@pytest.mark.parametrize("data", [None, [], "x", 3, True])
def test_non_object_documents_never_raise(data: object) -> None:
    assert validate_definition(data) == [DefinitionProblem("", "a loader definition must be a JSON object")]


def test_future_schema_reports_version_only() -> None:
    problems = validate_definition({"schema": "ace-loader/2", "whatever": 1})
    assert problems == [
        DefinitionProblem("schema", "unsupported version 'ace-loader/2'; this ACE-NeuroTools reads 'ace-loader/1' only")
    ]


def test_validate_reports_every_problem_at_once() -> None:
    doc = _mutated(NEURALYNX, _set("name", "Bad Name"), _set("modality", "calcium"), _delete("label"))
    assert {"name", "modality", "label"} <= set(_paths(validate_definition(doc)))


def test_definition_error_message_lists_problems() -> None:
    error = DefinitionError([DefinitionProblem("reader.io", "bad"), DefinitionProblem("", "whole")], source=Path("x.json"))
    text = str(error)
    assert "x.json" in text and "reader.io: bad" in text and "whole" in text
    assert isinstance(error, ValueError)


def test_digital_threshold_and_sample_index_parse() -> None:
    doc = _mutated(
        RHS2116,
        _set("time", {"source": "sample_index", "sampling_rate_hz": 30000}),
        _set("sync", {"strategy": "digital_threshold", "channel": "RHS2116_AC_31", "threshold": 2.5}),
    )
    d = parse_definition(doc)
    assert d.time.sampling_rate_hz == 30000.0
    assert d.sync == ld.SyncSpec("digital_threshold", channel="RHS2116_AC_31", threshold=2.5, edge="rising")


def test_neo_reader_with_filename_argument_and_scalar_args() -> None:
    doc = _mutated(
        NEURALYNX,
        _set("reader.io", "IntanIO"),
        _set("reader.path_argument", "filename"),
        _set("reader.path_from", {"source": "file", "file": "events"}),
        _set("reader.args", {}),
        _set("reader.read_block", {"lazy": False}),
    )
    assert validate_definition(doc) == []


@pytest.mark.parametrize(
    "pattern,ok",
    [
        ("*.nev", True),
        ("sub/**/Events*.nev", True),
        ("**/x.raw", True),
        ("[ab]?.csv", True),
        (".hidden*", True),
        ("", False),
        ("/abs/x", False),
        ("~/x", False),
        ("C:/x", False),
        ("c:x", False),
        ("a\\b", False),
        ("../x", False),
        ("a/../x", False),
        ("a/..", False),
        ("./x", False),
        ("a//b", False),
        ("a/", False),
        ("a**", False),
        ("**a/b", False),
        ("***", False),
        ("a\x00b", False),
    ],
)
def test_relative_glob_rule_and_schema_regex_agree(pattern: str, ok: bool) -> None:
    assert (check_relative_glob(pattern) is None) is ok
    regex = definition_json_schema()["$defs"]["glob"]["pattern"]
    assert (re.search(regex, pattern) is not None) is ok


# ─────────────────────────────────────────────────────────────────────────────
# Files on disk
# ─────────────────────────────────────────────────────────────────────────────

def _write(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def test_load_definition_requires_matching_file_name(tmp_path: Path) -> None:
    path = _write(tmp_path / "my-rig.json", _raw(NEURALYNX))
    with pytest.raises(DefinitionError) as info:
        load_definition(path)
    assert info.value.source == path
    assert [p.path for p in info.value.problems] == ["name"]
    assert "my-rig.json" in info.value.problems[0].message


@pytest.mark.parametrize(
    "text,fragment",
    [
        ("{not json", "invalid JSON"),
        ('{"schema": "ace-loader/1", "schema": "ace-loader/1"}', "duplicate key 'schema'"),
        ('{"x": NaN}', "NaN is not valid JSON"),
        ("[" * 100_000, "nested too deeply"),
    ],
)
def test_load_definition_rejects_bad_json(tmp_path: Path, text: str, fragment: str) -> None:
    path = _write(tmp_path / "neuralynx.json", text)
    with pytest.raises(DefinitionError) as info:
        load_definition(path)
    (problem,) = info.value.problems
    assert problem.path == "" and fragment in problem.message


def test_load_definition_rejects_non_utf8(tmp_path: Path) -> None:
    path = tmp_path / "neuralynx.json"
    path.write_bytes(b"\xff\xfe{")
    with pytest.raises(DefinitionError, match="UTF-8"):
        load_definition(path)


def test_load_definition_missing_file_raises_oserror(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_definition(tmp_path / "missing.json")


def test_project_without_loaders_folder(tmp_path: Path) -> None:
    assert load_project_definitions(tmp_path) == ([], {})


def test_project_definitions_report_bad_files(tmp_path: Path) -> None:
    folder = tmp_path / "loaders"
    _write(folder / "neuralynx.json", _raw(NEURALYNX))
    _write(folder / "rhs2116.json", _raw(RHS2116))
    _write(folder / "broken.json", "{")
    _write(folder / "renamed.json", _raw(NEURALYNX))
    _write(folder / "notes.txt", "ignored")
    (folder / "folder.json").mkdir()

    definitions, problems = load_project_definitions(tmp_path)
    assert [d.name for d in definitions] == ["neuralynx", "rhs2116"]
    assert set(problems) == {str(folder / "broken.json"), str(folder / "renamed.json")}
    assert "invalid JSON" in problems[str(folder / "broken.json")][0].message
    assert [p.path for p in problems[str(folder / "renamed.json")]] == ["name"]


def test_project_definitions_report_deeply_nested_file(tmp_path: Path) -> None:
    folder = tmp_path / "loaders"
    _write(folder / "neuralynx.json", _raw(NEURALYNX))
    _write(folder / "deep.json", "[" * 100_000)

    definitions, problems = load_project_definitions(tmp_path)
    assert [d.name for d in definitions] == ["neuralynx"]
    assert "nested too deeply" in problems[str(folder / "deep.json")][0].message


def test_project_definitions_reject_duplicate_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # File stems are unique within a folder, so force two files to load as the
    # same definition to exercise the duplicate rule.
    folder = tmp_path / "loaders"
    a = _write(folder / "a.json", "{}")
    b = _write(folder / "b.json", "{}")
    c = _write(folder / "c.json", "{}")

    def fake_load(path: Path) -> LoaderDefinition:
        name = "rhs2116" if Path(path).name == "c.json" else "neuralynx"
        base = NEURALYNX if name == "neuralynx" else RHS2116
        return parse_definition(_raw(base), source=Path(path))

    monkeypatch.setattr(ld, "load_definition", fake_load)
    definitions, problems = load_project_definitions(tmp_path)
    assert [d.source for d in definitions] == [c]
    assert set(problems) == {str(a), str(b)}
    assert "also defined in" in problems[str(a)][0].message
    assert str(b) in problems[str(a)][0].message


def test_project_definitions_reject_reserved_names(tmp_path: Path) -> None:
    _write(tmp_path / "loaders" / "neuralynx.json", _raw(NEURALYNX))
    definitions, problems = load_project_definitions(tmp_path, reserved_names={"neuralynx"})
    assert definitions == []
    (problem,) = problems[str(tmp_path / "loaders" / "neuralynx.json")]
    assert problem.path == "name" and "built-in" in problem.message


# ─────────────────────────────────────────────────────────────────────────────
# Detection and file resolution (names only)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_definition(**detect: list[str]) -> LoaderDefinition:
    return parse_definition(_mutated(NEURALYNX, _set("detect", detect)))


def test_detect_all_any_none(tmp_path: Path) -> None:
    folder = _make_layout(tmp_path / "rec", ["Events.nev", "CSC1.ncs", "sub/extra.dat"])
    assert definition_matches(_detect_definition(all_of=["Events.nev", "*.ncs"]), folder)
    assert not definition_matches(_detect_definition(all_of=["Events.nev", "*.raw"]), folder)
    assert definition_matches(_detect_definition(any_of=["*.raw", "*.ncs"]), folder)
    assert not definition_matches(_detect_definition(any_of=["*.raw", "*.xyz"]), folder)
    assert not definition_matches(_detect_definition(any_of=["*.nev"], none_of=["**/*.dat"]), folder)
    assert definition_matches(_detect_definition(any_of=["*.nev"], none_of=["*.dat"]), folder)
    assert definition_matches(_detect_definition(all_of=["sub/*.dat"]), folder)


def test_matching_files_lists_each_pattern(tmp_path: Path) -> None:
    folder = _make_layout(tmp_path / "rec", ["b.ncs", "a.ncs", "Events.nev"])
    hits = matching_files(_detect_definition(all_of=["*.ncs"], any_of=["*.nev", "*.ncs"], none_of=["*.raw"]), folder)
    assert list(hits) == ["*.ncs", "*.nev", "*.raw"]
    assert hits["*.ncs"] == [folder / "a.ncs", folder / "b.ncs"]
    assert hits["*.nev"] == [folder / "Events.nev"]
    assert hits["*.raw"] == []


def test_hand_built_unsafe_pattern_is_refused(tmp_path: Path) -> None:
    detect = ld.Detect(any_of=("../*",))
    with pytest.raises(ValueError, match="unsafe pattern"):
        definition_matches(detect, tmp_path)


def test_resolve_files_rhs2116_excludes_miniscope_and_captures_suffix(rhs2116_dir: Path) -> None:
    resolved = resolve_files(load_definition(RHS2116), rhs2116_dir)
    assert resolved.files["start_time"].name == "start-time_7.csv"
    assert resolved.variables == {"suffix": "7"}
    assert set(resolved.files) == {"start_time", "clock", "ac", "dc"}


def test_resolve_files_missing_required_file(rhs2116_dir: Path) -> None:
    (rhs2116_dir / "rhs2116pair-dc_7.raw").unlink()
    with pytest.raises(FileNotFoundError, match="'dc'"):
        resolve_files(load_definition(RHS2116), rhs2116_dir)


def test_resolve_files_optional_file_may_be_missing(rhs2116_dir: Path) -> None:
    (rhs2116_dir / "rhs2116pair-dc_7.raw").unlink()
    definition = parse_definition(_mutated(RHS2116, _set("reader.files[3].required", False)))
    assert "dc" not in resolve_files(definition, rhs2116_dir).files


def test_resolve_files_inserts_captured_values_literally(tmp_path: Path) -> None:
    folder = _make_layout(tmp_path / "rec", [
        "start-time_[1].csv", "rhs2116pair-clock_[1].raw", "rhs2116pair-ac_[1].raw",
        "rhs2116pair-dc_[1].raw", "rhs2116pair-dc_1.raw",
    ])
    resolved = resolve_files(load_definition(RHS2116), folder)
    assert resolved.variables["suffix"] == "[1]"
    assert resolved.files["dc"].name == "rhs2116pair-dc_[1].raw"


def test_resolve_files_pick_modes(tmp_path: Path) -> None:
    folder = _make_layout(tmp_path / "rec", ["b_1.csv", "a_2.csv", "c_3.csv"])
    os.utime(folder / "c_3.csv", (10, 10))
    os.utime(folder / "a_2.csv", (20, 20))
    os.utime(folder / "b_1.csv", (30, 30))

    def with_pick(pick: str) -> LoaderDefinition:
        return parse_definition(_mutated(
            RHS2116,
            _set("reader.files", [{"role": "ac", "pattern": "*.csv", "pick": pick}]),
            _set("time", {"source": "sample_index", "sampling_rate_hz": 1.0}),
        ))

    assert resolve_files(with_pick("first_sorted"), folder).files["ac"].name == "a_2.csv"
    assert resolve_files(with_pick("oldest_modified"), folder).files["ac"].name == "c_3.csv"
    assert resolve_files(with_pick("first_listed"), folder).files["ac"] == next(folder.glob("*.csv"))
    with pytest.raises(ValueError, match="matches several files"):
        resolve_files(with_pick("only"), folder)


def test_resolve_files_capture_out_of_range(tmp_path: Path) -> None:
    folder = _make_layout(tmp_path / "rec", ["start-time_0.csv"])
    definition = parse_definition(_mutated(RHS2116, _set("reader.files[0].capture.part", 5)))
    with pytest.raises(ValueError, match="part 5 does not exist"):
        resolve_files(definition, folder)


def test_resolve_files_ignores_folders_and_excluded_dirs(tmp_path: Path) -> None:
    folder = _make_layout(tmp_path / "rec", ["saved_movies/Events.nev"])
    (folder / "Events.nev").mkdir()
    with pytest.raises(FileNotFoundError, match="'events'"):
        resolve_files(load_definition(NEURALYNX), folder)


def test_resolve_files_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Recording folder"):
        resolve_files(load_definition(NEURALYNX), tmp_path / "missing")


# ─────────────────────────────────────────────────────────────────────────────
# JSON Schema drift checks
# ─────────────────────────────────────────────────────────────────────────────

def _json_equal(a: Any, b: Any) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    return a == b


def _type_ok(value: Any, name: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "boolean": isinstance(value, bool),
        "null": value is None,
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
    }[name]


def _schema_valid(value: Any, schema: dict[str, Any], root: dict[str, Any]) -> bool:
    """Minimal draft 2020-12 checker for the keywords definition_json_schema() uses."""
    known = {
        "$ref", "$schema", "$id", "$defs", "title", "description", "default", "type", "const", "enum",
        "properties", "required", "additionalProperties", "propertyNames", "items", "minItems", "uniqueItems",
        "minLength", "maxLength", "pattern", "minimum", "exclusiveMinimum", "not", "oneOf", "anyOf",
    }
    unknown = set(schema) - known
    assert not unknown, f"test checker does not support {unknown}"

    if "$ref" in schema:
        target: Any = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        if not _schema_valid(value, target, root):
            return False
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return False
    if "const" in schema and not _json_equal(value, schema["const"]):
        return False
    if "enum" in schema and not any(_json_equal(value, e) for e in schema["enum"]):
        return False
    if "not" in schema and _schema_valid(value, schema["not"], root):
        return False
    if "oneOf" in schema and sum(_schema_valid(value, s, root) for s in schema["oneOf"]) != 1:
        return False
    if "anyOf" in schema and not any(_schema_valid(value, s, root) for s in schema["anyOf"]):
        return False
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", len(value)):
            return False
        if "pattern" in schema and not re.search(schema["pattern"], value):
            return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            return False
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            return False
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            return False
        if schema.get("uniqueItems") and len({json.dumps(v, sort_keys=True) for v in value}) != len(value):
            return False
        if "items" in schema and not all(_schema_valid(v, schema["items"], root) for v in value):
            return False
    if isinstance(value, dict):
        props = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            return False
        for key, item in value.items():
            if "propertyNames" in schema and not _schema_valid(key, schema["propertyNames"], root):
                return False
            if key in props:
                if not _schema_valid(item, props[key], root):
                    return False
            elif schema.get("additionalProperties") is False:
                return False
            elif isinstance(schema.get("additionalProperties"), dict):
                if not _schema_valid(item, schema["additionalProperties"], root):
                    return False
    return True


def _object_schemas(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map validator FIELDS sections to the schema objects that describe them."""
    defs = schema["$defs"]
    path_from = defs["neo_reader"]["properties"]["path_from"]["oneOf"]
    ticks = defs["time_clock_file"]["properties"]["ticks_per_second"]["oneOf"]
    return {
        "definition": schema,
        "detect": defs["detect"],
        "file": defs["file"],
        "capture": defs["file"]["properties"]["capture"],
        "reader.neo": defs["neo_reader"],
        "reader.raw_binary": defs["raw_binary_reader"],
        "path_from.recording_folder": path_from[0],
        "path_from.file": path_from[1],
        "path_from.file_parent": path_from[2],
        "time.reader": defs["time_reader"],
        "time.clock_file": defs["time_clock_file"],
        "time.sample_index": defs["time_sample_index"],
        "csv_value": ticks[1],
        "effective_rate": defs["time_clock_file"]["properties"]["effective_rate"],
        "channels": defs["channels"],
        "sync.event_labels": defs["sync_event_labels"],
        "sync.digital_threshold": defs["sync_digital_threshold"],
        "sync.shared_clock": defs["sync_shared_clock"],
    }


def test_schema_objects_list_the_same_keys_as_the_validator() -> None:
    objects = _object_schemas(definition_json_schema())
    assert set(objects) == set(ld.FIELDS)
    for section, (required, optional) in ld.FIELDS.items():
        obj = objects[section]
        assert obj["additionalProperties"] is False, section
        assert set(obj["properties"]) == required | optional, section
        assert set(obj["required"]) == required, section


def test_schema_enums_match_validator_choices() -> None:
    schema = definition_json_schema()
    defs = schema["$defs"]
    reader_backends = {s["$ref"].split("/")[-1]: s for s in schema["properties"]["reader"]["oneOf"]}
    assert {defs[k]["properties"]["backend"]["const"] for k in reader_backends} == set(ld.BACKENDS)
    assert {defs[s["$ref"].split("/")[-1]]["properties"]["strategy"]["const"]
            for s in schema["properties"]["sync"]["oneOf"]} == set(ld.SYNC_STRATEGIES)
    assert {defs[s["$ref"].split("/")[-1]]["properties"]["source"]["const"]
            for s in schema["properties"]["time"]["oneOf"]} == set(ld.TIME_SOURCES)
    assert {s["properties"]["source"]["const"]
            for s in defs["neo_reader"]["properties"]["path_from"]["oneOf"]} == set(ld.PATH_SOURCES)
    assert defs["file"]["properties"]["pick"]["enum"] == list(ld.PICK_MODES)
    assert defs["raw_binary_reader"]["properties"]["dtype"]["enum"] == list(ld.SAMPLE_DTYPES)
    assert defs["raw_binary_reader"]["properties"]["output_dtype"]["enum"] == list(ld.OUTPUT_DTYPES)
    assert defs["time_clock_file"]["properties"]["clock_dtype"]["enum"] == list(ld.CLOCK_DTYPES)
    assert defs["channels"]["properties"]["source"]["enum"] == list(ld.CHANNEL_SOURCES)
    assert defs["channels"]["properties"]["default"]["enum"] == list(ld.CHANNEL_DEFAULTS)
    assert defs["sync_digital_threshold"]["properties"]["edge"]["enum"] == list(ld.EDGES)
    assert schema["properties"]["schema"]["const"] == SCHEMA
    assert schema["properties"]["modality"]["const"] in ld.MODALITIES
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_is_plain_json() -> None:
    schema = definition_json_schema()
    assert json.loads(json.dumps(schema)) == schema
    assert definition_json_schema() is not schema  # a fresh copy each call


@pytest.mark.parametrize("path", [NEURALYNX, RHS2116], ids=["neuralynx", "rhs2116"])
def test_examples_satisfy_schema(path: Path) -> None:
    schema = definition_json_schema()
    assert _schema_valid(_raw(path), schema, schema)


@pytest.mark.parametrize(
    "base,mutations,expressible",
    [(case[1], case[2], case[5]) for case in INVALID_CASES],
    ids=[case[0] for case in INVALID_CASES],
)
def test_schema_agrees_with_validator_on_invalid_cases(
    base: Path, mutations: list[Mutation], expressible: bool
) -> None:
    schema = definition_json_schema()
    doc = _mutated(base, *mutations)
    assert validate_definition(doc)  # the validator always rejects these
    # Structural cases must be rejected by the schema too; contextual ones
    # (neo names, cross-references, backend combinations) are validator-only
    # and are expected to pass the schema.
    assert _schema_valid(doc, schema, schema) is not expressible
