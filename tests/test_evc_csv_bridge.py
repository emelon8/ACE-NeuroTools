"""Phase 4 first slice (D05): CSV ⇄ parameter-document bridge — extraction
typing matches the pipeline view, writeback is a bijection on the canonical
templates, unknown columns survive verbatim, imports create the root
revision, and documents validate against their bundled schemas."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from unittest import mock

import pytest

from aceneurotools.shared.config_utils import load_analysis_params
from aceneurotools.evc import csv_bridge
from aceneurotools.evc.csv_bridge import (
    ANALYSIS_CNMFE_DOC,
    EXPERIMENT_DOC,
    extract,
    import_experiment,
    load_schema,
    validate_document,
    writeback,
)
from aceneurotools.evc.errors import CSVBridgeError
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.shared.csv_worker import CSVWorker

AUTHOR = "Test Rig <rig@lab>"

_TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "src" / "aceneurotools" / "shared" / "metadata_templates"


@pytest.fixture()
def project(tmp_path):
    """A project seeded with the canonical template rows as its live CSVs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "experiments.csv").write_text((_TEMPLATES_DIR / "experiments_template.csv").read_text())
    (project_dir / "analysis_parameters.csv").write_text(
        (_TEMPLATES_DIR / "analysis_parameters_template.csv").read_text()
    )
    return project_dir


def _load_doc(project_dir: Path, name: str) -> dict:
    return json.loads((project_dir / "parameters" / name).read_text())


# -- extract ------------------------------------------------------------------


def test_extract_types_match_pipeline_view(project):
    written = extract(1, project)
    assert set(written) == {EXPERIMENT_DOC, ANALYSIS_CNMFE_DOC}

    experiment = _load_doc(project, EXPERIMENT_DOC)
    assert experiment["line_number"] == 1
    assert experiment["id"] == "ExampleRat"
    assert experiment["date"] == "240101"
    # RAW csv value — relative, never pre-joined with data_path
    assert experiment["ephys_directory"].startswith("relative/path/to/ephys")
    assert experiment["rat_weight_kg"] == 0.5
    assert experiment["box_calcium_folder_id"] is None
    assert len(experiment["channels"]) == 5

    analysis = _load_doc(project, ANALYSIS_CNMFE_DOC)
    assert analysis["params"]["gSig"] == [7, 7]
    assert analysis["params"]["min_corr"] == 0.8
    assert analysis["params"]["update_background_components"] is True
    assert analysis["params"]["border_nan"] == "copy"
    assert analysis["params"]["crop_coords"] is None
    assert analysis["comments"].startswith("Typical default")


def test_extracted_documents_validate_against_bundled_schemas(project):
    extract(1, project)
    for name, schema in (
        (EXPERIMENT_DOC, "experiment.v1"),
        (ANALYSIS_CNMFE_DOC, "analysis.cnmfe.v1"),
    ):
        assert validate_document(_load_doc(project, name), load_schema(schema)) == ()


def test_extract_missing_line_or_csv_raises(project, tmp_path):
    with pytest.raises(CSVBridgeError):
        extract(999, project)
    empty = tmp_path / "empty_project"
    empty.mkdir()
    with pytest.raises(CSVBridgeError):
        extract(1, empty)


def test_validate_catches_broken_documents():
    schema = load_schema("experiment.v1")
    doc = {
        "schema": "aceneuro-experiment-v1",
        "line_number": "one",
        "id": "x",
        "_csv": {"columns": [], "raw": {}},
        "bogus": 1,
    }
    errors = validate_document(doc, schema)
    assert any("line_number" in e for e in errors)
    assert any("bogus" in e for e in errors)


# -- writeback bijection ------------------------------------------------------


def test_untouched_extract_writeback_is_byte_identical(project):
    before = {name: (project / name).read_bytes() for name in ("experiments.csv", "analysis_parameters.csv")}
    extract(1, project)
    writeback(project)
    for name, original in before.items():
        assert (project / name).read_bytes() == original, name


def test_second_extract_is_a_fixed_point(project):
    extract(1, project)
    first = {n: _load_doc(project, n) for n in (EXPERIMENT_DOC, ANALYSIS_CNMFE_DOC)}
    writeback(project)
    extract(1, project)
    second = {n: _load_doc(project, n) for n in (EXPERIMENT_DOC, ANALYSIS_CNMFE_DOC)}
    assert first == second


def test_edited_document_field_lands_in_csv_and_pipeline_load(project):
    """The Phase 4 acceptance: edit the JSON document, write back, and the
    unchanged CSV-reading pipeline path sees the new value."""
    extract(1, project)
    doc_path = project / "parameters" / ANALYSIS_CNMFE_DOC
    doc = json.loads(doc_path.read_text())
    doc["params"]["gSig"] = [8, 8]
    doc["params"]["crop_coords"] = [10, 20, 300, 400]
    doc_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")

    writeback(project)

    raw = CSVWorker.csv_row_to_dict(project / "analysis_parameters.csv", 1)
    converted = CSVWorker.convert_data_types(raw)
    assert converted["gSig"] == [8, 8]
    assert converted["min_corr"] == 0.8  # neighbours untouched
    # the exact load path MiniscopePipeline's CLI uses — no pipeline changes
    kwargs = load_analysis_params(1, project_path=project)
    assert kwargs["crop_coords"] == [10, 20, 300, 400]


