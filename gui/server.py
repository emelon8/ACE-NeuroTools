"""Local HTTP wrapper for existing projects, Box setup, cropping, and analysis runs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from gui.box_setup import BoxSetup, BoxSetupError
from gui.cropping import Cropping
from gui.csv_projects import Project, ProjectChangedError, ProjectError
from gui.job_scripts import generate as generate_job_scripts
from gui.native_dialogs import NativeDialogs
from gui.neurons import Neurons
from gui.recordings import Recordings
from gui.run_specs import PIPELINES, effective_parameters, settings_keys, specification, validate_settings
from gui.runs import Runs

ASSETS = Path(__file__).parent


class ProjectServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, initial: str | None = None, *, box_setup=None):
        self.box = box_setup if box_setup is not None else BoxSetup()
        self.runs = Runs()
        self.cropping = Cropping()
        self.recordings = Recordings(self.box)
        self.neurons = Neurons()
        self.native = NativeDialogs()
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
            if route.path == "/api/health":
                self._json({"application": "ACE Experiments"})
            elif route.path == "/api/box/status":
                self._json(self.server.box.status())
            elif route.path in {"/api/recording", "/api/neuron/export"}:
                with self.server.lock:
                    project = self.server.projects.get(args.get("project", [""])[0])
                if project is None:
                    raise ProjectError("Open this project first.")
                service = (
                    self.server.neurons.export_status
                    if route.path == "/api/neuron/export"
                    else self.server.recordings.status
                )
                self._json(service(project, args.get("job", [""])[0]))
            elif route.path == "/api/projects":
                with self.server.lock:
                    projects = [project.summary() for project in self.server.projects.values()]
                self._json({"projects": projects, "startup_error": self.server.startup_error})
            elif route.path in {
                "/api/experiment",
                "/api/runs",
                "/api/run",
                "/api/run/file",
                "/api/run/settings",
                "/api/neuron/sources",
            }:
                project_id = args.get("project", [""])[0]
                with self.server.lock:
                    project = self.server.projects.get(project_id)
                if project is None:
                    raise ProjectError("Open this project first.")
                number = args.get("number", [""])[0]
                if route.path == "/api/neuron/sources":
                    self._json(
                        self.server.neurons.sources(
                            project, number, args.get("data_path", [None])[0], self.server.runs.listing(project, number)
                        )
                    )
                elif route.path == "/api/runs":
                    self._json(self.server.runs.listing(project, number))
                elif route.path == "/api/run":
                    self._json(self.server.runs.inspect(project, args.get("run", [""])[0]))
                elif route.path == "/api/run/settings":
                    kind = args.get("kind", ["compute"])[0]
                    detail = project.inspect(number)
                    params, sources = effective_parameters(kind, detail["parameters"])
                    self._json({"parameters": params, "sources": sources, "label": PIPELINES[kind]})
                elif route.path == "/api/run/file":
                    directory = self.server.runs.directory(project, args.get("run", [""])[0])
                    name = args.get("name", [""])[0]
                    detail = self.server.runs.inspect(project, directory.name)
                    if name not in {item["name"] for item in detail["files"]}:
                        raise ProjectError("Choose an output file from this run.")
                    path = (directory / name).resolve()
                    if not path.is_relative_to(directory.resolve()):
                        raise ProjectError("Output file is outside this run folder.")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(path.stat().st_size))
                    self.send_header("Content-Disposition", "attachment")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    with path.open("rb") as handle:
                        import shutil

                        shutil.copyfileobj(handle, self.wfile)
                else:
                    self._json(project.inspect(number))
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
                            if item.is_file()
                            and (
                                args.get("files") == ["all"]
                                or item.suffix.lower()
                                in ({".hdf5", ".h5"} if args.get("files") == ["estimates"] else {".csv"})
                            )
                        ],
                    }
                )
            elif route.path in {
                "/",
                "/index.html",
                "/style.css",
                "/app.js",
                "/box.js",
                "/analysis.js",
                "/neurons.js",
                "/job_scripts.js",
            }:
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
                    "default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'",
                )
                self.end_headers()
                self.wfile.write(body)
            else:
                self._json({"error": "Page not found."}, 404)
        except ProjectChangedError as exc:
            self._json({"error": str(exc), "reload": True}, 409)
        except (ProjectError, BoxSetupError, OSError, ValueError) as exc:
            self._json({"error": str(exc)}, 400)

    def do_POST(self) -> None:
        if not self._same_origin() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self._json({"error": "Open the application at its local address to work with projects."}, 403)
            return
        route = urlsplit(self.path).path
        box_routes = {
            "/api/box/check": self.server.box.check,
            "/api/box/connect": self.server.box.connect,
            "/api/box/location": self.server.box.location,
            "/api/box/folders": self.server.box.folders,
            "/api/box/finish": self.server.box.finish,
            "/api/box/disconnect": self.server.box.disconnect,
        }
        experiment_routes = {
            "/api/experiment/save",
            "/api/run/review",
            "/api/run/start",
            "/api/run/stop",
            "/api/run/settings/save",
            "/api/job/scripts",
            "/api/crop/preview",
            "/api/crop/save",
            "/api/recording/prepare",
            "/api/recording/plan",
            "/api/recording/start",
            "/api/recording/cancel",
            "/api/neuron/open",
            "/api/neuron/component",
            "/api/neuron/decide",
            "/api/neuron/export",
        }
        if route not in {
            "/api/projects/open",
            "/api/projects/default",
            "/api/experiment/create",
            "/api/system/pick",
            "/api/system/open-folder",
            *experiment_routes,
            *box_routes,
        }:
            self._json({"error": "Operation not found."}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 262144:
                raise ProjectError("Project request is empty or too large.")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ProjectError("Send a valid application request.")
            if route == "/api/system/pick":
                self._json(self.server.native.pick(body))
                return
            if route == "/api/system/open-folder":
                if not isinstance(body.get("path"), str) or not body["path"].strip():
                    raise ProjectError("Choose an output folder.")
                self._json(self.server.native.open_folder(body["path"]))
                return
            if route in box_routes:
                self._json(box_routes[route](body))
                return
            if route in {"/api/projects/default", "/api/experiment/create"}:
                with self.server.lock:
                    project = self.server.projects.get(body.get("project"))
                    if project is None:
                        raise ProjectError("Open this project first.")
                    if route == "/api/projects/default":
                        saved = project.set_default_experiment(body.get("number"), body.get("versions"))
                        self.server.projects[saved.id] = saved
                        self._json({"project": saved.summary()})
                    else:
                        saved, backup = project.create_experiment(
                            body.get("number"), body.get("metadata"), body.get("parameters"), body.get("versions")
                        )
                        self.server.projects[saved.id] = saved
                        self._json(
                            {"project": saved.summary(), "experiment": saved.inspect(body["number"]), "backup": backup}
                        )
                return
            if route in experiment_routes:
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
                if route.startswith("/api/neuron/"):
                    self._json(getattr(self.server.neurons, route.rsplit("/", 1)[1])(project, body))
                    return
                # Preview reads and run launches never hold the CSV lock during long work.
                if route in {
                    "/api/recording/prepare",
                    "/api/recording/plan",
                    "/api/recording/start",
                    "/api/recording/cancel",
                    "/api/neuron/open",
                    "/api/neuron/component",
                    "/api/neuron/decide",
                    "/api/neuron/export",
                }:
                    action = getattr(self.server.recordings, route.rsplit("/", 1)[1])
                    self._json(action(project, body))
                    return
                if route == "/api/crop/preview":
                    self._json(self.server.cropping.preview(project, body))
                    return
                if route == "/api/run/review":
                    self._json(self.server.runs.review(project, body))
                    return
                if route == "/api/job/scripts":
                    with self.server.lock:
                        self._json(generate_job_scripts(project, body))
                    return
                if route == "/api/run/start":
                    with self.server.lock:
                        self._json(self.server.runs.start(project, body))
                    return
                if route == "/api/run/stop":
                    self._json(self.server.runs.stop(project, body.get("run")))
                    return
                with self.server.lock:
                    # Re-fetch after releasing the lock for dispatch.
                    project = self.server.projects[body["project"]]
                    if route == "/api/crop/save":
                        saved, backup = self.server.cropping.save(project, body)
                    else:
                        new_columns = ()
                        if route == "/api/run/settings/save":
                            kind = body.get("kind", "compute")
                            keys = specification(kind)[1] | {"crop_coords"}
                            if not isinstance(body.get("changes"), dict) or any(
                                key not in keys for key in body["changes"]
                            ):
                                raise ProjectError("Choose valid settings for this analysis.")
                            validate_settings(kind, body["changes"])
                            body["section"] = "parameters"
                            new_columns = tuple(settings_keys())
                        saved, backup = project.save(
                            body["number"],
                            body.get("section"),
                            body.get("changes"),
                            body.get("versions"),
                            body.get("create", False),
                            new_columns=new_columns,
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
        except (ProjectError, BoxSetupError, OSError, ValueError) as exc:
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
    print(f"Experiment application: {url}", flush=True)
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
