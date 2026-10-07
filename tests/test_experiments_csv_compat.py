"""Bug 4 (2026-09-15 audit): the experiments.csv templates and their readers
must agree. Covers the tolerant optional-Box-column reads in file_downloader,
the init template gaining the Box columns, and row/header alignment of the
canonical package templates (both example rows were misaligned)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from aceneurotools.init import _CSV_COLUMNS, _write_experiments_template
from aceneurotools.shared.csv_worker import CSVWorker
from aceneurotools.shared.file_downloader import verify_file_by_line

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "src" / "aceneurotools" / "shared" / "metadata_templates"


# -- canonical package templates ----------------------------------------------


@pytest.mark.parametrize(
    "template",
    ["experiments_template.csv", "analysis_parameters_template.csv"],
)
def test_canonical_template_rows_match_header(template):
    """Every example row must have exactly as many fields as the header —
    csv_row_to_dict refuses misaligned CSVs, so a broken template broke
    every fresh project that copied it."""
    rows = list(csv.reader(open(_TEMPLATES_DIR / template)))
    header = rows[0]
    for row_num, row in enumerate(rows[1:], start=2):
        assert len(row) == len(header), f"{template} row {row_num} misaligned"


def test_canonical_experiments_template_values_land_in_right_columns():
    rows = list(csv.reader(open(_TEMPLATES_DIR / "experiments_template.csv")))
    record = dict(zip(rows[0], rows[1]))
    assert record["ephys directory"].startswith("relative/path/to/ephys")
    assert record["rat weight (kg)"] == "0.500"
    assert record["comments"].startswith("Example baseline")


def test_canonical_analysis_template_parses_via_csv_worker(tmp_path):
    """The template example row must survive the strict csv_row_to_dict path
    used by every pipeline load."""
    source = _TEMPLATES_DIR / "analysis_parameters_template.csv"
    target = tmp_path / "analysis_parameters.csv"
    target.write_text(source.read_text())
    raw = CSVWorker.csv_row_to_dict(target, 1)
    assert raw is not None
    converted = CSVWorker.convert_data_types(raw)
    assert converted["gSig"] == [7, 7]
    assert converted["border_nan"] == "copy"
    assert converted["comments"].startswith("Typical default")


# -- init template ------------------------------------------------------------


def test_init_template_includes_optional_box_columns(tmp_path):
    target = tmp_path / "experiments_template.csv"
    _write_experiments_template(target)
    rows = list(csv.reader(open(target)))
    header = rows[0]
    assert "Box Calcium Folder ID" in header
    assert "Box ephys folder ID" in header
    for row in rows[1:]:
        assert len(row) == len(header)


def test_init_box_columns_marked_optional():
    notes = {name: note for name, _a, _b, note in _CSV_COLUMNS}
    assert notes["Box Calcium Folder ID"].startswith("OPTIONAL")
    assert notes["Box ephys folder ID"].startswith("OPTIONAL")


# -- verify_file_by_line tolerance --------------------------------------------


def _write_csv(path: Path, header: list[str], row: list[str]) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerow(row)


def test_verify_without_box_columns_checks_local_files(tmp_path):
    """A CSV without any Box columns (pre-fix init template shape) must not
    KeyError — it should simply report local availability."""
    csv_path = tmp_path / "experiments.csv"
    _write_csv(
        csv_path,
        ["line number", "id", "ephys directory", "calcium imaging directory"],
        ["7", "rat_007", "sub7/ephys", "sub7/miniscope"],
    )
    base = tmp_path / "data"
    (base / "sub7" / "ephys").mkdir(parents=True)
    (base / "sub7" / "ephys" / "chan.ncs").write_bytes(b"x")

    assert verify_file_by_line(7, csv_path, do_type="ephys", base_file_path=base) is True
    # miniscope data absent and no Box ID available -> False, not KeyError
    assert verify_file_by_line(7, csv_path, do_type="miniscope", base_file_path=base) is False


def test_verify_with_empty_box_ids_stays_local(tmp_path):
    """Canonical-template shape: Box columns present but blank behaves the
    same as absent columns — no Box attempt, local check only."""
    csv_path = tmp_path / "experiments.csv"
    _write_csv(
        csv_path,
        [
            "line number",
            "id",
            "Box Calcium Folder ID",
            "calcium imaging directory",
            "Box ephys folder ID",
            "ephys directory",
        ],
        ["7", "rat_007", "", "sub7/miniscope", "", "sub7/ephys"],
    )
    base = tmp_path / "data"
    base.mkdir()
    assert verify_file_by_line(7, csv_path, do_type="both", base_file_path=base) is False
