"""Isolated synthetic workspaces for browser tests; never uses research data."""
import tempfile
from pathlib import Path

import uvicorn
from ace_workbench.app import create_app
from ace_workbench.demo import create_demo
from ace_workbench.workspaces import WorkspaceRegistry

with tempfile.TemporaryDirectory(prefix="ace-browser-test-") as temp:
    roots = create_demo(Path(temp) / "demo")
    app = create_app(
        WorkspaceRegistry(roots, author="Browser test <test@localhost>"),
        "browser-test-session", 8766, Path(__file__).resolve().parents[1] / "dist",
    )
    uvicorn.run(app, host="127.0.0.1", port=8766, access_log=False)
