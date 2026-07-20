"""Tests for CSVWorker row loading and type conversion.

Covers correctness plus the single-disk-read optimization in csv_row_to_dict
(previously the file was opened twice per call).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aceneurotools.shared import csv_worker as csv_worker_mod
from aceneurotools.shared.csv_worker import CSVWorker

CSV_TEXT = (
    "line number,id,date (YYMMDD),some_value,LFP and EEG CSCs\n"
    "1,R230706B,230706,3.5,CSC1;CSC2\n"
    "2,R230707A,230707,7,CSC3\n"
)


@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    p = tmp_path / "experiments.csv"
    p.write_text(CSV_TEXT)
    return p


def test_reads_correct_row(csv_file: Path):
    row = CSVWorker.csv_row_to_dict(csv_file, 2)
    assert row["id"] == "R230707A"
    assert str(row["line number"]) == "2"


def test_missing_line_raises(csv_file: Path):
    with pytest.raises(ValueError, match="not found"):
        CSVWorker.csv_row_to_dict(csv_file, 99)


def test_malformed_row_raises_helpful_error(tmp_path: Path):
    bad = tmp_path / "bad.csv"
    # Row 2 has an unquoted comma -> 4 fields vs 3-column header.
    bad.write_text("line number,id,coords\n1,R1,(0, 1, 2)\n")
    with pytest.raises(ValueError, match="CSV malformed"):
        CSVWorker.csv_row_to_dict(bad, 1)


def test_missing_file_returns_none(tmp_path: Path):
    assert CSVWorker.csv_row_to_dict(tmp_path / "nope.csv", 1) is None


def test_empty_file_returns_none(tmp_path: Path):
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    assert CSVWorker.csv_row_to_dict(empty, 1) is None


def test_reads_file_only_once(csv_file: Path, monkeypatch):
    """The disk should be touched exactly once (single read_text call) and
    pandas should parse from memory (single read_csv call)."""
    read_text_calls = {"n": 0}
    read_csv_calls = {"n": 0}

    original_read_text = Path.read_text
    original_read_csv = csv_worker_mod.pd.read_csv

    def counting_read_text(self, *args, **kwargs):
        read_text_calls["n"] += 1
        return original_read_text(self, *args, **kwargs)

    def counting_read_csv(*args, **kwargs):
        read_csv_calls["n"] += 1
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    monkeypatch.setattr(csv_worker_mod.pd, "read_csv", counting_read_csv)

    CSVWorker.csv_row_to_dict(csv_file, 1)

    assert read_text_calls["n"] == 1
    assert read_csv_calls["n"] == 1


def test_convert_data_types_semicolon_list_and_strings():
    raw = {"id": "R1", "LFP and EEG CSCs": "CSC1;CSC2", "some_value": "3.5", "flag": "true"}
    converted = CSVWorker.convert_data_types(raw)
    assert converted["id"] == "R1"
    assert converted["LFP and EEG CSCs"] == ["CSC1", "CSC2"]
    assert converted["some_value"] == 3.5
    assert converted["flag"] is True
