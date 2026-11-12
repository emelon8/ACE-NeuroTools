"""Loaders page: list, edit, check and save ephys loader definitions.

Definitions live in ``<project>/loaders/<name>.json`` (schema ``ace-loader/1``).
Parsing, validation and folder matching all come from
:mod:`aceneurotools.shared.loader_definitions`; this module only adds what the
workbench needs around them:

- per-file digests, so a save made from a stale copy is refused (409), as in the
  CSV editor
- a backup of the previous version in ``.ace-gui-backups`` before any overwrite
  or delete
- the built-in ephys loaders, listed exactly as ``ace-neuro loaders list`` does
- detection against an experiment's ephys folder, resolved on this computer

The browser never sends a filesystem path. Definitions are addressed by name,
and the experiment's folder comes from ``experiments.csv``.

Loading signal data from a definition (preview, and use in analyses) needs a
change to the core ephys loaders proposed in ADR 0008, so it is not offered here.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any

from aceneurotools.gui.csv_projects import ProjectChangedError, ProjectError
from aceneurotools.gui.routes import Feature, Route
from aceneurotools.shared import loader_definitions as ld

TEMPLATES_DIR = Path(ld.__file__).parent / "loader_templates"
TEMPLATES = (
    ("neo-reader", "Neo reader", "A system that a neo reader opens, such as Intan, Open Ephys or Neuralynx files."),
    ("raw-binary", "Raw binary file", "One interleaved binary file with a fixed sample type and channel count."),
)
BACKUPS_DIRNAME = ".ace-gui-backups"
MAX_SHOWN_MATCHES = 5
PREVIEW_NOTE = (
    "Preview is not available yet. Loading signals from a definition needs a change to the core ephys "
    "loaders that is under review (ADR 0008). Until then, definitions are not used by analyses."
)

_builtins_lock = threading.Lock()
_builtins_cache: list[dict[str, Any]] | None = None


# ── Built-in loaders ─────────────────────────────────────────────────────────


def _first_line(text: str | None) -> str:
    return next((line.strip() for line in (text or "").splitlines() if line.strip()), "")


def _builtin_classes() -> list[tuple[str, type]]:
    # Same list as `ace-neuro loaders list`; importing the ephys package is slow,
    # so it happens on first use, not at server start.
    from aceneurotools.cli import _builtin_ephys_loaders

    return _builtin_ephys_loaders()


def _reserved(name: str, cls: type) -> list[str]:
    """Names a project definition may not use because they refer to this built-in.

    The same rule as ``ace-neuro loaders``: the registered name and its short
    form (``neuralynx`` for ``NeuralynxDataManager``), case-insensitively.
    """
    from aceneurotools.cli import _reserved_names_for

    return _reserved_names_for(name, cls)


def builtin_loaders() -> list[dict[str, Any]]:
    global _builtins_cache
    with _builtins_lock:
        if _builtins_cache is None:
            _builtins_cache = [
                {
                    "name": name,
                    "class": f"{cls.__module__}.{cls.__qualname__}",
                    "description": _first_line(cls.__doc__),
                    "recognises": _first_line(getattr(cls.can_handle, "__doc__", None)),
                    "reserved": _reserved(name, cls),
                }
                for name, cls in _builtin_classes()
            ]
        return [dict(item) for item in _builtins_cache]


def reserved_names() -> set[str]:
    return {value for item in builtin_loaders() for value in item["reserved"]}


# ── Files ────────────────────────────────────────────────────────────────────


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _folder(project) -> Path:
    return Path(project.path) / ld.LOADERS_DIRNAME


def check_name(value: Any) -> str:
    """A definition name from the browser; checked before it is joined to any path."""
    if (
        not isinstance(value, str)
        or len(value) > ld.NAME_MAX_LENGTH
        or not re.fullmatch(ld.NAME_PATTERN, value)
    ):
        raise ProjectError(
            "Loader names use lowercase letters and digits separated by hyphens, for example my-rig "
            f"(at most {ld.NAME_MAX_LENGTH} characters)."
        )
    if re.fullmatch(ld.WINDOWS_DEVICE_NAME_PATTERN, value):
        raise ProjectError(f"'{value}' is a reserved device name on Windows. Choose another loader name.")
    return value


def _file(project, name: str) -> Path:
    return _folder(project) / f"{check_name(name)}.json"


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ProjectError(f"Cannot read {path.name}: {exc.strerror or exc}") from exc


def _decode(content: bytes, path: Path) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        raise ProjectError(f"{path.name} is not UTF-8 text. Fix or remove it outside ACE.") from None


def _project_definitions(project):
    try:
        return ld.load_project_definitions(project.path, reserved_names=reserved_names())
    except RecursionError:
        # load_project_definitions does not catch this for very deeply nested JSON.
        raise ProjectError(
            "A file in the loaders folder is nested too deeply to read. Remove or fix it outside ACE."
        ) from None


def _problems(items) -> list[dict[str, str]]:
    return [{"path": item.path, "message": item.message} for item in items]


def draft_problems(project, text: Any, name: str | None, *, creating: bool) -> tuple[Any, list[dict[str, str]]]:
    """Problems with a definition as it would be saved to ``loaders/<name>.json``."""
    if not isinstance(text, str):
        raise ProjectError("Send the loader definition as JSON text.")
    data, problems = ld.check_definition_text(text, file_stem=name)
    found = _problems(problems)
    target = data.get("name") if isinstance(data, dict) else None
    if isinstance(target, str):
        if target.lower() in reserved_names():
            found.append({"path": "name", "message": f"'{target}' is the name of a built-in loader. Choose another name."})
        elif creating and re.fullmatch(ld.NAME_PATTERN, target) and len(target) <= ld.NAME_MAX_LENGTH:
            if (_folder(project) / f"{target}.json").exists():
                found.append({"path": "name", "message": f"This project already has a loader named '{target}'."})
    return data, found


# ── Routes ───────────────────────────────────────────────────────────────────


def listing(context):
    """Built-in loaders and this project's definitions, with problems and digests."""
    project = context.project
    builtins = builtin_loaders()
    folder = _folder(project)
    definitions, problems = _project_definitions(project)
    valid = {Path(item.source).name: item for item in definitions}
    issues = {Path(key).name: value for key, value in problems.items()}
    entries = []
    if folder.is_dir():
        for path in sorted(folder.glob("*.json")):
            if not path.is_file():
                continue
            content = _read(path)
            definition = valid.get(path.name)
            label = definition.label if definition else None
            if definition is None and content is not None:
                try:
                    raw = json.loads(content.decode("utf-8-sig"))
                    label = raw.get("label") if isinstance(raw, dict) and isinstance(raw.get("label"), str) else None
                except (UnicodeDecodeError, ValueError, RecursionError):
                    label = None
            try:
                editable = check_name(path.stem) == path.stem  # the rule the open and delete routes apply
            except ProjectError:
                editable = False
            entries.append(
                {
                    "name": path.stem,
                    "file": f"{ld.LOADERS_DIRNAME}/{path.name}",
                    "label": label,
                    "backend": definition.backend if definition else None,
                    "valid": definition is not None and path.name not in issues,
                    "problems": _problems(issues.get(path.name, [])),
                    "digest": _digest(content) if content is not None else None,
                    "editable": editable,
                }
            )
    return {
        "builtins": builtins,
        "definitions": entries,
        "folder": f"{ld.LOADERS_DIRNAME}/",
        "folder_exists": folder.is_dir(),
        "preview": {"available": False, "note": PREVIEW_NOTE},
    }


