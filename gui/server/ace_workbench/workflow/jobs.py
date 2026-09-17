"""Frozen preflight plans, one local worker, cancellation and durable outcomes."""

from __future__ import annotations

import getpass
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from aceneurotools.evc.api import write_manifest

from .. import documents, history
from ..workspaces import confined
from .common import atomic_json, read_json
from .lease import ProjectLease
from .service import WorkflowService
from .storage import identifier

TERMINAL = {"succeeded", "failed", "cancelled", "interrupted"}


class JobManager:
    def __init__(self, service: WorkflowService):
        self.service, self.registry = service, service.registry
        self.directory = confined(self.registry.project, ".ace-workbench")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lease = ProjectLease(confined(self.directory, "server.lock"))
        self.lock = threading.RLock()
        self.process: subprocess.Popen | None = None
        self.current: str | None = None
        self.monitor: threading.Thread | None = None
        self.closed = False
        (self.directory / "jobs").mkdir(exist_ok=True)
        (self.directory / "plans").mkdir(exist_ok=True)
        for path in (self.directory / "jobs").glob("*.json"):
            value = read_json(path)
            if value["state"] not in TERMINAL:
                value.update(
                    state="interrupted",
                    finished=time.time(),
                    detail="Workbench stopped before the outcome was registered. Partial outputs are retained; retry creates a new run.",
                )
                atomic_json(path, value)

    def environment(self) -> dict:
        environment = dict(os.environ)
        package_root = str(Path(__file__).resolve().parents[2])
        # Installed source tree is explicit; no shell expansion or command strings.
        import aceneurotools

        source_root = str(Path(aceneurotools.__file__).resolve().parent.parent)
        environment["PYTHONPATH"] = os.pathsep.join([package_root, source_root])
        environment.update(
            PYTHONUNBUFFERED="1", MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"
        )
        return environment

    def command(self, spec: Path, check=False) -> list[str]:
        python = (
            sys.executable
            if read_json(spec)["configuration"]["pipeline"] in {"inventory", "trace-summary"}
            else self.registry.runner_python
        )
        return [python, "-m", "ace_workbench.workflow.worker", str(spec), *(["--check"] if check else [])]

    def preflight(self, workspace: str, configuration_path: str) -> dict:
        with self.registry.lock:
            self.registry.require_idle(workspace)
            configuration = self.service.configuration(workspace, configuration_path)
            state = history.state(self.registry, workspace)
            if not state["clean"]:
                raise documents.ConflictError("Record or restore parameter changes before preflight.")
            root = self.registry.root(workspace)
            input_root = confined(root, configuration["recording_root"])
            key = uuid.uuid4().hex
            report_path = self.directory / "plans" / f"{key}.check.json"
            spec_path = self.directory / "plans" / f"{key}.spec.json"
            atomic_json(
                spec_path, {"configuration": configuration, "input_root": str(input_root), "output": str(report_path)}
            )
        with (self.directory / "plans" / f"{key}.log").open("w") as log:
            try:
                result = subprocess.run(
                    self.command(spec_path, True),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=self.environment(),
                    cwd=self.directory,
                    timeout=900,
                    check=False,
                )
                report = (
                    read_json(report_path)
                    if report_path.exists()
                    else {
                        "ok": False,
                        "error": "Worker could not start. Configure --runner-python with the scientific environment; inspect the server preflight log.",
                    }
                )
                if result.returncode and report.get("ok"):
                    report = {"ok": False, "error": "Preflight worker exited unexpectedly."}
            except (OSError, subprocess.TimeoutExpired) as exc:
                report = {"ok": False, "error": f"Could not complete preflight: {exc}"}
        required = (
            sum(f["size"] for f in configuration["inputs"]) + report.get("estimated_output_bytes", 0) + 64 * 1024**2
        )
        free = shutil.disk_usage(root).free
        if report.get("ok") and free < required:
            report.update(
                ok=False,
                error="Insufficient free experiment disk space for the private run copy and estimated outputs.",
            )
        with self.registry.lock:
            history.require_version(self.registry, workspace, state["version"])
            plan = {
                "id": key,
                "workspace": workspace,
                "configuration_path": configuration_path,
                "configuration": configuration,
                "version": state["version"],
                "pre_revision": state["head"],
                "input_root": str(input_root),
                "created": time.time(),
                "expires": time.time() + 3600,
                "report": report,
                "required_disk_bytes": required,
                "available_disk_bytes": free,
                "output": str(root / "artifacts/runs" / key),
                "used": False,
            }
            atomic_json(self.directory / "plans" / f"{key}.json", plan)
        return plan

    def path(self, key: str) -> Path:
        return confined(self.directory, f"jobs/{identifier(key)}.json")

    def read(self, key: str) -> dict:
        value = read_json(self.path(key))
        root = self.registry.root(value["workspace"])
        path = confined(root, f"artifacts/runs/{key}/worker.log")
        if path.exists():
            with path.open("rb") as stream:
                stream.seek(max(0, path.stat().st_size - 24000))
                value["log"] = stream.read().decode("utf-8", errors="replace")
        else:
            value["log"] = ""
        return value

    def list(self, workspace: str | None = None) -> list[dict]:
        result = []
        for path in sorted((self.directory / "jobs").glob("*.json"), reverse=True):
            value = read_json(path)
            if value["workspace"] in self.registry.roots and (workspace is None or value["workspace"] == workspace):
                result.append(value)
        return sorted(result, key=lambda item: item["created"], reverse=True)

    def launch(self, key: str) -> dict:
        with self.lock, self.registry.lock:
            if self.closed or self.current is not None:
                raise documents.ConflictError(
                    "One local run is already active. Wait or cancel it before starting another."
                )
            plan_path = confined(self.directory, f"plans/{identifier(key)}.json")
            plan = read_json(plan_path)
            if plan["used"] or time.time() > plan["expires"] or not plan["report"].get("ok"):
                raise documents.ConflictError("This plan is expired, already used, or blocked. Run preflight again.")
            workspace = plan["workspace"]
            self.registry.require_idle(workspace)
            history.require_version(self.registry, workspace, plan["version"])
            if self.service.configuration(workspace, plan["configuration_path"]) != plan["configuration"]:
                raise documents.ConflictError("Configuration changed; run preflight again.")
            directory = confined(self.registry.root(workspace), f"artifacts/runs/{key}")
            if shutil.disk_usage(self.registry.root(workspace)).free < plan["required_disk_bytes"]:
                raise documents.ConflictError("Free disk space changed since preflight. Review a new plan.")
            directory.mkdir(parents=True, exist_ok=False)
            job = {
                "id": key,
                "workspace": workspace,
                "pipeline": plan["configuration"]["pipeline"],
                "configuration_path": plan["configuration_path"],
                "state": "running",
                "created": time.time(),
                "finished": None,
                "detail": "Verifying inputs and creating a private run copy",
                "output": str(directory / "outputs"),
                "pre_revision": plan["pre_revision"],
                "post_revision": None,
            }
            approval = {
                "time": job["created"],
                "researcher": self.registry.author or getpass.getuser(),
                "action": "Run approved configuration",
                "plan": key,
            }
            spec = {
                "configuration": plan["configuration"],
                "input_root": plan["input_root"],
                "output": str(directory),
                "environment": plan["report"]["environment"],
                "plan": key,
                "pre_revision": plan["pre_revision"],
                "parent_pid": os.getpid(),
                "approval": approval,
            }
            plan.update(used=True, approval=approval)
            atomic_json(directory / "approved-plan.json", plan)
            atomic_json(directory / "worker-spec.json", spec)
            atomic_json(plan_path, plan)
            atomic_json(self.path(key), job)
            self.registry.active.add(workspace)
            try:
                with (directory / "worker.log").open("w") as log:
                    self.process = subprocess.Popen(
                        self.command(directory / "worker-spec.json"),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        env=self.environment(),
                        cwd=directory,
                        start_new_session=os.name != "nt",
                    )
                self.current = key
                self.monitor = threading.Thread(target=self._monitor, args=(key, self.process, plan), daemon=True)
                self.monitor.start()
            except OSError as exc:
                self.registry.active.discard(workspace)
                job.update(state="failed", finished=time.time(), detail=f"Worker could not start: {exc}")
                atomic_json(self.path(key), job)
            return job

    def _monitor(self, key: str, process: subprocess.Popen, plan: dict) -> None:
        code = process.wait()
        with self.lock, self.registry.lock:
            job = read_json(self.path(key))
            try:
                if job["state"] == "cancelling":
                    job.update(
                        state="cancelled",
                        detail="Cancelled by researcher. Partial outputs retained; no successful result manifest.",
                    )
                elif code != 0:
                    job.update(
                        state="failed",
                        detail=f"Worker exited with code {code}. See the run log; partial outputs retained.",
                    )
                else:
                    job.update(
                        state="succeeded",
                        detail="Processing completed. Review the outputs before scientific interpretation.",
                    )
                    root = self.registry.root(job["workspace"])
                    # Do not automatically record unrelated external edits into a run revision.
                    history.require_version(self.registry, job["workspace"], plan["version"])
                    write_manifest(
                        Path(job["output"]),
                        pipeline=job["pipeline"],
                        revision=job["pre_revision"],
                        manifest_dir=confined(root, f"results/{key}"),
                    )
                    job["post_revision"] = self.registry.evc(job["workspace"]).record(
                        f"Complete {job['pipeline']} run {key[:8]}", author=self.registry.author
                    )
            except Exception as exc:
                job.update(
                    state="failed",
                    detail=f"Run outcome/provenance could not be finalized: {exc}. Outputs are retained; not reported as successful.",
                )
            finally:
                job["finished"] = time.time()
                atomic_json(self.path(key), job)
                atomic_json(Path(plan["output"]) / "outcome.json", job)
                self.registry.active.discard(job["workspace"])
                self.current, self.process = None, None

    def cancel(self, key: str) -> dict:
        with self.lock:
            job = read_json(self.path(key))
            if job["state"] in TERMINAL:
                return job
            if key != self.current or self.process is None:
                raise documents.ConflictError("No worker owned by this session is running this job.")
            job.update(state="cancelling", detail="Stopping the worker; partial outputs will be retained.")
            atomic_json(self.path(key), job)
            process = self.process
            if process.poll() is None:
                if os.name == "nt":
                    process.terminate()
                else:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                threading.Thread(target=self._kill_after_timeout, args=(process,), daemon=True).start()
            return job

    @staticmethod
    def _kill_after_timeout(process: subprocess.Popen) -> None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def shutdown(self) -> None:
        with self.lock:
            self.closed = True
            if self.current:
                self.cancel(self.current)
        if self.monitor:
            self.monitor.join(timeout=8)
        self.lease.close()
