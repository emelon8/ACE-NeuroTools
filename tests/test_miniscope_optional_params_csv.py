"""A miniscope run may crop without a per-experiment parameter file."""

import csv

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
