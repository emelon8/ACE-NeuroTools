"""Route registry for GUI features.

Each GUI feature lives in its own module and declares a ``FEATURE`` object. The
server collects the features listed in :mod:`aceneurotools.gui.features`, so a new
feature adds one module (plus its browser files) and one line to that list
instead of another branch in ``server.py``.

A feature module looks like this::

    from aceneurotools.gui.routes import Feature, Route

    def _status(context):
        return {"ready": True, "project": context.project.id}

    FEATURE = Feature(
        name="example",
        routes=(Route("GET", "/api/example/status", _status, scope="project"),),
        scripts=("example.js",),
    )

The server keeps its existing protections for every feature route: requests
must come from the local address, carry the launch token, and POST bodies must
be JSON. Handlers receive a :class:`Context` and return a JSON-compatible dict
or a :class:`FileResponse`. ``ProjectError``/``ValueError``/``OSError`` become
400 responses and ``ProjectChangedError`` becomes a 409 with ``reload``, exactly
as for the built-in routes.

Scopes resolve and validate the project before the handler runs:

``none``
    No project is required.
``project``
    ``project`` (query for GET, body for POST) must name an open project.
``experiment``
    As ``project``, and ``number`` must name an experiment in it.

Set ``locked=True`` for handlers that read and then write project CSVs or JSON
files; they run while holding the server lock, so they must not do slow work.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCOPES = {"none", "project", "experiment"}
METHODS = {"GET", "POST"}
_STATIC_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*\.(js|css|html)")


@dataclass(frozen=True)
class FileResponse:
    """A file or bytes response for a feature route (images, downloads, fragments)."""

    content_type: str
    body: bytes | None = None
    path: Path | None = None
    download_name: str | None = None
    cache: str = "no-store"

    def __post_init__(self) -> None:
        if (self.body is None) == (self.path is None):
            raise ValueError("A file response needs exactly one of body or path.")


@dataclass
class Context:
    """What a feature handler receives for one request."""

    server: Any
    method: str
    path: str
    query: dict[str, str]
    body: dict[str, Any]
    project: Any = None
    number: str | None = None

    def value(self, name: str, default: Any = None) -> Any:
        """Read a request value from the JSON body (POST) or query string (GET)."""
        source = self.body if self.method == "POST" else self.query
        return source.get(name, default)

    def replace_project(self, project: Any) -> None:
        """Publish a re-read project after a save. Call while holding the server lock."""
        self.server.projects[project.id] = project
        self.project = project


Handler = Callable[[Context], "dict[str, Any] | FileResponse"]


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    handler: Handler
    scope: str = "project"
    locked: bool = False

    def __post_init__(self) -> None:
        if self.method not in METHODS:
            raise ValueError(f"Unsupported method for {self.path}: {self.method}")
        if self.scope not in SCOPES:
            raise ValueError(f"Unsupported scope for {self.path}: {self.scope}")
        if not self.path.startswith("/api/"):
            raise ValueError(f"Feature routes must live under /api/: {self.path}")


@dataclass(frozen=True)
class Feature:
    """A GUI feature: its API routes and the browser files it needs.

    ``scripts`` and ``styles`` are file names in the gui/ folder. They are served
    at ``/<name>`` and loaded by features.js after the core scripts, in order.
    ``fragments`` are HTML files a script can load with ``aceFeatures.fragment``.
    ``service`` builds per-server state (for example a job queue); it is stored
    as ``server.services[name]``.
    """

    name: str
    routes: tuple[Route, ...] = ()
    scripts: tuple[str, ...] = ()
    styles: tuple[str, ...] = ()
    fragments: tuple[str, ...] = ()
    service: Callable[[Any], Any] | None = None
    files: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        names = (*self.scripts, *self.styles, *self.fragments)
        for name in names:
            if not _STATIC_NAME.fullmatch(name):
                raise ValueError(f"Feature file names must be simple lower-case names: {name}")
        object.__setattr__(self, "files", names)


class Registry:
    """Feature routes and browser files collected for one server."""

    def __init__(self, features: Iterable[Feature] = ()) -> None:
        self.features: list[Feature] = []
        self._routes: dict[tuple[str, str], Route] = {}
        self._files: dict[str, str] = {}
        for feature in features:
            self.add(feature)

    def add(self, feature: Feature) -> None:
        if any(existing.name == feature.name for existing in self.features):
            raise ValueError(f"Feature registered twice: {feature.name}")
        for route in feature.routes:
            key = (route.method, route.path)
            if key in self._routes:
                raise ValueError(f"Route registered twice: {route.method} {route.path}")
            self._routes[key] = route
        for name in feature.files:
            if f"/{name}" in self._files:
                raise ValueError(f"Browser file registered twice: {name}")
            self._files[f"/{name}"] = name
        self.features.append(feature)

    def match(self, method: str, path: str) -> Route | None:
        return self._routes.get((method, path))

    def paths(self, method: str) -> set[str]:
        return {path for (verb, path) in self._routes if verb == method}

    @property
    def static(self) -> dict[str, str]:
        return dict(self._files)

    def manifest(self) -> list[dict[str, Any]]:
        """What the browser loader needs: each feature's scripts and styles, in order."""
        return [
            {"name": feature.name, "scripts": list(feature.scripts), "styles": list(feature.styles)}
            for feature in self.features
        ]


def load_features(modules: Iterable[str]) -> list[Feature]:
    """Import each feature module and return its ``FEATURE``."""
    features = []
    for module_name in modules:
        module = importlib.import_module(module_name)
        feature = getattr(module, "FEATURE", None)
        if not isinstance(feature, Feature):
            raise TypeError(f"{module_name} does not define FEATURE = Feature(...)")
        features.append(feature)
    return features