def definition(context):
    """One definition's text and digest. Query: ``name``."""
    path = _file(context.project, context.value("name"))
    content = _read(path)
    if content is None:
        raise ProjectError(f"{path.name} is no longer in this project's loaders folder. Refresh the list.")
    text = _decode(content, path)
    _, problems = draft_problems(context.project, text, path.stem, creating=False)
    editor_text = text.removeprefix("\ufeff") if not problems else text
    return {"name": path.stem, "text": editor_text, "digest": _digest(content), "problems": problems}


def schema(context):
    """JSON Schema, the choices the form offers, and the starting templates."""
    templates = []
    for template_id, label, description in TEMPLATES:
        templates.append(
            {
                "id": template_id,
                "label": label,
                "description": description,
                "text": (TEMPLATES_DIR / f"{template_id}.json").read_text(encoding="utf-8"),
            }
        )
    return {
        "schema": ld.definition_json_schema(),
        "choices": {
            "backends": list(ld.BACKENDS),
            "neo_ios": ld.neo_io_names(),
            "sample_dtypes": list(ld.SAMPLE_DTYPES),
            "sync_strategies": list(ld.SYNC_STRATEGIES),
            "edges": list(ld.EDGES),
            "channel_defaults": list(ld.CHANNEL_DEFAULTS),
        },
        "templates": templates,
        "preview": {"available": False, "note": PREVIEW_NOTE},
    }