def test_writeback_preserves_unknown_lab_columns(project):
    rows = list(csv.reader(open(project / "experiments.csv")))
    rows[0].append("my lab notes")
    rows[1].append("keep me, exactly; as-is")
    with open(project / "experiments.csv", "w", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)

    extract(1, project)
    doc_path = project / "parameters" / EXPERIMENT_DOC
    doc = json.loads(doc_path.read_text())
    assert doc["_csv"]["raw"]["my lab notes"] == "keep me, exactly; as-is"
    doc["rat_weight_kg"] = 0.42
    doc_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    writeback(project)

    rows = list(csv.reader(open(project / "experiments.csv")))
    record = dict(zip(rows[0], rows[1]))
    assert record["my lab notes"] == "keep me, exactly; as-is"
    assert record["rat weight (kg)"] == "0.42"


def test_writeback_does_not_clobber_concurrent_csv_edits(project):
    """Fields the document did not change keep their *current* CSV bytes —
    a cell edited in the CSV after extraction survives writeback."""
    extract(1, project)
    from aceneurotools.shared.csv_worker import update_csv_cell

    update_csv_cell("oasis_v2", "method_deconvolution", 1, project / "analysis_parameters.csv")
    writeback(project)
    rows = list(csv.reader(open(project / "analysis_parameters.csv")))
    record = dict(zip(rows[0], rows[1]))
    assert record["method_deconvolution"] == "oasis_v2"


def test_writeback_refuses_when_columns_vanish(project):
    extract(1, project)
    rows = list(csv.reader(open(project / "experiments.csv")))
    drop = rows[0].index("comments")
    for row in rows:
        del row[drop]
    with open(project / "experiments.csv", "w", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    with pytest.raises(CSVBridgeError):
        writeback(project)


# -- writeback: staging, atomic replacement, failure containment --------------


def _edit_doc(project_dir: Path, name: str, edit) -> None:
    """Apply *edit(document)* to a parameter document in place."""
    path = project_dir / "parameters" / name
    doc = json.loads(path.read_text())
    edit(doc)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def _no_staging_files(project_dir: Path) -> bool:
    return list(project_dir.glob(".tmp-csvbridge-*")) == []


class _DieAfterFirstRow:
    """A ``csv.writer`` stand-in that writes the header to the staging handle
    and then fails on the first data row (full disk / crash mid-write)."""

    def __init__(self, handle, **_kwargs):
        self._handle = handle
        self._wrote_header = False

    def writerow(self, row):
        self._handle.write("|".join(row) + "\n")
        if self._wrote_header:
            raise OSError("disk full")
        self._wrote_header = True

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def test_staging_write_failure_leaves_originals_intact(project):
    """A failure between truncation and completion must never damage the live
    CSV: everything is written to a staging file first."""
    extract(1, project)
    _edit_doc(project, EXPERIMENT_DOC, lambda doc: doc.update(rat_weight_kg=0.42))
    before = {name: (project / name).read_bytes() for name in ("experiments.csv", "analysis_parameters.csv")}

    with mock.patch.object(csv_bridge.csv, "writer", _DieAfterFirstRow):
        with pytest.raises(OSError, match="disk full"):
            writeback(project)

    for name, original in before.items():
        assert (project / name).read_bytes() == original, name
    assert _no_staging_files(project)


def test_replace_failure_leaves_original_intact_and_removes_staging(project):
    extract(1, project)
    _edit_doc(project, EXPERIMENT_DOC, lambda doc: doc.update(rat_weight_kg=0.42))
    before = {name: (project / name).read_bytes() for name in ("experiments.csv", "analysis_parameters.csv")}

    with mock.patch.object(csv_bridge.os, "replace", side_effect=OSError("sharing violation")):
        with pytest.raises(OSError, match="sharing violation"):
            writeback(project)

    for name, original in before.items():
        assert (project / name).read_bytes() == original, name
    assert _no_staging_files(project)


def test_concurrent_change_between_read_and_replace_is_refused(project):
    """The compare-and-set digest catches an edit that lands after writeback
    read the CSV but before it replaces it."""
    extract(1, project)
    _edit_doc(project, EXPERIMENT_DOC, lambda doc: doc.update(rat_weight_kg=0.42))
    from aceneurotools.shared.csv_worker import update_csv_cell

    real_commit = csv_bridge._commit_staged_csv

    def commit_after_external_edit(change):
        update_csv_cell("edited elsewhere", "comments", 1, project / "experiments.csv")
        return real_commit(change)

    with mock.patch.object(csv_bridge, "_commit_staged_csv", commit_after_external_edit):
        with pytest.raises(CSVBridgeError, match="changed since it was read"):
            writeback(project)

    rows = list(csv.reader(open(project / "experiments.csv")))
    record = dict(zip(rows[0], rows[1]))
    assert record["comments"] == "edited elsewhere"  # newer edit survives untouched
    assert record["rat weight (kg)"] == "0.500"  # staged value did NOT land
    assert _no_staging_files(project)


def test_bom_bearing_csv_roundtrips_and_keeps_bom(project):
    """A UTF-8-BOM experiments.csv must extract, update, and stay BOM-prefixed."""
    experiment_csv = project / "experiments.csv"
    experiment_csv.write_bytes(b"\xef\xbb\xbf" + experiment_csv.read_bytes())

    extract(1, project)  # the BOM must not glue itself onto the first header cell
    _edit_doc(project, EXPERIMENT_DOC, lambda doc: doc.update(rat_weight_kg=0.42))
    writeback(project)

    content = experiment_csv.read_bytes()
    assert content.startswith(b"\xef\xbb\xbf")
    assert not content.startswith(b"\xef\xbb\xbf\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")))
    record = dict(zip(rows[0], rows[1]))
    assert record["line number"] == "1"
    assert record["rat weight (kg)"] == "0.42"
    assert _no_staging_files(project)


