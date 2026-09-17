"""Isolated synthetic workspaces for browser tests; never uses research data."""
import tempfile
from pathlib import Path

import uvicorn
from ace_workbench.app import create_app
from ace_workbench.demo import create_demo
from ace_workbench.workspaces import WorkspaceRegistry
from fastapi.staticfiles import StaticFiles

with tempfile.TemporaryDirectory(prefix="ace-browser-test-") as temp:
    directory = Path(temp)
    registry = WorkspaceRegistry(create_demo(directory / "initial"), author="Browser test <test@localhost>")
    app = create_app(registry, "browser-test-session", 8766)

    @app.post("/api/test/reset")
    def reset():
        # Test-only route, behind the same capability header; absent in production.
        with registry.lock:
            root = Path(tempfile.mkdtemp(dir=directory)) / "demo"
            fresh = WorkspaceRegistry(create_demo(root))
            registry.roots = fresh.roots
        return {"ready": True}

    app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "dist", html=True))
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