def validate(context):
    """Problems with a draft. Body: ``text``, and ``name`` when editing a saved definition."""
    original = context.value("name")
    name = check_name(original) if original is not None else None
    _, problems = draft_problems(context.project, context.value("text"), name, creating=name is None)
    return {"valid": not problems, "problems": problems}


def _refuse_links(project, path: Path) -> None:
    for item in (_folder(project), path):
        if item.is_symlink():
            raise ProjectError(
                f"{item.name} is a link to another location. Edit the original files outside ACE instead."
            )


def _backup(project, name: str, content: bytes, mode: int) -> str:
    backups = Path(project.path) / BACKUPS_DIRNAME
    backups.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = backups / f"loader-{name}-{stamp}-{uuid.uuid4().hex[:8]}.json"
    path.write_bytes(content)
    os.chmod(path, mode)
    return str(path)


def _check_version(path: Path, expected: Any) -> bytes | None:
    current = _read(path)
    if expected is None:
        if current is not None:
            raise ProjectChangedError(
                f"This project already has a loader named '{path.stem}'. Open it from the list, or choose another name."
            )
    elif not isinstance(expected, str):
        raise ProjectError("Reload this loader before saving.")
    elif current is None:
        raise ProjectChangedError(f"{path.name} was deleted elsewhere. Refresh the list; your edits are still on this page.")
    elif _digest(current) != expected:
        raise ProjectChangedError(
            f"{path.name} changed since you opened it. Reload it to see the saved version; your edits are still on this page."
        )
    return current


def save(context):
    """Save a valid definition. Body: ``name``, ``text`` and ``digest`` (null for a new loader)."""
    project = context.project
    path = _file(project, context.value("name"))
    expected = context.value("digest")
    text = context.value("text")
    _, problems = draft_problems(project, text, path.stem, creating=False)
    if problems:
        shown = "; ".join(f"{item['path'] or 'definition'}: {item['message']}" for item in problems[:3])
        more = f" (and {len(problems) - 3} more)" if len(problems) > 3 else ""
        raise ProjectError(f"Fix this loader before saving. {shown}{more}")
    _refuse_links(project, path)
    current = _check_version(path, expected)
    text = text.removeprefix("\ufeff")
    content = text if text.endswith("\n") else text + "\n"
    payload = content.encode("utf-8")
    if current == payload:
        # Nothing changed: no write and no backup, as for an unchanged CSV save.
        return {"name": path.stem, "digest": _digest(payload), "backup": None, "created": False}
    folder = _folder(project)
    folder.mkdir(exist_ok=True)
    # Staged with a non-.json suffix so a half-written file is never listed as a definition.
    descriptor, staged_name = tempfile.mkstemp(prefix=".ace-loader-", suffix=".tmp", dir=folder)
    staged = Path(staged_name)
    backup = None
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
        mode = path.stat().st_mode & 0o777 if current is not None else 0o644
        os.chmod(staged, mode)
        _check_version(path, expected)
        if current is not None:
            backup = _backup(project, path.stem, current, mode)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
    return {"name": path.stem, "digest": _digest(payload), "backup": backup, "created": current is None}