def test_second_document_failure_leaves_both_csvs_unchanged(project):
    """writeback stages every target before replacing any: a schema error in
    the analysis document must not leave experiments.csv half-updated."""
    extract(1, project)
    _edit_doc(project, EXPERIMENT_DOC, lambda doc: doc.update(rat_weight_kg=0.42))
    _edit_doc(project, ANALYSIS_CNMFE_DOC, lambda doc: doc.update(line_number="one"))  # violates integer schema
    before = {name: (project / name).read_bytes() for name in ("experiments.csv", "analysis_parameters.csv")}

    with pytest.raises(CSVBridgeError, match="analysis.cnmfe.json"):
        writeback(project)

    for name, original in before.items():
        assert (project / name).read_bytes() == original, name
    assert _no_staging_files(project)


def test_changed_cell_is_canonical_and_unrelated_bytes_survive(project):
    """Only the document-changed cell is re-serialized; everything else —
    unknown lab columns, quoted cells, empty spacer columns — is canonical
    RFC-4180 with LF endings."""
    experiment_csv = project / "experiments.csv"
    rows = list(csv.reader(open(experiment_csv)))
    rows[0].extend(["my lab notes", ""])
    rows[1].extend(['say "hi", exactly; as-is', ""])
    with open(experiment_csv, "w", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(rows)
    before_text = experiment_csv.read_text()

    extract(1, project)
    _edit_doc(project, EXPERIMENT_DOC, lambda doc: doc.update(rat_weight_kg=0.42))
    writeback(project)

    content = experiment_csv.read_bytes()
    assert b"\r" not in content  # LF line endings only
    assert content.endswith(b"\n")
    # the quoted lab cell is re-emitted in canonical minimal-quoting form
    assert b'"say ""hi"", exactly; as-is"' in content
    before_rows = list(csv.reader(io.StringIO(before_text, newline="")))
    after_rows = list(csv.reader(io.StringIO(content.decode("utf-8"), newline="")))
    assert before_rows[0] == after_rows[0]
    for name, before_cell, after_cell in zip(before_rows[0], before_rows[1], after_rows[1]):
        if name == "rat weight (kg)":
            assert before_cell == "0.500" and after_cell == "0.42"
        else:
            assert before_cell == after_cell, name
    header, row = after_rows[0], after_rows[1]
    record = dict(zip(header, row))
    assert header[-1] == "" and record[""] == ""  # spacer header and cell survive
    assert _no_staging_files(project)


def test_repeated_writeback_is_byte_idempotent(project):
    extract(1, project)
    _edit_doc(project, ANALYSIS_CNMFE_DOC, lambda doc: doc["params"].update(gSig=[9, 9]))

    writeback(project)
    first = {name: (project / name).read_bytes() for name in ("experiments.csv", "analysis_parameters.csv")}
    writeback(project)  # no re-extract; documents unchanged since the first pass
    second = {name: (project / name).read_bytes() for name in first}
    assert first == second


# -- import: the root revision ------------------------------------------------


def test_import_records_root_revision_and_is_idempotent(project):
    result = import_experiment(1, project, author=AUTHOR)
    assert result.root is True
    assert result.documents == (ANALYSIS_CNMFE_DOC, EXPERIMENT_DOC)

    evc = ExperimentVersionControl.open(project)
    history = evc.history()
    assert len(history) == 1
    assert history[0].message == "imported from CSV: line 1"
    files = evc.show(result.revision).files
    assert f"parameters/{EXPERIMENT_DOC}" in files
    assert f"parameters/{ANALYSIS_CNMFE_DOC}" in files

    again = import_experiment(1, project, author=AUTHOR)
    assert again.revision == result.revision and again.root is False
    assert len(ExperimentVersionControl.open(project).history()) == 1
