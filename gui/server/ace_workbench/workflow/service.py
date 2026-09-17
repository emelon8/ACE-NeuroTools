"""Application coordinator; transports do not make scientific decisions."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from aceneurotools.evc.api import ExperimentVersionControl

from .. import documents
from ..workspaces import WorkspaceRegistry, confined
from .common import atomic_json, file_hash, read_json
from .detectors import DetectorRegistry
from .models import Candidate, Selection, Setup
from .pipelines import Pipeline, PipelineRegistry, QuestionEngine
from .storage import RESERVE, ImportStore, relative_path


class WorkflowService:
    def __init__(self, registry: WorkspaceRegistry):
        self.registry = registry
        self.imports = ImportStore(registry.project)
        self.detectors = DetectorRegistry()
        self.pipelines = PipelineRegistry()
        self.questions = QuestionEngine()

    def inspect(self, key: str) -> dict:
        with self.imports.lock:
            value = self.imports.finish(key)
            if value["state"] == "attached":
                return value
            candidates = self.detectors.inspect(self.imports.directory(key) / "files", value["files"])
            value["candidates"] = [c.to_dict() for c in candidates]
            self.imports.write(value)
            return self.describe(value)

    def describe(self, value: dict) -> dict:
        result = dict(value)
        result["candidates"] = [
            {**c, "pipelines": self.pipelines.describe(Candidate(**c))} for c in value.get("candidates", [])
        ]
        return result

    def selection(self, key: str, selection: Selection) -> tuple[dict, Candidate, Pipeline]:
        value = self.imports.read(key)
        if value["state"] not in {"inspected", "attached"}:
            raise ValueError("Finish copying all files before configuring an experiment.")
        candidate = next((Candidate(**c) for c in value.get("candidates", []) if c["id"] == selection.candidate), None)
        if candidate is None:
            raise ValueError("Choose a detected recording.")
        return value, candidate, self.pipelines.get(selection.pipeline, candidate)

    def questionnaire(self, key: str, selection: Selection) -> dict:
        _, candidate, pipeline = self.selection(key, selection)
        return {
            "questions": [q.to_dict() for q in pipeline.questions(candidate)],
            "known": candidate.metadata,
            "blockers": candidate.blockers if pipeline.scientific else [],
            "description": pipeline.description,
        }

    def setup(self, key: str, setup: Setup) -> dict:
        with self.imports.lock, self.registry.lock:
            value, candidate, pipeline = self.selection(key, setup)
            if value["state"] == "attached":
                raise documents.ConflictError(
                    "This import is already attached. Reopen its saved workflow configuration."
                )
            if pipeline.scientific and candidate.blockers:
                raise ValueError("; ".join(candidate.blockers))
            answers = self.questions.validate(pipeline, candidate, setup.answers)
            effective = pipeline.effective(candidate, answers)
            existing = setup.destination != "new"
            if existing:
                self.registry.require_idle(setup.destination)
                root = self.registry.root(setup.destination)
                if not self.registry.evc(setup.destination).status().clean:
                    raise documents.ConflictError(
                        "Record or restore existing experiment changes before attaching a recording."
                    )
                ignore = confined(root, ".evc/ignore").read_text()
                if "artifacts/" not in {line.strip() for line in ignore.splitlines()}:
                    raise ValueError(
                        "This experiment must exclude artifacts/ in .evc/ignore before importing recordings."
                    )
            else:
                name = relative_path(setup.name.strip())
                if not re.fullmatch(r"[\w][\w .-]{0,99}", name):
                    raise ValueError(
                        "Experiment names must begin with a letter/number and use letters, numbers, spaces, dots or hyphens."
                    )
                root = confined(self.registry.project, name)
                if any(child.name.casefold() == name.casefold() for child in self.registry.project.iterdir()):
                    raise documents.ConflictError(
                        "An experiment or folder with that name already exists. Choose another name or an existing experiment."
                    )
            target = confined(root, f"artifacts/recordings/{key}")
            configuration_path = f"parameters/workflow.{key}.json"
            configuration = {
                "schema": "ace-workflow-v1",
                "id": key,
                "recording_root": target.relative_to(root).as_posix(),
                "candidate": candidate.to_dict(),
                "pipeline": pipeline.id,
                "answers": answers,
                "effective": effective,
                "inputs": [{k: f[k] for k in ("path", "size", "sha256")} for f in value["files"]],
                "association": "existing" if existing else "new",
                "experiment_name": root.name,
                "meaning": "Subject, condition and treatment are not inferred; record them in experiment notes when relevant.",
            }
            documents.parse_document(configuration_path, json.dumps(configuration, indent=2))
            if (
                shutil.disk_usage(root if existing else root.parent).free
                < sum(f["size"] for f in value["files"]) + RESERVE
            ):
                raise ValueError(
                    "Insufficient experiment disk space for the recording copy; staged files are retained."
                )
            config_target = confined(root, configuration_path)
            if target.exists() or config_target.exists():
                raise documents.ConflictError("Recording destination already exists; no files were replaced.")
            committed = False
            created_root = False
            try:
                if not existing:
                    root.mkdir(exist_ok=False)
                    created_root = True
                    ExperimentVersionControl.init(root, workspace=True)
                evc = ExperimentVersionControl.open(root)
                target.parent.mkdir(parents=True, exist_ok=True)
                # Retain the staging source until EVC records the complete setup.
                shutil.copytree(self.imports.directory(key) / "files", target)
                for item in configuration["inputs"]:
                    copied = confined(target, item["path"])
                    if copied.stat().st_size != item["size"] or file_hash(copied) != item["sha256"]:
                        raise ValueError(f"Copied input failed integrity verification: {item['path']}")
                atomic_json(config_target, configuration)
                if not existing:
                    atomic_json(
                        root / "parameters/experiment.json",
                        {
                            "schema": "aceneuro-experiment-v1",
                            "line_number": 1,
                            "id": "",
                            "date": None,
                            "comments": "Imported through the workbench. Subject and treatment have not been specified.",
                            "_csv": {"columns": [], "raw": {}},
                        },
                    )
                revision = evc.record(f"Attach recording and configure {pipeline.label}", author=self.registry.author)
                committed = True
                workspace = self.registry.register(root)
                value.update(state="attached", workspace=workspace, configuration=configuration_path, revision=revision)
                self.imports.write(value)
                # An ignored provenance copy travels with the experiment if its project changes.
                atomic_json(confined(root, f"artifacts/recordings/{key}.import.json"), value)
            except Exception:
                if not committed:
                    if created_root:
                        shutil.rmtree(root)
                    elif existing:
                        shutil.rmtree(target, ignore_errors=True)
                        config_target.unlink(missing_ok=True)
                raise
            # Cleanup failure must not make a successfully committed import look unsuccessful.
            shutil.rmtree(self.imports.directory(key) / "files", ignore_errors=True)
            return {"workspace": workspace, "configuration": configuration_path, "revision": revision}

    def configurations(self, workspace: str) -> list[dict]:
        root = self.registry.root(workspace)
        result = []
        for path in documents.list_documents(self.registry, workspace):
            if Path(path).name.startswith("workflow."):
                value = read_json(confined(root, path))
                result.append(
                    {
                        "path": path,
                        "pipeline": value.get("pipeline"),
                        "label": value.get("candidate", {}).get("label", path),
                    }
                )
        return result

    def configuration(self, workspace: str, path: str) -> dict:
        document = documents.read_document(self.registry, workspace, path)
        value = documents.parse_document(path, document["text"])
        if value.get("schema") != "ace-workflow-v1":
            raise ValueError("Choose a saved workflow configuration.")
        # Immutable import provenance is authoritative, even if JSON was edited externally.
        try:
            original = self.imports.read(value["id"])
        except FileNotFoundError:
            original = read_json(
                confined(self.registry.root(workspace), f"artifacts/recordings/{value['id']}.import.json")
            )
            original["workspace"] = next(item for item in self.registry.list() if item["id"] == workspace)
            self.imports.directory(value["id"]).mkdir(parents=True, exist_ok=True)
            self.imports.write(original)
        if original.get("workspace", {}).get("id") != workspace or original.get("configuration") != path:
            raise ValueError("Configuration does not belong to this imported recording.")
        candidate = next((Candidate(**c) for c in original["candidates"] if c["id"] == value["candidate"]["id"]), None)
        if candidate is None or candidate.to_dict() != value["candidate"]:
            raise ValueError("Detection evidence changed. Reimport the recording to replace its metadata.")
        inputs = [{k: f[k] for k in ("path", "size", "sha256")} for f in original["files"]]
        if value["inputs"] != inputs or value["recording_root"] != f"artifacts/recordings/{value['id']}":
            raise ValueError("Input paths and hashes are immutable; reimport changed recordings.")
        pipeline = self.pipelines.get(value["pipeline"], candidate)
        if pipeline.scientific and candidate.blockers:
            raise ValueError("; ".join(candidate.blockers))
        answers = self.questions.validate(pipeline, candidate, value["answers"])
        expected = pipeline.effective(candidate, answers)
        if value["effective"] != expected:
            raise ValueError("Effective settings disagree with the answers. Reconfigure through Import & Run.")
        return value

    def reconfigure(self, workspace: str, path: str, selection: Selection) -> dict:
        with self.registry.lock:
            self.registry.require_idle(workspace)
            value = self.configuration(workspace, path)
            _, candidate, pipeline = self.selection(value["id"], selection)
            if pipeline.scientific and candidate.blockers:
                raise ValueError("; ".join(candidate.blockers))
            answers = self.questions.validate(pipeline, candidate, selection.answers)
            value.update(
                candidate=candidate.to_dict(),
                pipeline=pipeline.id,
                answers=answers,
                effective=pipeline.effective(candidate, answers),
            )
            if not self.registry.evc(workspace).status().clean:
                raise documents.ConflictError("Record other parameter changes before reconfiguring a workflow.")
            atomic_json(confined(self.registry.root(workspace), path), value)
            revision = self.registry.evc(workspace).record("Update workflow settings", author=self.registry.author)
            return {"configuration": path, "revision": revision}