def delete(context):
    """Delete a definition after backing it up. Body: ``name`` and ``digest``."""
    project = context.project
    path = _file(project, context.value("name"))
    expected = context.value("digest")
    if not isinstance(expected, str):
        raise ProjectError("Reload this loader before deleting it.")
    _refuse_links(project, path)
    current = _check_version(path, expected)
    backup = _backup(project, path.stem, current, path.stat().st_mode & 0o777)
    path.unlink()
    return {"name": path.stem, "backup": backup}


def _ephys_folder(context) -> tuple[Path | None, dict[str, Any]]:
    """Resolve the experiment's ephys directory on this computer, as recording previews do."""
    value = context.project.experiments[context.number].get("ephys directory", "").strip()
    if not value:
        return None, {
            "status": "no-directory",
            "message": f"Experiment {context.number} has no ephys directory in experiments.csv. "
            "Set it in Experiment details, then check again.",
        }
    if ";" in value:
        return None, {
            "status": "several-directories",
            "message": "The ephys directory lists several folders. Loaders are checked against one recording folder.",
        }
    if PureWindowsPath(value).is_absolute() and not Path(value).is_absolute():
        return None, {
            "status": "missing",
            "message": "The ephys directory is a Windows path. Open this project on that computer, or use a relative folder.",
        }
    if Path(value).expanduser().is_absolute():
        candidates = [Path(value).expanduser()]
    else:
        # The project folder first, then the Box download folder, as when loading a recording.
        bases = [Path(context.project.path)]
        download = context.server.box.status().get("download_path")
        if isinstance(download, str) and download.strip():
            bases.append(Path(download).expanduser())
        candidates = [base / value for base in bases]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve(), {"status": "ok"}
    return None, {
        "status": "missing",
        "message": "The ephys folder is not on this computer. Download the recording or check the ephys directory.",
        "checked": [str(item) for item in candidates],
    }


def _matches(definition, folder: Path) -> list[dict[str, Any]]:
    rules = definition.detect
    found = []
    for pattern, paths in ld.matching_files(definition, folder).items():
        found.append(
            {
                "pattern": pattern,
                "rule": [key for key in ("all_of", "any_of", "none_of") if pattern in getattr(rules, key)],
                "count": len(paths),
                "examples": [path.relative_to(folder).as_posix() for path in paths[:MAX_SHOWN_MATCHES]],
            }
        )
    return found


