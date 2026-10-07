"""CSV ⇄ workspace configuration bridge (Phase 4, first slice).

Implements the D05 decision (``docs/adr/0002-json-parameter-documents.md``,
plan §Phase 4): the authoritative saved configuration is a set of canonical
JSON documents in the experiment's ``parameters/`` directory; existing CSVs
are imported non-destructively and written back for compatibility while
CSV-reading pipelines migrate.

Two documents are bridged in this slice:

* ``parameters/experiment.json``   ⇄ the experiment's ``experiments.csv`` row
  (schema ``aceneuro-experiment-v1``)
* ``parameters/analysis.cnmfe.json`` ⇄ its ``analysis_parameters.csv`` row
  (schema ``aceneuro-analysis-cnmfe-v1``)

Round-trip contract:

* Extraction reads **raw CSV cell values** with the standard-library ``csv``
  module — never through ``ExperimentDataManager``, which pre-joins
  ``data_path`` into the directory columns and would break the bijection.
* Typing matches what pipelines see: values go through
  ``CSVWorker.convert_data_types`` (imported lazily — this module imports
  without pandas).
* Every raw cell is preserved verbatim in the document's ``_csv`` section, so
  unknown lab-specific columns survive writeback untouched (D05's
  export-coverage rule: explicit passthrough, not silent loss).
* Writeback rewrites only cells whose typed value the document changed; the
  file is re-emitted in canonical CSV form (RFC-4180 minimal quoting, LF line
  endings — the same canonicalisation ``csv_worker.update_csv_cell`` already
  applies).

``import_experiment`` records the first extraction as the experiment's
"imported from CSV" root revision — every history begins with a faithful copy
of its legacy state.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from aceneurotools.evc.errors import CSVBridgeError, NothingToRecordError, RepositoryNotFoundError
from aceneurotools.evc.porcelain import ExperimentVersionControl
from aceneurotools.evc.workspace import ExperimentWorkspace

EXPERIMENTS_CSV = "experiments.csv"
ANALYSIS_CSV = "analysis_parameters.csv"

EXPERIMENT_DOC = "experiment.json"
ANALYSIS_CNMFE_DOC = "analysis.cnmfe.json"

EXPERIMENT_SCHEMA = "aceneuro-experiment-v1"
ANALYSIS_CNMFE_SCHEMA = "aceneuro-analysis-cnmfe-v1"

_SCHEMAS_DIR = Path(__file__).resolve().parent / "schemas"

#: Experiment-document fields: (json key, CSV column, conversion kind).
#: Kinds: "int" (strict integer), "str" (string, '' -> null), "list"
#: (semicolon-separated, '' -> null), "value" (pipeline typing via CSVWorker).
EXPERIMENT_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("line_number", "line number", "int"),
    ("id", "id", "str"),
    ("date", "date (YYMMDD)", "str"),
    ("box_calcium_folder_id", "Box Calcium Folder ID", "value"),
    ("calcium_imaging_directory", "calcium imaging directory", "str"),
    ("box_ephys_folder_id", "Box ephys folder ID", "value"),
    ("ephys_directory", "ephys directory", "str"),
    ("rat_weight_kg", "rat weight (kg)", "value"),
    ("systemic_drug", "systemic drug", "str"),
    ("systemic_dose", "systemic dose (% or mg/kg/min)", "value"),
    ("systemic_drug_concentration_mg_per_ml", "systemic drug concentration (mg/mL)", "value"),
    ("total_systemic_time_min", "total systemic time (min)", "value"),
    ("emg_channel", "emg channel", "str"),
    ("events_filename", "events filename", "str"),
    ("channels", "LFP and EEG CSCs", "list"),
    ("comments", "comments", "str"),
)

#: Columns of analysis_parameters.csv owned by the *experiment* document (or
#: identity duplicates); they pass through analysis-document writeback
#: verbatim. Both historical Box-column spellings are covered.
_ANALYSIS_IDENTITY_COLUMNS = frozenset(
    {
        "line number",
        "id",
        "date (YYMMDD)",
        "Box calcium folder ID",
        "Box Calcium Folder ID",
        "calcium imaging directory",
        "Box ephys folder ID",
        "ephys directory",
    }
)


# -- schema loading and validation -------------------------------------------


def load_schema(name: str) -> dict:
    """Load a bundled parameter-document schema (``experiment.v1``,
    ``analysis.cnmfe.v1``)."""
    path = _SCHEMAS_DIR / f"{name}.schema.json"
    if not path.is_file():
        available = sorted(p.name[: -len(".schema.json")] for p in _SCHEMAS_DIR.glob("*.schema.json"))
        raise CSVBridgeError(f"unknown schema {name!r}; available: {available}")
    return json.loads(path.read_text())


def validate_document(document: object, schema: dict) -> tuple[str, ...]:
    """Validate a document against the supported JSON Schema subset.

    Supports: ``type`` (incl. unions), ``const``, ``enum``, ``required``,
    ``properties``, ``additionalProperties: false``, ``items``, ``pattern``
    (``re.search``, per JSON Schema), ``minimum``. This is a dependency-free
    stand-in; adopting a full validator (jsonschema/pydantic) is a separate
    dependency decision recorded in D05's follow-ups.
    """
    errors: list[str] = []
    _validate(document, schema, "$", errors)
    return tuple(errors)


def _is_type(value: object, type_name: str) -> bool:
    if type_name == "object":
        return isinstance(value, dict)
    if type_name == "array":
        return isinstance(value, list)
    if type_name == "string":
        return isinstance(value, str)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "null":
        return value is None
    raise CSVBridgeError(f"unsupported schema type: {type_name!r}")


def _validate(value: object, schema: dict, path: str, errors: list[str]) -> None:
    if "const" in schema:
        if value != schema["const"]:
            errors.append(f"{path}: expected {schema['const']!r}, got {value!r}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']!r}")
        return
    declared = schema.get("type")
    if declared is not None:
        allowed = [declared] if isinstance(declared, str) else list(declared)
        if not any(_is_type(value, t) for t in allowed):
            errors.append(f"{path}: expected {allowed}, got {type(value).__name__}")
            return
    if isinstance(value, str) and "pattern" in schema:
        if not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']!r}")
    if _is_type(value, "number") and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{path}: {value!r} below minimum {schema['minimum']!r}")
    if isinstance(value, dict):
        for required in schema.get("required", ()):
            if required not in value:
                errors.append(f"{path}: missing required property {required!r}")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key], f"{path}.{key}", errors)
            elif additional is False:
                errors.append(f"{path}.{key}: unexpected property")
            elif isinstance(additional, dict):
                _validate(item, additional, f"{path}.{key}", errors)
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]", errors)


# -- CSV row access -----------------------------------------------------------


def _read_rows(csv_path: Path) -> tuple[list[str], list[list[str]]]:
    if not csv_path.is_file():
        raise CSVBridgeError(f"CSV not found: {csv_path}")
    with open(csv_path, newline="") as fh:
        rows = [row for row in csv.reader(fh)]
    if not rows:
        raise CSVBridgeError(f"CSV is empty: {csv_path}")
    header, data = rows[0], rows[1:]
    for row_num, row in enumerate(data, start=2):
        if row and any(row) and len(row) != len(header):
            raise CSVBridgeError(
                f"{csv_path} row {row_num} has {len(row)} fields but the "
                f"header has {len(header)} columns; fix the CSV first"
            )
    return header, data


def _find_row(header: list[str], data: list[list[str]], line_num: int, csv_path: Path) -> int:
    if "line number" not in header:
        raise CSVBridgeError(f"{csv_path} has no 'line number' column")
    column = header.index("line number")
    matches = [index for index, row in enumerate(data) if row and any(row) and row[column].strip() == str(line_num)]
    if not matches:
        raise CSVBridgeError(f"line {line_num} not found in {csv_path}")
    if len(matches) > 1:
        raise CSVBridgeError(f"line {line_num} appears {len(matches)} times in {csv_path}")
    return matches[0]


def _typed_from_raw(column: str, raw: str, kind: str) -> object:
    """One conversion used by both extract and writeback — symmetric by
    construction. ``value`` kind delegates to the exact typing pipelines see."""
    if kind == "int":
        try:
            return int(raw.strip())
        except ValueError as exc:
            raise CSVBridgeError(f"column {column!r}: {raw!r} is not an integer") from exc
    if kind == "str":
        return raw if raw.strip() else None
    if kind == "list":
        return raw.split(";") if raw.strip() else None
    from aceneurotools.shared.csv_worker import CSVWorker  # lazy: pulls pandas

    return CSVWorker.convert_data_types({column: raw})[column]


def _serialize_cell(value: object, kind: str) -> str:
    """Canonical CSV cell for a document-edited value; parses back equal
    under the same ``kind`` (the serialize/parse symmetry the bijection
    tests pin down)."""
    if value is None:
        return ""
    if value is True:
        return "TRUE"
    if value is False:
        return "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        if kind == "list":
            return ";".join(str(item) for item in value)
        return json.dumps(value)
    return str(value)


# -- extract ------------------------------------------------------------------


def _passthrough(header: list[str], row: list[str]) -> dict:
    return {"columns": list(header), "raw": dict(zip(header, row))}


def _build_experiment_doc(header: list[str], row: list[str]) -> dict:
    raw = dict(zip(header, row))
    doc: dict = {"schema": EXPERIMENT_SCHEMA}
    for json_key, column, kind in EXPERIMENT_FIELDS:
        if column in raw:
            doc[json_key] = _typed_from_raw(column, raw[column], kind)
    doc["_csv"] = _passthrough(header, row)
    return doc


def _build_analysis_doc(header: list[str], row: list[str]) -> dict:
    raw = dict(zip(header, row))
    doc: dict = {
        "schema": ANALYSIS_CNMFE_SCHEMA,
        "line_number": _typed_from_raw("line number", raw["line number"], "int"),
        "id": _typed_from_raw("id", raw.get("id", ""), "str"),
        "date": _typed_from_raw("date (YYMMDD)", raw.get("date (YYMMDD)", ""), "str"),
        "comments": _typed_from_raw("comments", raw.get("comments", ""), "str"),
    }
    doc["params"] = {
        column: _typed_from_raw(column, cell, "value")
        for column, cell in raw.items()
        if column not in _ANALYSIS_IDENTITY_COLUMNS and column != "comments"
    }
    doc["_csv"] = _passthrough(header, row)
    return doc


def _write_document(path: Path, doc: dict, schema_name: str) -> None:
    errors = validate_document(doc, load_schema(schema_name))
    if errors:
        raise CSVBridgeError(f"extracted document {path.name} fails its schema: " + "; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")


def extract(
    line_num: int,
    project_path: str | Path,
    experiment_dir: str | Path | None = None,
) -> dict[str, Path]:
    """Materialise one experiment's CSV row slice as parameter documents.

    Reads ``experiments.csv`` (required) and ``analysis_parameters.csv``
    (optional — skipped when the file or the row is absent) from
    ``project_path`` and writes canonical JSON documents into the workspace's
    ``parameters/`` directory (``experiment_dir`` defaults to the project
    directory, provisional until D06). Returns ``{document name: path}``.
    """
    project_path = Path(project_path)
    workspace = ExperimentWorkspace(Path(experiment_dir) if experiment_dir is not None else project_path)
    written: dict[str, Path] = {}

    header, data = _read_rows(project_path / EXPERIMENTS_CSV)
    row = data[_find_row(header, data, line_num, project_path / EXPERIMENTS_CSV)]
    experiment_path = workspace.parameters_dir / EXPERIMENT_DOC
    _write_document(experiment_path, _build_experiment_doc(header, row), "experiment.v1")
    written[EXPERIMENT_DOC] = experiment_path

    analysis_csv = project_path / ANALYSIS_CSV
    if analysis_csv.is_file():
        header, data = _read_rows(analysis_csv)
        try:
            row = data[_find_row(header, data, line_num, analysis_csv)]
        except CSVBridgeError:
            row = None  # no analysis row for this experiment — experiment doc only
        if row is not None:
            analysis_path = workspace.parameters_dir / ANALYSIS_CNMFE_DOC
            _write_document(analysis_path, _build_analysis_doc(header, row), "analysis.cnmfe.v1")
            written[ANALYSIS_CNMFE_DOC] = analysis_path
    return written


# -- writeback ----------------------------------------------------------------


def _typed_now(doc: dict, column: str) -> tuple[bool, object]:
    """Current typed value the document holds for a CSV column, if any."""
    if doc.get("schema") == EXPERIMENT_SCHEMA:
        for json_key, mapped_column, _kind in EXPERIMENT_FIELDS:
            if mapped_column == column:
                return True, doc.get(json_key)
        return False, None
    if column in _ANALYSIS_IDENTITY_COLUMNS:
        return False, None  # owned by the experiment document
    if column == "comments":
        return True, doc.get("comments")
    if column in doc.get("params", {}):
        return True, doc["params"][column]
    return False, None


def _kind_for(doc: dict, column: str) -> str:
    if doc.get("schema") == EXPERIMENT_SCHEMA:
        for _json_key, mapped_column, kind in EXPERIMENT_FIELDS:
            if mapped_column == column:
                return kind
    return "str" if column == "comments" else "value"


def _write_row_back(csv_path: Path, doc: dict) -> None:
    header, data = _read_rows(csv_path)
    known = doc["_csv"]["raw"]
    vanished = [column for column in doc["_csv"]["columns"] if column not in header]
    if vanished:
        raise CSVBridgeError(f"{csv_path} no longer has column(s) {vanished}; re-extract before writeback")
    target = _find_row(header, data, doc["line_number"], csv_path)

    new_row: list[str] = []
    for index, column in enumerate(header):
        current_cell = data[target][index]
        has_typed, typed_value = _typed_now(doc, column)
        if column not in known or not has_typed:
            new_row.append(current_cell)  # passthrough / post-extract columns
            continue
        kind = _kind_for(doc, column)
        if _typed_from_raw(column, known[column], kind) == typed_value:
            new_row.append(current_cell)  # document did not change this field
        else:
            new_row.append(_serialize_cell(typed_value, kind))
    data[target] = new_row

    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(data)


def writeback(
    experiment_dir: str | Path,
    project_path: str | Path | None = None,
) -> tuple[Path, ...]:
    """Write the workspace's parameter documents back into the CSV rows.

    The inverse of :func:`extract`: document-edited fields overwrite their CSV
    cells (canonical serialization); untouched fields and unknown columns keep
    their current CSV bytes, so concurrent CSV edits to *other* fields are
    never clobbered. Returns the CSV paths updated.
    """
    workspace = ExperimentWorkspace(Path(experiment_dir))
    project_path = Path(project_path) if project_path is not None else workspace.root
    updated: list[Path] = []

    targets = (
        (EXPERIMENT_DOC, "experiment.v1", project_path / EXPERIMENTS_CSV),
        (ANALYSIS_CNMFE_DOC, "analysis.cnmfe.v1", project_path / ANALYSIS_CSV),
    )
    for doc_name, schema_name, csv_path in targets:
        doc_path = workspace.parameters_dir / doc_name
        if not doc_path.is_file():
            continue
        doc = json.loads(doc_path.read_text())
        errors = validate_document(doc, load_schema(schema_name))
        if errors:
            raise CSVBridgeError(f"{doc_path} fails its schema: " + "; ".join(errors))
        _write_row_back(csv_path, doc)
        updated.append(csv_path)
    if not updated:
        raise CSVBridgeError(f"no parameter documents found in {workspace.parameters_dir}")
    return tuple(updated)


# -- import (root revision) ---------------------------------------------------


@dataclass(frozen=True)
class ImportResult:
    """Outcome of importing an experiment's legacy CSV state into history."""

    revision: str
    documents: tuple[str, ...]
    root: bool  # True when this import created the experiment's first revision


def import_experiment(
    line_num: int,
    project_path: str | Path,
    experiment_dir: str | Path | None = None,
    author: str | None = None,
) -> ImportResult:
    """Extract an experiment's CSV state and record it as a revision.

    On a fresh experiment this creates the "imported from CSV" **root
    revision** — every history begins with a faithful copy of its legacy
    state (plan §Phase 4). Re-importing unchanged state reuses the current
    head instead of fabricating an empty revision.
    """
    project_path = Path(project_path)
    directory = Path(experiment_dir) if experiment_dir is not None else project_path
    try:
        evc = ExperimentVersionControl.open(directory)
    except RepositoryNotFoundError:
        evc = ExperimentVersionControl.init(directory, workspace=True)
    was_unborn = evc.repo.refs.head_oid() is None

    written = extract(line_num, project_path, directory)
    try:
        revision = evc.record(f"imported from CSV: line {line_num}", author=author)
    except NothingToRecordError:
        revision = evc.repo.refs.head_oid()
        assert revision is not None
        was_unborn = False
    return ImportResult(revision=revision, documents=tuple(sorted(written)), root=was_unborn)
