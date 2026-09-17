"""Thin local HTTP transport over the workflow application services."""

from fastapi import APIRouter, Query, Request

from .jobs import JobManager
from .models import BeginImport, Launch, Preflight, Selection, Setup
from .service import WorkflowService
from .storage import CHUNK_SIZE


def router(service: WorkflowService, jobs: JobManager) -> APIRouter:
    routes = APIRouter(prefix="/api/workflow")

    @routes.post("/imports")
    def begin(body: BeginImport):
        return service.imports.begin(body.files)

    @routes.get("/imports/{key}")
    def get_import(key: str):
        return service.describe(service.imports.read(key))

    @routes.put("/imports/{key}/files/{index}")
    async def upload(key: str, index: int, request: Request, offset: int = Query(ge=0)):
        data = await request.body()
        if len(data) > CHUNK_SIZE:
            raise ValueError("Upload chunks are limited to 1 MiB.")
        # File write is bounded to one chunk; do not hold a lock across awaits.
        return service.imports.append(key, index, offset, data)

    @routes.post("/imports/{key}/inspect")
    def inspect(key: str):
        return service.inspect(key)

    @routes.delete("/imports/{key}")
    def discard(key: str):
        service.imports.discard(key)
        return {"discarded": True}

    @routes.post("/imports/{key}/questions")
    def questions(key: str, body: Selection):
        return service.questionnaire(key, body)

    @routes.post("/imports/{key}/setup")
    def setup(key: str, body: Setup):
        return service.setup(key, body)

    @routes.get("/configurations")
    def configurations(workspace: str):
        return service.configurations(workspace)

    @routes.get("/configuration")
    def configuration(workspace: str, path: str):
        return service.configuration(workspace, path)

    @routes.put("/configuration")
    def reconfigure(workspace: str, path: str, body: Selection):
        return service.reconfigure(workspace, path, body)

    @routes.post("/preflight")
    def preflight(body: Preflight):
        return jobs.preflight(body.workspace, body.configuration)

    @routes.post("/runs")
    def launch(body: Launch):
        return jobs.launch(body.plan)

    @routes.get("/runs")
    def list_runs(workspace: str | None = None):
        return jobs.list(workspace)

    @routes.get("/runs/{key}")
    def run(key: str):
        return jobs.read(key)

    @routes.post("/runs/{key}/cancel")
    def cancel(key: str):
        return jobs.cancel(key)

    return routes