def _suggest_loaders(folder, builtins, definitions):
    """Recommend configured loaders first and retain ambiguous file-type alternatives.

    Filename hints never prove a format and never open recordings or instantiate IOs.
    Only files directly in the experiment recording folder are inspected.
    """
    configured = [
        {"kind": kind, "name": item["name"], "label": item.get("label") or item["name"],
         "reason": "Matches this loader's filename rules. Confirm the acquisition format before using it."}
        for kind, items in (("builtin", builtins), ("project", definitions))
        for item in items if item["matches"]
    ]
    suffixes = {}
    for path in folder.iterdir():
        if path.is_file() and path.suffix:
            suffixes.setdefault(path.suffix.lower().lstrip("."), set()).add(path.suffix)
    suggestions = list(configured)
    for name in ld.neo_io_names():
        cls = ld._neo_io_class(name)
        if cls is None:
            continue
        extensions = {str(ext).lower().lstrip(".") for ext in getattr(cls, "extensions", ())}
        matched = sorted(set(suffixes) & extensions - {""})
        if not matched:
            continue
        try:
            parameters = inspect.signature(cls.__init__).parameters
        except (ValueError, TypeError):
            continue
        path_keys = ("dirname", "filename") if getattr(cls, "mode", None) == "dir" else ("filename", "dirname")
        argument = next((key for key in path_keys if key in parameters), None)
        if argument is None:
            continue
        args = {}
        if "mode" in parameters:
            read_only = ld.READ_ONLY_MODES_BY_IO.get(name, ld.READ_ONLY_MODES)
            args["mode"] = read_only[0]
        patterns = sorted("*" + actual for ext in matched for actual in suffixes[ext])
        suggestions.append({"kind": "neo", "name": name, "label": "Create a loader with " + name,
                            "patterns": patterns, "path_argument": argument, "args": args,
                            "reason": "Possible reader for " + ", ".join(patterns) + ". File extensions are a hint; confirm the format and settings."})
    binary = sorted(set(suffixes) & {"dat", "bin", "raw"})
    if binary:
        suggestions.append({"kind": "raw_binary", "name": "raw-binary", "label": "Create a raw binary loader",
                            "patterns": sorted("*" + actual for ext in binary for actual in suffixes[ext]),
                            "reason": "Possible binary recording. Confirm it is interleaved raw data; sample type, channel count, scaling and sampling rate cannot be inferred from the extension."})
    return suggestions


def detect(context):
    """Which loaders recognise the experiment's ephys folder. Body: ``number``; optional draft ``text``.

    Not locked: globbing a folder on a network drive can be slow.
    """
    folder, result = _ephys_folder(context)
    result["directory"] = context.project.experiments[context.number].get("ephys directory", "").strip()
    if folder is None:
        return result
    result["folder"] = str(folder)
    builtins = []
    for name, cls in _builtin_classes():
        try:
            builtins.append({"name": name, "matches": bool(cls.can_handle(folder))})
        except Exception as exc:  # A failing check is reported, not raised.
            builtins.append({"name": name, "matches": False, "error": str(exc)})
    definitions, problems = _project_definitions(context.project)
    project_results = [
        {"name": item.name, "label": item.label, "matches": ld.definition_matches(item, folder), "patterns": _matches(item, folder)}
        for item in definitions
    ]
    draft = None
    text = context.value("text")
    if text is not None:
        if not isinstance(text, str):
            raise ProjectError("Send the loader definition as JSON text.")
        # The same checks as validate and save, so a draft that cannot be saved is never shown as valid.
        data, draft_issues = draft_problems(context.project, text, None, creating=False)
        if draft_issues:
            draft = {"valid": False, "problems": draft_issues}
        else:
            parsed = ld.parse_definition(data)
            draft = {
                "valid": True,
                "name": parsed.name,
                "matches": ld.definition_matches(parsed, folder),
                "patterns": _matches(parsed, folder),
            }
    used = next((item["name"] for item in builtins if item["matches"]), None)
    result.update(
        {
            "builtins": builtins,
            "builtin_used": used,
            "definitions": project_results,
            "skipped": sorted(Path(key).name for key in problems),
            "draft": draft,
            "suggestions": _suggest_loaders(folder, builtins, project_results),
        }
    )
    return result


FEATURE = Feature(
    name="loaders",
    routes=(
        Route("GET", "/api/loaders", listing, scope="project"),
        Route("GET", "/api/loaders/definition", definition, scope="project"),
        Route("GET", "/api/loaders/schema", schema, scope="none"),
        Route("POST", "/api/loaders/validate", validate, scope="project"),
        Route("POST", "/api/loaders/save", save, scope="project", locked=True),
        Route("POST", "/api/loaders/delete", delete, scope="project", locked=True),
        Route("POST", "/api/loaders/detect", detect, scope="experiment"),
    ),
    scripts=("loaders.js",),
    styles=("loaders.css",),
    fragments=("loaders.html",),
)
