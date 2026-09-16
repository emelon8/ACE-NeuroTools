"""Phase 4 first slice (D05): CSV ⇄ parameter-document bridge — extraction
typing matches the pipeline view, writeback is a bijection on the canonical
templates, unknown columns survive verbatim, imports create the root
revision, and documents validate against their bundled schemas."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from aceneurotools.config.config_utils import load_analysis_params
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

_TEMPLATES_DIR = (
    Path(__file__).resolve().parents[1]
    / "src" / "aceneurotools" / "shared" / "metadata_templates"
)


@pytest.fixture()
def project(tmp_path):
    """A project seeded with the canonical template rows as its live CSVs."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "experiments.csv").write_text(
        (_TEMPLATES_DIR / "experiments_template.csv").read_text()
    )
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
    doc = {"schema": "aceneuro-experiment-v1", "line_number": "one", "id": "x",
           "_csv": {"columns": [], "raw": {}}, "bogus": 1}
    errors = validate_document(doc, schema)
    assert any("line_number" in e for e in errors)
    assert any("bogus" in e for e in errors)


# -- writeback bijection ------------------------------------------------------


def test_untouched_extract_writeback_is_byte_identical(project):
    before = {
        name: (project / name).read_bytes()
        for name in ("experiments.csv", "analysis_parameters.csv")
    }
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
