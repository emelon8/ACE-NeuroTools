import pytest
from fastapi.testclient import TestClient

from ace_workbench.app import create_app
from ace_workbench.demo import create_demo
from ace_workbench.workspaces import WorkspaceRegistry


@pytest.fixture
def service(tmp_path):
    roots = create_demo(tmp_path / "demo")
    registry = WorkspaceRegistry(roots, author="Test researcher <test@localhost>")
    with TestClient(create_app(registry, "test-token"), base_url="http://127.0.0.1:8765", headers={"x-ace-token": "test-token"}) as client:
        workspace = registry.list()[0]["id"]
        yield client, f"/api/workspaces/{workspace}", registry, workspace
