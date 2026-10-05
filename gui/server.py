"""Local HTTP interface for existing projects and explicit CSV edits."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from gui.csv_projects import Project, ProjectChangedError, ProjectError

ASSETS = Path(__file__).parent


class ProjectServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, initial: str | None = None):
        self.projects: dict[str, Project] = {}
        self.lock = threading.Lock()
        self.startup_error: str | None = None
        if initial:
            try:
                project = Project.open(initial)
                self.projects[project.id] = project
            except ProjectError as exc:
                self.startup_error = str(exc)
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server: ProjectServer

    def _same_origin(self) -> bool:
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host in allowed and (not origin or origin in {f"http://{value}" for value in allowed})

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._same_origin():
            self._json({"error": "This viewer accepts requests from its local address only."}, 403)
            return
        route = urlsplit(self.path)
        args = parse_qs(route.query)
        try:
            if route.path == "/api/projects":
                with self.server.lock:
                    projects = [project.summary() for project in self.server.projects.values()]
                self._json({"projects": projects, "startup_error": self.server.startup_error})
            elif route.path == "/api/experiment":
                project_id = args.get("project", [""])[0]
                with self.server.lock:
                    project = self.server.projects.get(project_id)
                if project is None:
                    raise ProjectError("Open this project first.")
                self._json(project.inspect(args.get("number", [""])[0]))
            elif route.path == "/api/folders":
                path = Path(args.get("path", [str(Path.home())])[0]).expanduser().resolve()
                if not path.is_dir():
                    raise ProjectError(f"Folder does not exist: {path}")
                folders = sorted(
                    (item for item in path.iterdir() if item.is_dir() and not item.name.startswith(".")),
                    key=lambda item: item.name.casefold(),
                )
                self._json(
                    {
                        "path": str(path),
                        "parent": str(path.parent),
                        "breadcrumbs": [
                            {"name": part.name or "Computer", "path": str(part)}
                            for part in [*reversed(path.parents), path]
                        ],
                        "has_experiments": (path / "experiments.csv").is_file(),
                        "has_parameters": (path / "analysis_parameters.csv").is_file(),
                        "folders": [
                            {"name": item.name, "path": str(item), "project": (item / "experiments.csv").is_file()}
                            for item in folders
                        ],
                        "files": [
                            {"name": item.name, "path": str(item)}
                            for item in sorted(path.iterdir(), key=lambda item: item.name.casefold())
                            if item.is_file() and item.suffix.lower() == ".csv"
                        ],
                    }
                )
            elif route.path in {"/", "/index.html", "/style.css", "/app.js"}:
                name = "index.html" if route.path == "/" else route.path[1:]
                body = (ASSETS / name).read_bytes()
                self.send_response(200)
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                self.send_header("Content-Type", f"{mime}; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'",
                )
                self.end_headers()
                self.wfile.write(body)
            else:
                self._json({"error": "Page not found."}, 404)
        except ProjectChangedError as exc:
            self._json({"error": str(exc), "reload": True}, 409)
        except (ProjectError, OSError) as exc:
            self._json({"error": str(exc)}, 400)

    def do_POST(self) -> None:
        if not self._same_origin() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self._json({"error": "Open the application at its local address to work with projects."}, 403)
            return
        route = urlsplit(self.path).path
        if route not in {"/api/projects/open", "/api/experiment/save"}:
            self._json({"error": "Operation not found."}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 262144:
                raise ProjectError("Project request is empty or too large.")
            body = json.loads(self.rfile.read(length))
            if route == "/api/experiment/save":
                if (
                    not isinstance(body, dict)
                    or not isinstance(body.get("project"), str)
                    or not isinstance(body.get("number"), str)
                ):
                    raise ProjectError("Choose an experiment before saving.")
                with self.server.lock:
                    project = self.server.projects.get(body["project"])
                    if project is None:
                        raise ProjectError("Open this project first.")
                    if not isinstance(body.get("create", False), bool):
                        raise ProjectError("Invalid settings creation request.")
                    saved, backup = project.save(
                        body["number"],
                        body.get("section"),
                        body.get("changes"),
                        body.get("versions"),
                        body.get("create", False),
                    )
                    self.server.projects[saved.id] = saved
                    detail = saved.inspect(body["number"])
                self._json({"project": saved.summary(), "experiment": detail, "backup": backup})
                return
            if not isinstance(body, dict) or not isinstance(body.get("path"), str) or not body["path"].strip():
                raise ProjectError("Enter a project folder or an experiments.csv path.")
            project = Project.open(body["path"].strip())
            with self.server.lock:
                self.server.projects[project.id] = project
                self.server.startup_error = None
            self._json(project.summary())
        except ProjectChangedError as exc:
            self._json({"error": str(exc), "reload": True}, 409)
        except (ProjectError, OSError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)

    def log_message(self, format, *args) -> None:
        # Log the method/status, not local path query strings or CSV contents.
        if len(args) >= 2:
            print(f"{self.command} {args[1]}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Browse and edit existing ACE-NeuroTools experiments locally.")
    parser.add_argument("--project", help="Folder containing experiments.csv, or its full path")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = ProjectServer(("127.0.0.1", args.port), args.project)
    except OSError as exc:
        parser.exit(1, f"Cannot start CSV viewer: {exc}. Choose another port with --port.\n")
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"CSV project viewer: {url}", flush=True)
    if server.startup_error:
        print(server.startup_error, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
