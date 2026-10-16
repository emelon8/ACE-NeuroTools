"""Backend CSV contracts: identity, safe parsing, and failure without data loss."""

from __future__ import annotations

import csv

import pytest

from aceneurotools.shared import csv_worker
from aceneurotools.shared.csv_worker import CSVWorker, append_row_csv, update_csv_cell


def table(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([header, *rows])


@pytest.mark.parametrize("identifier", ["001", "NA", "NULL", "000000000000000000123", "rat µ"])
def test_reader_preserves_subject_identity_and_literal_notes(tmp_path, identifier):
    path = tmp_path / "experiments.csv"
    table(path, ["line number", "id", "comments", "value"], [["001", identifier, "NA", "3.5"]])
    row = CSVWorker.csv_row_to_dict(path, "001")
    assert row["line number"] == "001"
    assert row["id"] == identifier
    assert row["comments"] == "NA"
    assert CSVWorker.convert_data_types(row)["value"] == 3.5


@pytest.mark.parametrize(
    "content, message",
    [
        ("line number,id\n1,A\n1,B\n", "more than once"),
        ("line number,id,id\n1,A,B\n", "unique"),
        ("line number,\n1,A\n", "unique"),
        ('line number,id\n1,"unfinished\n', "malformed"),
        ("line number,id\n,A\n", "blank"),
        ("line number,id\n 1,A\n", "spaces"),
    ],
)
def test_reader_rejects_ambiguous_or_malformed_rows_without_writing(tmp_path, content, message):
    path = tmp_path / "experiments.csv"
    path.write_text(content, encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match=message):
        CSVWorker.csv_row_to_dict(path, 1)
    assert path.read_bytes() == before


def test_bom_crlf_quoted_newline_and_blank_rows(tmp_path):
    path = tmp_path / "experiments.csv"
    path.write_bytes(b'\xef\xbb\xbfline number,id,comments\r\n\r\n001,007,"a,b\r\nc"\r\n')
    row = CSVWorker.csv_row_to_dict(path, "001")
    assert row == {"line number": "001", "id": "007", "comments": "a,b\r\nc"}


def test_blank_optional_settings_use_pipeline_defaults(tmp_path):
    path = tmp_path / "analysis_parameters.csv"
    table(path, ["line number", "crop", "decay_time"], [["1", "", ""]])
    converted = CSVWorker.convert_data_types(CSVWorker.csv_row_to_dict(path, 1))
    assert converted["crop"] is None
    assert converted["decay_time"] is None


@pytest.mark.parametrize("value", ["__import__('os').system('false')", "open('sentinel', 'w')", "lambda: 1"])
def test_value_parser_never_executes_expressions(tmp_path, monkeypatch, value):
    monkeypatch.chdir(tmp_path)
    source = {"custom": value}
    assert CSVWorker.convert_data_types(source) == source
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("column, number", [("unknown", 1), ("id", 99)])
def test_update_invalid_target_preserves_exact_bytes(tmp_path, column, number):
    path = tmp_path / "experiments.csv"
    path.write_bytes(b"line number,id\r\n1,A\r\n2,B\r\n")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        update_csv_cell("replacement", column, number, path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("operation", ["update", "append"])
def test_failed_atomic_replace_keeps_original_and_cleans_staging(tmp_path, monkeypatch, operation):
    path = tmp_path / "experiments.csv"
    table(path, ["line number", "id"], [["1", "A"]])
    before = path.read_bytes()

    def fail_replace(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(csv_worker.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk failure"):
        if operation == "update":
            update_csv_cell("B", "id", 1, path)
        else:
            append_row_csv({"line number": "2", "id": "B"}, path)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_append_uses_existing_column_order_and_adds_missing_newline(tmp_path):
    path = tmp_path / "experiments.csv"
    path.write_text("line number,id,comments\n1,A,original", encoding="utf-8")
    append_row_csv({"comments": "µ, quoted\nline", "id": "B", "line number": "2"}, path)
    with path.open(newline="", encoding="utf-8") as handle:
        assert list(csv.DictReader(handle)) == [
            {"line number": "1", "id": "A", "comments": "original"},
            {"line number": "2", "id": "B", "comments": "µ, quoted\nline"},
        ]


@pytest.mark.parametrize("row", [{"line number": "2"}, {"line number": "2", "id": "B", "extra": "x"}])
def test_append_rejects_mismatched_schema_without_modifying_file(tmp_path, row):
    path = tmp_path / "experiments.csv"
    path.write_text("line number,id\n1,A\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="columns"):
        append_row_csv(row, path)
    assert path.read_bytes() == before


def test_update_preserves_unselected_rows_unicode_and_bom(tmp_path):
    path = tmp_path / "experiments.csv"
    path.write_bytes(b'\xef\xbb\xbfline number,id,comments\r\n001,007,old\r\n002,008,"keep,me"\r\n')
    update_csv_cell("new µ\nline", "comments", "001", path)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert CSVWorker.csv_row_to_dict(path, "001")["comments"] == "new µ\nline"
    assert CSVWorker.csv_row_to_dict(path, "002")["comments"] == "keep,me"


def test_append_can_create_a_new_table(tmp_path):
    path = tmp_path / "nested.csv"
    append_row_csv({"line number": "1", "id": "001"}, path)
    assert CSVWorker.csv_row_to_dict(path, 1)["id"] == "001"


def test_schema_extensions_do_not_mutate_global_conversion_policy():
    source = {"custom_id": "001", "channels": "A;B", "crop": "False"}
    result = CSVWorker.convert_data_types(
        source, extra_string_columns=frozenset({"custom_id"}), extra_list_columns=frozenset({"channels"})
    )
    assert result == {"custom_id": "001", "channels": ["A", "B"], "crop": False}
    assert source == {"custom_id": "001", "channels": "A;B", "crop": "False"}
    assert "custom_id" not in csv_worker.STRING_COLUMNS
    assert "channels" not in csv_worker.SEMICOLON_LIST_COLUMNS


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('["first note", "second note"]', ["first note", "second note"]),
        ('{"lab note": "a b"}', {"lab note": "a b"}),
        ('("a b", "c d")', ["a b", "c d"]),
        ("(3, 4)", [3, 4]),
    ],
)
def test_structured_values_preserve_spaces_inside_text(raw, expected):
    assert CSVWorker.convert_data_types({"custom": raw})["custom"] == expected


def test_legacy_empty_spacer_columns_remain_readable_and_writable(tmp_path):
    path = tmp_path / "experiments.csv"
    path.write_text("line number,id,,,value\n1,001,,,3.5\n2,002,,,4\n", encoding="utf-8")
    raw = CSVWorker.csv_row_to_dict(path, 1)
    assert raw["id"] == "001"
    assert CSVWorker.convert_data_types(raw)["value"] == 3.5
    update_csv_cell("new", "id", 1, path)
    append_row_csv({"line number": "3", "id": "003", "": "", "value": "5"}, path)
    assert CSVWorker.csv_row_to_dict(path, 1)["id"] == "new"
    assert CSVWorker.csv_row_to_dict(path, 2)["id"] == "002"
    assert CSVWorker.csv_row_to_dict(path, 3)["id"] == "003"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["line number", "id", "", "", "value"]
    assert all(row[2:4] == ["", ""] for row in rows[1:])


def test_legacy_spacer_columns_cannot_be_populated_by_a_write(tmp_path):
    path = tmp_path / "experiments.csv"
    path.write_text("line number,id,,\n1,A,,\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(ValueError):
        update_csv_cell("would disappear", "", 1, path)
    with pytest.raises(ValueError):
        append_row_csv({"line number": "2", "id": "B", "": "would disappear"}, path)
    assert path.read_bytes() == before


def test_optional_analysis_row_uses_defaults_without_hiding_malformed_csv(tmp_path):
    from aceneurotools.shared.experiment_data_manager import ExperimentDataManager

    path = tmp_path / "analysis_parameters.csv"
    path.write_text("line number,crop\n7,False\n")
    before = path.read_bytes()
    manager = ExperimentDataManager(96, project_path=tmp_path, data_path=tmp_path, auto_import_metadata=False)
    assert manager.analysis_params == {}
    assert path.read_bytes() == before
    path.write_text("line number,crop\n7,False,extra\n")
    with pytest.raises(ValueError, match="malformed"):
        ExperimentDataManager(96, project_path=tmp_path, data_path=tmp_path, auto_import_metadata=False)
