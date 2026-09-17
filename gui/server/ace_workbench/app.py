"""Same-origin HTTP boundary for the local workbench."""

from __future__ import annotations

import hmac
from dataclasses import asdict
from pathlib import Path

from aceneurotools.evc.api import EVCError, load_schema
from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import documents, history, results
from .workspaces import WorkspaceRegistry


class Save(BaseModel):
    path: str
    text: str = Field(max_length=2 * 1024 * 1024)
    etag: str


class Record(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    version: str


class Restore(BaseModel):
    revision: str
    version: str


class Comment(BaseModel):
    text: str = Field(min_length=1, max_length=16000)


def create_app(registry: WorkspaceRegistry, token: str, port: int = 8765, dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="ACENeuroTools local workbench", docs_url=None, redoc_url=None, openapi_url=None)
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{host}" for host in hosts}

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.headers.get("host") not in hosts:
            return JSONResponse({"detail": "Unrecognized local host."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"detail": "Foreign origins are not allowed."}, status_code=403)
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("x-ace-token", "")
            if not hmac.compare_digest(supplied, token):
                return JSONResponse({"detail": "Session expired. Reopen the URL printed by ace-workbench."}, status_code=401)
            size = request.headers.get("content-length")
            if size and int(size) > 3 * 1024 * 1024:
                return JSONResponse({"detail": "Request too large."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; img-src 'self' data:; worker-src 'self' blob:; "
            "connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'"
        )
        return response

    @app.exception_handler(Exception)
    async def unexpected(_request, exc):
        import logging
        logging.getLogger(__name__).exception("Workbench request failed", exc_info=exc)
        return JSONResponse({"detail": "Operation failed. See the local server log; refresh before retrying."}, status_code=500)

    async def expected(_request, exc):
        code = 409 if isinstance(exc, documents.ConflictError) else 404 if isinstance(exc, (KeyError, FileNotFoundError)) else 400
        return JSONResponse({"detail": str(exc)}, status_code=code)

    for error in (ValueError, EVCError, KeyError, OSError):
        app.add_exception_handler(error, expected)

    @app.get("/api/session")
    def session():
        return {"version": "0.1.0", "workspaces": registry.list(), "mode": "local", "author": registry.author}

    @app.get("/api/schemas")
    def schemas():
        return {name: load_schema(schema) for name, schema in documents.SCHEMAS.items()}

    @app.get("/api/workspaces/{workspace}/state")
    def state(workspace: str):
        with registry.lock:
            return {"status": history.state(registry, workspace), "documents": documents.list_documents(registry, workspace)}

    @app.get("/api/workspaces/{workspace}/document")
    def document(workspace: str, path: str, revision: str | None = None):
        with registry.lock:
            return documents.read_document(registry, workspace, path, revision)

    @app.put("/api/workspaces/{workspace}/document")
    def save(workspace: str, body: Save):
        return documents.save_document(registry, workspace, body.path, body.text, body.etag)

    @app.get("/api/workspaces/{workspace}/history")
    def revisions(workspace: str, limit: int = Query(200, ge=1, le=1000)):
        with registry.lock:
            return [asdict(rev) for rev in registry.evc(workspace).history(limit)]

    @app.post("/api/workspaces/{workspace}/record")
    def record(workspace: str, body: Record):
        return history.record(registry, workspace, body.message, body.version)

    @app.post("/api/workspaces/{workspace}/restore")
    def restore(workspace: str, body: Restore):
        return history.restore(registry, workspace, body.revision, body.version)

    @app.get("/api/workspaces/{workspace}/diff")
    def diff(workspace: str, a: str, b: str = "HEAD"):
        with registry.lock:
            return [asdict(d) for d in registry.evc(workspace).diff(a, b)]

    @app.get("/api/workspaces/{workspace}/revision/{revision}")
    def show(workspace: str, revision: str):
        return asdict(registry.evc(workspace).show(revision))

    @app.get("/api/workspaces/{workspace}/revision/{revision}/comments")
    def comments(workspace: str, revision: str):
        return {"text": registry.evc(workspace).comments(revision) or ""}

    @app.post("/api/workspaces/{workspace}/revision/{revision}/comments")
    def comment(workspace: str, revision: str, body: Comment):
        if not body.text.strip():
            raise ValueError("A comment cannot be blank.")
        with registry.lock:
            return {"revision": registry.evc(workspace).comment(revision, body.text, author=registry.author)}

    @app.get("/api/workspaces/{workspace}/recovery")
    def recovery(workspace: str):
        return [asdict(entry) for entry in registry.evc(workspace).recover()]

    @app.get("/api/workspaces/{workspace}/results")
    def runs(workspace: str):
        return results.list_results(registry, workspace)

    @app.post("/api/workspaces/{workspace}/results/{run}/verify")
    def verify(workspace: str, run: str):
        return results.verify(registry, workspace, run)

    @app.get("/api/workspaces/{workspace}/results/{run}/preview")
    def preview(workspace: str, run: str, path: str):
        return results.preview(registry, workspace, run, path)

    if dist and dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="workbench")
    return app
