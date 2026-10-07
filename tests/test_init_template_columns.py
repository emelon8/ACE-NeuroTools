"""Keep new-project metadata compatible with the optional Box downloader."""

import csv

from aceneurotools.init import _write_experiments_template


def test_generated_experiments_template_has_optional_box_columns(tmp_path):
    path = tmp_path / "experiments_template.csv"
    _write_experiments_template(path)

    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 2
    for row in rows:
        assert "Box Calcium Folder ID" in row
        assert "Box ephys folder ID" in row
        assert row["Box Calcium Folder ID"] == ""
        assert row["Box ephys folder ID"] == ""
