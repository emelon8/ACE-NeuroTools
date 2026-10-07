"""Project snapshots and staged CSV edits using existing CSV utilities."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aceneurotools.shared.csv_worker import CSVWorker, append_row_csv, update_csv_cell
from gui.fields import describe, validate


class ProjectError(ValueError):
    """A project file cannot be displayed safely."""


class ProjectChangedError(ProjectError):
    """The user must reload a snapshot changed by another application."""


def _read_table(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
    # The core offers a one-experiment reader, not a whole-project reader.
    # Enumerate raw rows once, then use CSVWorker for selected-row interpretation.
    try:
        content = path.read_bytes()
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProjectError(f"{path.name} is not UTF-8. Choose a UTF-8 CSV; the original file was not changed.") from exc
    except OSError as exc:
        raise ProjectError(f"Cannot read {path}: {exc.strerror or str(exc)}") from exc
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, [])
        if not header or "line number" not in header:
            raise ProjectError(f"{path.name} must contain the exact column 'line number'.")
        if any(not name for name in header) or len(set(header)) != len(header):
            raise ProjectError(f"{path.name} has empty or repeated column names. Columns must be unique.")
        rows = []
        seen = set()
        for row in reader:
            if not any(value.strip() for value in row):
                continue
            if len(row) != len(header):
                raise ProjectError(
                    f"{path.name}, row ending on line {reader.line_num}: "
                    f"expected {len(header)} columns, found {len(row)}. Check quoting and trailing commas."
                )
            record = dict(zip(header, row))
            identifier = record["line number"]
            if not identifier.strip() or identifier != identifier.strip():
                raise ProjectError(
                    f"{path.name}, line {reader.line_num}: experiment number is blank or contains outer spaces."
                )
            if identifier in seen:
                raise ProjectError(f"{path.name}: experiment number {identifier} occurs more than once.")
            seen.add(identifier)
            rows.append(record)
    except csv.Error as exc:
        raise ProjectError(f"{path.name} contains invalid CSV: {exc}") from exc
    return header, rows, hashlib.sha256(content).hexdigest()


def _display_value(value: Any) -> Any:
    """Make existing reader output JSON-safe without changing CSV semantics."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _display_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_display_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        import math

        return value if math.isfinite(value) else None
    # Some pandas/numpy scalar values need conversion to their Python equivalent.
    if hasattr(value, "item"):
        return _display_value(value.item())
    return str(value)


