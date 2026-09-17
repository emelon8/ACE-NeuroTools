"""Application coordinator; transports do not make scientific decisions."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from aceneurotools.evc.api import ExperimentVersionControl

from .. import documents
from ..workspaces import WorkspaceRegistry, confined
from .common import atomic_json, read_json
from .detectors import DetectorRegistry
from .models import Candidate, Selection, Setup
from .pipelines import PipelineRegistry, QuestionEngine
from .storage import ImportStore


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

    def selection(self, key: str, selection: Selection) -> tuple[dict, Candidate, object]:
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
            else:
                name = setup.name.strip()
                if not re.fullmatch(r"[\w][\w .-]{0,99}", name) or name.endswith((".", " ")):
                    raise ValueError(
                        "Experiment names must begin with a letter/number and use letters, numbers, spaces, dots or hyphens."
                    )
                root = confined(self.registry.project, name)
                # mkdir, not exist_ok: no overwrite or automatic merging of experiment names.
                root.mkdir(exist_ok=False)
                ExperimentVersionControl.init(root, workspace=True)
            evc = ExperimentVersionControl.open(root)
            # A user may have customized EVC ignores. Never import bulk unless artifacts is excluded.
            ignore = (root / ".evc/ignore").read_text()
            if "artifacts/" not in {line.strip() for line in ignore.splitlines()}:
                raise ValueError("This experiment must exclude artifacts/ in .evc/ignore before importing recordings.")
            target = confined(root, f"artifacts/recordings/{key}")
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise documents.ConflictError("Recording destination already exists; no files were replaced.")
            # Keep staging as the recoverable source until the setup is fully recorded.
            shutil.copytree(self.imports.directory(key) / "files", target)
            configuration_path = f"parameters/workflow.{key}.json"
            configuration = {
                "schema": "ace-workflow-v1",
                "id": key,
                "recording_root": str(target.relative_to(root)),
                "candidate": candidate.to_dict(),
                "pipeline": pipeline.id,
                "answers": answers,
                "effective": effective,
                "inputs": [{k: f[k] for k in ("path", "size", "sha256")} for f in value["files"]],
                "association": "existing" if existing else "new",
                "experiment_name": root.name,
                "meaning": "Subject, condition and treatment are not inferred; record them in experiment notes when relevant.",
            }
            atomic_json(confined(root, configuration_path), configuration)
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
            workspace = self.registry.register(root)
            value.update(state="attached", workspace=workspace, configuration=configuration_path, revision=revision)
            self.imports.write(value)
            shutil.rmtree(self.imports.directory(key) / "files")
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
        original = self.imports.read(value["id"])
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
