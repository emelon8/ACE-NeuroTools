"""Verify an installed distribution without scientific or optional dependencies."""

from __future__ import annotations

import csv
import json
from importlib.metadata import distribution
from importlib.resources import files

import aceneurotools

root = files("aceneurotools")
metadata = distribution("aceneurotools")
assert metadata.version == aceneurotools.__version__
assert any(entry.name == "ace-neuro" for entry in metadata.entry_points)
assert (root / "py.typed").is_file()
for name in ("experiment.v1", "analysis.cnmfe.v1"):
    assert json.loads((root / "evc" / "schemas" / (name + ".schema.json")).read_text())
for name in ("experiments_template.csv", "analysis_parameters_template.csv"):
    with (root / "shared" / "metadata_templates" / name).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert "line number" in rows[0]
    assert all(len(row) == len(rows[0]) for row in rows[1:])
print("Installed package version, command, schemas, and templates verified.")