@dataclass
class Project:
    path: Path
    metadata_columns: list[str]
    experiments: dict[str, dict[str, str]]
    parameter_columns: list[str]
    parameters: dict[str, dict[str, str]]
    digests: dict[str, str | None]
    warnings: list[str]
    parameter_error: str | None = None
    default_experiment: str | None = None

    @classmethod
    def open(cls, location: str | Path) -> Project:
        path = Path(location).expanduser().resolve()
        if path.is_file():
            if path.name != "experiments.csv":
                raise ProjectError("Select a project folder or its experiments.csv file.")
            path = path.parent
        if not path.is_dir():
            raise ProjectError(f"Project folder does not exist: {path}")
        columns, rows, digest = _read_table(path / "experiments.csv")
        experiments = {row["line number"]: row for row in rows}
        warnings = []
        digests: dict[str, str | None] = {"experiments.csv": digest}
        parameter_columns, parameter_rows, parameter_error = [], [], None
        parameter_path = path / "analysis_parameters.csv"
        if parameter_path.exists():
            try:
                parameter_columns, parameter_rows, parameter_digest = _read_table(parameter_path)
                digests["analysis_parameters.csv"] = parameter_digest
            except ProjectError as exc:
                parameter_error = str(exc)
                # Keep metadata available, but never represent invalid settings as defaults.
                try:
                    digests["analysis_parameters.csv"] = hashlib.sha256(parameter_path.read_bytes()).hexdigest()
                except OSError:
                    digests["analysis_parameters.csv"] = None
                warnings.append(f"Analysis settings unavailable: {exc}")
        else:
            digests["analysis_parameters.csv"] = None
            warnings.append(
                "analysis_parameters.csv is absent. No per-experiment settings are available in this project."
            )
        parameters = {row["line number"]: row for row in parameter_rows}
        defaults_path = path / ".ace-gui-project.json"
        default_experiment = None
        if defaults_path.exists():
            try:
                settings = json.loads(defaults_path.read_text(encoding="utf-8"))
                default_experiment = settings.get("default_experiment")
                if default_experiment is not None and (
                    not isinstance(default_experiment, str)
                    or default_experiment not in parameters
                    or default_experiment not in experiments
                ):
                    warnings.append("The saved default experiment no longer has analysis settings.")
                    default_experiment = None
            except (OSError, ValueError, AttributeError):
                warnings.append("Project defaults could not be read.")
        digests[defaults_path.name] = (
            hashlib.sha256(defaults_path.read_bytes()).hexdigest() if defaults_path.exists() else None
        )
        if not parameter_error and parameter_path.exists():
            missing = [key for key in experiments if key not in parameters]
            extra = [key for key in parameters if key not in experiments]
            if missing:
                warnings.append(
                    f"{len(missing)} experiments have no matching analysis-parameter record: {', '.join(missing)}."
                )
            if extra:
                warnings.append(f"Parameter records have no matching experiment: {', '.join(extra)}.")
        return cls(
            path,
            columns,
            experiments,
            parameter_columns,
            parameters,
            digests,
            warnings,
            parameter_error,
            default_experiment,
        )

    @property
    def id(self) -> str:
        return hashlib.sha256(str(self.path).encode()).hexdigest()[:16]

    def ensure_current(self) -> None:
        for name, expected in self.digests.items():
            path = self.path / name
            try:
                actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
            except OSError as exc:
                raise ProjectChangedError(
                    f"Cannot recheck {name}. Reload the project: {exc.strerror or str(exc)}"
                ) from exc
            if actual != expected:
                raise ProjectChangedError(
                    f"{name} changed since it was opened. Reload the project to see the current values."
                )

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.path.name,
            "path": str(self.path),
            "count": len(self.experiments),
            "parameter_count": len(self.parameters),
            "warnings": self.warnings,
            "missing_parameters": [number for number in self.experiments if number not in self.parameters],
            "orphan_parameters": [number for number in self.parameters if number not in self.experiments],
            "parameter_error": self.parameter_error,
            "default_experiment": self.default_experiment,
            "versions": self.digests,
            "metadata_columns": self.metadata_columns,
            "parameter_columns": self.settings_columns(),
            "experiments": [
                {
                    "number": number,
                    "subject": row.get("id", ""),
                    "date": row.get("date (YYMMDD)", ""),
                    "title": row.get("title", "") or row.get("experiment title", ""),
                    "miniscope": bool(row.get("calcium imaging directory", "").strip()),
                    "ephys": bool(row.get("ephys directory", "").strip()),
                    "box": bool(
                        row.get("Box Calcium Folder ID", "").strip() or row.get("Box ephys folder ID", "").strip()
                    ),
                    "has_parameters": number in self.parameters,
                    "parameter_error": self.parameter_error is not None,
                    "search": " ".join(row.values()).lower(),
                }
                for number, row in self.experiments.items()
            ],
        }

    def inspect(self, number: str) -> dict[str, Any]:
        self.ensure_current()
        if number not in self.experiments:
            raise ProjectError(f"Experiment {number} was not found in this project.")
        metadata = self.experiments[number]
        parameters = self.parameters.get(number)
        interpretation = {}
        reader_errors = []
        for name, raw in (("experiments.csv", metadata), ("analysis_parameters.csv", parameters)):
            if raw is None:
                continue
            try:
                original = CSVWorker.csv_row_to_dict(self.path / name, number)
                if original is None:
                    reader_errors.append(f"The existing CSV reader could not read experiment {number} from {name}.")
                else:
                    interpretation[name] = _display_value(CSVWorker.convert_data_types(original))
            except (ValueError, TypeError, OSError) as exc:
                reader_errors.append(f"Existing CSV reader: {name}: {exc}")
        # Recheck after reader calls so concurrent edits never mix file versions.
        self.ensure_current()
        recordings = []
        for label, directory, box_column in (
            ("Calcium imaging", "calcium imaging directory", "Box Calcium Folder ID"),
            ("Electrophysiology", "ephys directory", "Box ephys folder ID"),
        ):
            box_id = metadata.get(box_column, "").strip()
            recordings.append(
                {
                    "name": label,
                    "directory": metadata.get(directory, ""),
                    "box_id": box_id,
                    # Raw strings retain exact folder IDs, independent of pandas coercion.
                    "box_url": f"https://app.box.com/folder/{box_id}"
                    if box_id.isascii() and box_id.isdigit()
                    else None,
                }
            )
        return {
            "number": number,
            "metadata": metadata,
            "metadata_columns": self.metadata_columns,
            "parameters": parameters,
            "parameter_columns": self.parameter_columns,
            "fields": {
                "metadata": [describe(key) for key in self.metadata_columns],
                "parameters": [describe(key, settings=True) for key in self.settings_columns()],
            },
            "versions": self.digests,
            "parameter_error": self.parameter_error,
            "recordings": recordings,
            "interpreted": interpretation,
            "reader_errors": reader_errors,
        }

    def settings_columns(self) -> list[str]:
        if self.parameter_columns:
            return self.parameter_columns
        if self.parameter_error:
            return []
        # Reuse the installed schema, but never create a template experiment or defaults.
        from aceneurotools.shared import csv_worker

        template = Path(csv_worker.__file__).parent / "metadata_templates" / "analysis_parameters_template.csv"
        # Only the existing schema is needed. Do not import its example/default row.
        with template.open(encoding="utf-8-sig", newline="") as handle:
            return next(csv.reader(handle))

    def set_default_experiment(self, number: str | None, versions: dict) -> Project:
        self.ensure_current()
        if versions != self.digests:
            raise ProjectChangedError("This project changed. Reload before changing its default experiment.")
        if number is not None and (number not in self.experiments or number not in self.parameters):
            raise ProjectError("Choose an experiment with saved analysis settings as the default.")
        path = self.path / ".ace-gui-project.json"
        if path.is_symlink():
            raise ProjectError("Project defaults cannot be saved through a linked file.")
        descriptor, name = tempfile.mkstemp(prefix=".ace-default-", suffix=".json", dir=self.path)
        staged = Path(name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"default_experiment": number}, handle)
                handle.write("\n")
            self.ensure_current()
            os.replace(staged, path)
        finally:
            staged.unlink(missing_ok=True)
        return Project.open(self.path)

    def create_experiment(
        self, number: str, metadata: dict[str, str], parameters: dict[str, str], versions: dict
    ) -> tuple[Project, str | None]:
        self.ensure_current()
        if versions != self.digests:
            raise ProjectChangedError("This project changed. Reload before creating the experiment.")
        if not isinstance(number, str) or not number or number != number.strip() or number in self.experiments:
            raise ProjectError("Enter a new, unique experiment number.")
        if not isinstance(metadata, dict) or not isinstance(parameters, dict):
            raise ProjectError("Enter valid experiment details and analysis settings.")
        for values, columns in ((metadata, self.metadata_columns), (parameters, self.settings_columns())):
            if any(
                not isinstance(key, str) or not isinstance(value, str) or key not in columns or key == "line number"
                for key, value in values.items()
            ):
                raise ProjectError("Experiment fields must match this project's CSV columns.")
            for key, value in values.items():
                validate(key, value)
        # The metadata writer already stages the CSV and makes a backup. If the
        # second write fails, restore the original metadata before returning.
        saved, backup = self.save(number, "metadata", metadata, versions, create=True, allow_new_metadata=True)
        try:
            if parameters:
                saved, _ = saved.save(number, "parameters", parameters, saved.digests, create=True)
        except Exception:
            if backup:
                os.replace(backup, self.path / "experiments.csv")
            raise
        return saved, backup

    def save(
        self,
        number: str,
        section: str,
        changes: dict[str, str],
        versions: dict,
        create: bool = False,
        *,
        new_columns: tuple[str, ...] = (),
        allow_new_metadata: bool = False,
    ) -> tuple[Project, str | None]:
        """Save one selected record/file. Stage existing utilities, back up, then replace."""
        self.ensure_current()
        if versions != self.digests:
            raise ProjectChangedError("This experiment was saved elsewhere. Reload before saving your changes.")
        if (
            (number not in self.experiments and not (section == "metadata" and create and allow_new_metadata))
            or not isinstance(section, str)
            or section not in {"metadata", "parameters"}
        ):
            raise ProjectError("Choose an existing experiment and a valid section to save.")
        if not isinstance(changes, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in changes.items()
        ):
            raise ProjectError("Each edited field must contain text.")
        filename = "experiments.csv" if section == "metadata" else "analysis_parameters.csv"
        if section == "parameters" and self.parameter_error:
            raise ProjectError(f"Settings cannot be saved until the file is repaired: {self.parameter_error}")
        columns = list(self.metadata_columns if section == "metadata" else self.settings_columns())
        additions = (
            [key for key in new_columns if key in changes and key not in columns] if section == "parameters" else []
        )
        columns.extend(additions)
        existing = self.experiments.get(number) if section == "metadata" else self.parameters.get(number)
        if existing is None and not create:
            raise ProjectError("This experiment has no settings record. Choose Add settings first.")
        if "line number" in changes or any(key not in columns for key in changes):
            raise ProjectError("Experiment numbers and column names cannot be changed here.")
        # A missing row is created deliberately; unchanged values are never reinterpreted.
        changes = {key: value for key, value in changes.items() if existing is None or existing.get(key) != value}
        for key, value in changes.items():
            try:
                validate(key, value)
            except ValueError as exc:
                raise ProjectError(str(exc)) from exc
        if not changes and existing is not None:
            return self, None
        path = self.path / filename
        if path.is_symlink():
            raise ProjectError(
                "This CSV is a link to another file. Open the folder containing the original file to edit it."
            )
        original = path.read_bytes() if path.exists() else None
        if (hashlib.sha256(original).hexdigest() if original is not None else None) != self.digests[filename]:
            raise ProjectChangedError("The project files changed. Reload before saving.")
        descriptor, staged_name = tempfile.mkstemp(prefix=".ace-edit-", suffix=".csv", dir=self.path)
        staged = Path(staged_name)
        backup = None
        try:
            with os.fdopen(descriptor, "wb") as handle:
                if original is not None:
                    # DictReader in the existing writer does not strip UTF-8 BOM.
                    handle.write(original.removeprefix(b"\xef\xbb\xbf"))
                else:
                    buffer = io.StringIO(newline="")
                    csv.writer(buffer).writerow(columns)
                    handle.write(buffer.getvalue().encode())
            if original is not None and additions:
                with staged.open(newline="", encoding="utf-8") as handle:
                    records = list(csv.DictReader(handle))
                with staged.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=columns)
                    writer.writeheader()
                    writer.writerows(records)
            if existing is None:
                row = {key: changes.get(key, "") for key in columns}
                row["line number"] = number
                # Existing append helper expects the previous record to end with a newline.
                if staged.read_bytes() and not staged.read_bytes().endswith((b"\n", b"\r")):
                    with staged.open("ab") as handle:
                        handle.write(b"\n")
                append_row_csv(row, staged)
            else:
                for key, value in changes.items():
                    update_csv_cell(value, key, number, staged)
            # Retain UTF-8 BOM when existing utilities rewrite a BOM-bearing file.
            content = staged.read_bytes()
            if original and original.startswith(b"\xef\xbb\xbf") and not content.startswith(b"\xef\xbb\xbf"):
                staged.write_bytes(b"\xef\xbb\xbf" + content)
            _, rows, _ = _read_table(staged)
            saved_row = next((row for row in rows if row["line number"] == number), None)
            if saved_row is None or any(saved_row[key] != value for key, value in changes.items()):
                raise ProjectError("The existing CSV writer could not update this record. Nothing was saved.")
            self.ensure_current()
            if original is not None:
                backups = self.path / ".ace-gui-backups"
                backups.mkdir(exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
                backup_path = backups / f"{path.stem}-{stamp}-{uuid.uuid4().hex[:8]}.csv"
                backup_path.write_bytes(original)
                os.chmod(backup_path, path.stat().st_mode & 0o777)
                backup = str(backup_path)
                os.chmod(staged, path.stat().st_mode & 0o777)
            self.ensure_current()
            os.replace(staged, path)
        finally:
            staged.unlink(missing_ok=True)
        return Project.open(self.path), backup
