"""A miniscope run may crop without a per-experiment parameter file or row."""

import csv

import pytest

from aceneurotools.pipelines.miniscope import _save_crop_coords_if_configured


def test_crop_coordinates_do_not_require_optional_parameter_csv(tmp_path):
    coords = {"x0": 2, "y0": 3, "x1": 20, "y1": 30}

    assert _save_crop_coords_if_configured(coords, 96, tmp_path) is False
    assert not (tmp_path / "analysis_parameters.csv").exists()

    csv_path = tmp_path / "analysis_parameters.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["line number", "crop_coords"])
        writer.writeheader()
        writer.writerow({"line number": "96", "crop_coords": ""})

    assert _save_crop_coords_if_configured(coords, 96, tmp_path) is True
    with csv_path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["crop_coords"] == str(coords)


def test_missing_optional_parameter_row_does_not_abort_or_rewrite_file(tmp_path):
    path = tmp_path / "analysis_parameters.csv"
    path.write_text("line number,crop_coords\n7,\n")
    before = path.read_bytes()
    assert _save_crop_coords_if_configured({"x0": 0, "y0": 0, "x1": 10, "y1": 10}, 96, tmp_path) is False
    assert path.read_bytes() == before


def test_crop_save_does_not_hide_malformed_parameter_table(tmp_path):
    path = tmp_path / "analysis_parameters.csv"
    path.write_text("line number,crop_coords\n96,unquoted,extra\n")
    before = path.read_bytes()
    with pytest.raises(ValueError, match="malformed"):
        _save_crop_coords_if_configured({"x0": 0, "y0": 0, "x1": 10, "y1": 10}, 96, tmp_path)
    assert path.read_bytes() == before
