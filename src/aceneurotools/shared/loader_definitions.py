"""JSON definitions for user-described ephys loaders (schema ``ace-loader/1``).

A loader definition describes an acquisition system as configuration: how to
recognise its recording folder, which reader opens it, where sample times come
from, how channels are named and how it synchronises with other recordings.
Projects keep definitions in ``<project>/loaders/<name>.json``.

This module only parses, validates and matches definitions against folders.
It never reads signal data: :func:`definition_matches`, :func:`matching_files`
and :func:`resolve_files` look at file *names* only. Loading channels from a
definition belongs to the ephys data managers and is proposed separately
(ADR 0008).

Definitions travel inside run plans to other computers, so every file pattern
is a relative glob under the recording folder and no value may be a machine
path.

Public API
----------
SCHEMA                    -- the schema identifier, ``"ace-loader/1"``.
validate_definition       -- list every problem in a parsed JSON document.
parse_definition          -- build a :class:`LoaderDefinition` or raise.
load_definition           -- read and parse one ``<name>.json`` file.
load_project_definitions  -- read ``<project>/loaders/*.json``.
definition_matches        -- does a definition's ``detect`` match a folder?
matching_files            -- which entries each ``detect`` pattern matches.
resolve_files             -- locate the reader's files (names only).
definition_json_schema    -- JSON Schema (draft 2020-12) for ``ace-loader/1``.
neo_io_names              -- neo IO classes a definition may name.
"""

from __future__ import annotations

import copy
import difflib
import fnmatch
import glob as globlib
import inspect
import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeGuard

__all__ = [
    "SCHEMA",
    "LOADERS_DIRNAME",
    "DefinitionError",
    "DefinitionProblem",
    "LoaderDefinition",
    "Detect",
    "FileRule",
    "Capture",
    "PathFrom",
    "NeoReader",
    "RawBinaryReader",
    "CsvValue",
    "EffectiveRate",
    "TimeSpec",
    "ChannelSpec",
    "SyncSpec",
    "ResolvedFiles",
    "validate_definition",
    "parse_definition",
    "load_definition",
    "load_project_definitions",
    "definition_matches",
    "matching_files",
    "resolve_files",
    "definition_json_schema",
    "neo_io_names",
    "check_relative_glob",
]

SCHEMA = "ace-loader/1"
_SCHEMA_FAMILY = "ace-loader/"

#: Folder under a project that holds loader definitions.
LOADERS_DIRNAME = "loaders"

MODALITIES = ("ephys",)
BACKENDS = ("neo", "raw_binary")
SYNC_STRATEGIES = ("event_labels", "digital_threshold", "shared_clock")
PICK_MODES = ("only", "first_listed", "oldest_modified", "first_sorted")
PATH_SOURCES = ("recording_folder", "file", "file_parent")
TIME_SOURCES = ("reader", "clock_file", "sample_index")
CHANNEL_SOURCES = ("reader", "template")
CHANNEL_DEFAULTS = ("all", "none")
EDGES = ("rising", "falling", "both")
RATE_METHODS = ("median_interval",)
SAMPLE_DTYPES = (
    "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "float32", "float64",
)
CLOCK_DTYPES = ("uint32", "uint64", "int32", "int64", "float64")
OUTPUT_DTYPES = ("float32", "float64")
READ_ONLY_MODES = ("r", "ro")

#: neo IO classes a definition may not name, with the reason.
DENIED_NEO_IOS: Mapping[str, str] = {
    "PickleIO": "PickleIO unpickles files, which can run arbitrary code",
    "NeurosharectypesIO": "NeurosharectypesIO loads a native library named in its arguments",
}

NAME_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
NAME_MAX_LENGTH = 64
ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"
VARIABLE_PATTERN = r"^[a-z][a-z0-9_]*$"
INDEX_PLACEHOLDER = "{index}"

_NAME_RE = re.compile(NAME_PATTERN)
_ROLE_RE = re.compile(ROLE_PATTERN)
_VARIABLE_RE = re.compile(VARIABLE_PATTERN)
_PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Required and optional keys of every object in the format. The hand-written
# validator enforces these; tests check that definition_json_schema() agrees.
FIELDS: Mapping[str, tuple[frozenset[str], frozenset[str]]] = {
    "definition": (
        frozenset({"schema", "name", "label", "modality", "detect", "reader", "time", "channels", "sync"}),
        frozenset({"description"}),
    ),
    "detect": (frozenset(), frozenset({"all_of", "any_of", "none_of"})),
    "file": (
        frozenset({"role", "pattern"}),
        frozenset({"exclude_names", "exclude_dirs", "pick", "required", "capture"}),
    ),
    "capture": (frozenset({"variable", "split", "part"}), frozenset()),
    "reader.neo": (
        frozenset({"backend", "io", "path_argument", "path_from"}),
        frozenset({"files", "args", "read_block"}),
    ),
    "reader.raw_binary": (
        frozenset({"backend", "files", "signal_file", "dtype", "channel_count"}),
        frozenset({"gain", "offset", "byte_offset", "output_dtype"}),
    ),
    "path_from.recording_folder": (frozenset({"source"}), frozenset()),
    "path_from.file": (frozenset({"source", "file"}), frozenset()),
    "path_from.file_parent": (frozenset({"source", "file"}), frozenset()),
    "time.reader": (frozenset({"source"}), frozenset()),
    "time.clock_file": (
        frozenset({"source", "clock_file", "clock_dtype", "ticks_per_second", "effective_rate"}),
        frozenset(),
    ),
    "time.sample_index": (frozenset({"source", "sampling_rate_hz"}), frozenset()),
    "csv_value": (frozenset({"csv_file", "column"}), frozenset({"header_rows"})),
    "effective_rate": (frozenset({"method", "first_samples"}), frozenset()),
    "channels": (frozenset({"source", "default"}), frozenset({"template", "select_by_index"})),
    "sync.event_labels": (frozenset({"strategy", "labels"}), frozenset()),
    "sync.digital_threshold": (frozenset({"strategy", "channel", "threshold"}), frozenset({"edge"})),
    "sync.shared_clock": (frozenset({"strategy"}), frozenset()),
}

Scalar = str | int | float | bool | None


# ─────────────────────────────────────────────────────────────────────────────
# Problems and errors
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DefinitionProblem:
    """One thing wrong with a definition.

    Attributes:
        path: Location in the document, dotted with list indices in brackets
            (``"reader.io"``, ``"reader.files[1].pattern"``). Empty for the
            document as a whole.
        message: What is wrong, in words a user can act on.
    """

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}" if self.path else self.message


class DefinitionError(ValueError):
    """A loader definition is invalid. ``problems`` lists every issue found."""

    def __init__(self, problems: Iterable[DefinitionProblem], *, source: Path | None = None) -> None:
        self.problems: list[DefinitionProblem] = list(problems)
        self.source = source
        where = f"{source}: " if source is not None else ""
        lines = "\n".join(f"  {p}" for p in self.problems)
        super().__init__(f"{where}invalid loader definition ({len(self.problems)} problem(s)):\n{lines}")


# ─────────────────────────────────────────────────────────────────────────────
# Parsed definition
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Detect:
    """Folder recognition. Patterns are relative globs under the recording folder.

    A folder matches when every ``all_of`` pattern matches at least one entry,
    at least one ``any_of`` pattern matches (if any are given), and no
    ``none_of`` pattern matches.
    """

    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()
    none_of: tuple[str, ...] = ()

    @property
    def patterns(self) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for p in (*self.all_of, *self.any_of, *self.none_of):
            seen.setdefault(p, None)
        return tuple(seen)


@dataclass(frozen=True)
class Capture:
    """Take a value from a located file's stem: ``stem.split(split)[part]``."""

    variable: str
    split: str
    part: int

    def apply(self, stem: str) -> str:
        parts = stem.split(self.split)
        try:
            return parts[self.part]
        except IndexError:
            raise ValueError(
                f"cannot capture '{self.variable}': '{stem}' has {len(parts)} part(s) "
                f"when split on {self.split!r}, so part {self.part} does not exist"
            ) from None


@dataclass(frozen=True)
class FileRule:
    """A named file the reader needs, located by a relative glob.

    ``pattern`` may contain ``{variable}`` placeholders captured by earlier
    rules; captured values are inserted literally (glob characters escaped).
    """

    role: str
    pattern: str
    exclude_names: tuple[str, ...] = ()
    exclude_dirs: tuple[str, ...] = ()
    pick: str = "only"
    required: bool = True
    capture: Capture | None = None


@dataclass(frozen=True)
class PathFrom:
    """What the loader passes as the reader's path argument."""

    source: str  # recording_folder | file | file_parent
    file: str | None = None


@dataclass(frozen=True)
class NeoReader:
    """Open the recording with a class from ``neo.io.iolist``.

    The loader calls ``io(**{path_argument: <path>}, **args)`` and then
    ``read_block(**read_block)``. The path is never part of ``args``.
    """

    io: str
    path_argument: str
    path_from: PathFrom
    files: tuple[FileRule, ...] = ()
    args: dict[str, Scalar] = field(default_factory=dict, hash=False)
    read_block: dict[str, Scalar] = field(default_factory=dict, hash=False)

    backend = "neo"


@dataclass(frozen=True)
class RawBinaryReader:
    """Interleaved sample-major binary signal file (``neo.rawio.RawBinarySignalRawIO``).

    Values are ``raw.astype(output_dtype) * gain + offset``.
    """

    files: tuple[FileRule, ...]
    signal_file: str
    dtype: str
    channel_count: int
    gain: float = 1.0
    offset: float = 0.0
    byte_offset: int = 0
    output_dtype: str = "float32"

    backend = "raw_binary"


Reader = NeoReader | RawBinaryReader


@dataclass(frozen=True)
class CsvValue:
    """A number read from a located CSV file (no header unless ``header_rows``)."""

    csv_file: str
    column: int
    header_rows: int = 0


@dataclass(frozen=True)
class EffectiveRate:
    """How ``Channel.sampling_rate`` is derived from a clock time vector."""

    method: str  # median_interval: 1 / median(diff(times[:first_samples]))
    first_samples: int


@dataclass(frozen=True)
class TimeSpec:
    """Where sample times come from.

    * ``reader`` -- the neo reader's segments (via ``BlockProcessor``).
    * ``clock_file`` -- a binary clock file of ``clock_dtype`` ticks;
      ``seconds = ticks / ticks_per_second`` in float64.
    * ``sample_index`` -- ``arange(n) / sampling_rate_hz``.
    """

    source: str
    clock_file: str | None = None
    clock_dtype: str | None = None
    ticks_per_second: float | CsvValue | None = None
    effective_rate: EffectiveRate | None = None
    sampling_rate_hz: float | None = None


@dataclass(frozen=True)
class ChannelSpec:
    """How channels are named and which are loaded when none are requested."""

    source: str  # reader | template
    default: str  # all | none
    template: str | None = None
    select_by_index: bool = False

    def name_for(self, index: int) -> str:
        if self.template is None:
            raise ValueError("channel names come from the reader; there is no template")
        return self.template.replace(INDEX_PLACEHOLDER, str(index))


@dataclass(frozen=True)
class SyncSpec:
    """How the recording is synchronised with other modalities."""

    strategy: str
    labels: tuple[str, ...] = ()
    channel: str | None = None
    threshold: float | None = None
    edge: str | None = None


@dataclass(frozen=True)
class LoaderDefinition:
    """A validated ``ace-loader/1`` definition.

    ``raw`` is the original JSON object; ``source`` is the file it came from,
    if any. Neither takes part in equality.
    """

    name: str
    label: str
    modality: str
    detect: Detect
    reader: Reader
    time: TimeSpec
    channels: ChannelSpec
    sync: SyncSpec
    description: str | None = None
    schema: str = SCHEMA
    source: Path | None = field(default=None, compare=False)
    raw: dict[str, Any] = field(default_factory=dict, compare=False, hash=False, repr=False)

    @property
    def backend(self) -> str:
        return self.reader.backend

    @property
    def files(self) -> tuple[FileRule, ...]:
        return self.reader.files


@dataclass(frozen=True)
class ResolvedFiles:
    """Files located for a definition in one recording folder."""

    files: dict[str, Path] = field(hash=False)
    variables: dict[str, str] = field(hash=False)


# ─────────────────────────────────────────────────────────────────────────────
# Small checks
# ─────────────────────────────────────────────────────────────────────────────

def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return (_is_int(value) or isinstance(value, float)) and math.isfinite(value)  # type: ignore[arg-type]


def _looks_like_machine_path(text: str) -> bool:
    if text.startswith(("/", "~")) or "\\" in text or _DRIVE_RE.match(text):
        return True
    return ".." in text.split("/")


def check_relative_glob(pattern: object) -> str | None:
    """Return why ``pattern`` is not a safe relative glob, or ``None`` if it is.

    Patterns are evaluated with :meth:`pathlib.Path.glob` under the recording
    folder. They must use ``/`` separators and may not be absolute, start with
    ``~`` or a drive letter, contain backslashes, or have empty, ``.`` or
    ``..`` segments.
    """
    if not isinstance(pattern, str):
        return "must be a string"
    if not pattern:
        return "must not be empty"
    if "\x00" in pattern:
        return "must not contain NUL characters"
    if "\\" in pattern:
        return "must use '/' separators, not backslashes"
    if pattern.startswith("/"):
        return "must be relative to the recording folder, not an absolute path"
    if pattern.startswith("~"):
        return "must be relative to the recording folder, not a home-directory path"
    if _DRIVE_RE.match(pattern):
        return "must be relative to the recording folder, not start with a drive letter"
    segments = pattern.split("/")
    if ".." in segments:
        return "must stay inside the recording folder ('..' is not allowed)"
    if "." in segments:
        return "must not contain '.' segments"
    if "" in segments:
        return "must not contain empty segments ('//' or a trailing '/')"
    if any("**" in seg and seg != "**" for seg in segments):
        return "'**' must be a whole segment, as in 'sub/**/file.ext'"
    return None


def neo_io_names() -> list[str]:
    """Names of the neo IO classes a definition may use (sorted).

    This is ``neo.io.iolist`` minus :data:`DENIED_NEO_IOS`. neo is imported
    on first call only.
    """
    import neo.io  # type: ignore  # lazy: neo is heavy and only needed for neo readers

    return sorted({cls.__name__ for cls in neo.io.iolist} - set(DENIED_NEO_IOS))


def _neo_io_class(name: str) -> Any:
    import neo.io  # type: ignore

    for cls in neo.io.iolist:
        if cls.__name__ == name:
            return cls
    return None


def _parameters(func: Any) -> tuple[set[str], bool]:
    """Named parameters of ``func`` (minus self) and whether it takes ``**kwargs``."""
    try:
        sig = inspect.signature(func)
    except (TypeError, ValueError):
        return set(), True
    names: set[str] = set()
    var_kw = False
    for p in sig.parameters.values():
        if p.kind is p.VAR_KEYWORD:
            var_kw = True
        elif p.kind is not p.VAR_POSITIONAL and p.name != "self":
            names.add(p.name)
    return names, var_kw


# ─────────────────────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────────────────────

def _join(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}.{key}" if path else key


class _Validator:
    def __init__(self) -> None:
        self.problems: list[DefinitionProblem] = []

    def add(self, path: str, message: str) -> None:
        self.problems.append(DefinitionProblem(path, message))

    # generic shapes -----------------------------------------------------------

    def obj(self, value: object, path: str, section: str) -> dict[str, Any] | None:
        """Check ``value`` is an object with exactly the keys ``section`` allows."""
        if not isinstance(value, dict):
            self.add(path, "must be an object")
            return None
        required, optional = FIELDS[section]
        allowed = required | optional
        for key in value:
            if key not in allowed:
                hint = difflib.get_close_matches(str(key), sorted(allowed), n=1)
                extra = f"; did you mean '{hint[0]}'?" if hint else ""
                self.add(_join(path, str(key)), f"unknown key{extra} (allowed: {', '.join(sorted(allowed))})")
        for key in sorted(required):
            if key not in value:
                self.add(_join(path, key), "is required")
        return value

    def text(self, value: object, path: str, *, allow_empty: bool = False) -> TypeGuard[str]:
        if not isinstance(value, str):
            self.add(path, "must be a string")
            return False
        if not allow_empty and not value.strip():
            self.add(path, "must not be empty")
            return False
        return True

    def choice(self, value: object, path: str, options: tuple[str, ...]) -> TypeGuard[str]:
        if not isinstance(value, str) or value not in options:
            self.add(path, f"must be one of: {', '.join(options)} (got {value!r})")
            return False
        return True

    def integer(self, value: object, path: str, *, minimum: int | None = None) -> bool:
        if not _is_int(value):
            self.add(path, "must be an integer")
            return False
        if minimum is not None and value < minimum:  # type: ignore[operator]
            self.add(path, f"must be at least {minimum}")
            return False
        return True

    def number(self, value: object, path: str, *, positive: bool = False) -> bool:
        if not _is_number(value):
            self.add(path, "must be a finite number")
            return False
        if positive and value <= 0:  # type: ignore[operator]
            self.add(path, "must be greater than 0")
            return False
        return True

    def boolean(self, value: object, path: str) -> bool:
        if not isinstance(value, bool):
            self.add(path, "must be true or false")
            return False
        return True

    def string_list(self, value: object, path: str, *, non_empty: bool = False) -> list[str] | None:
        if not isinstance(value, list):
            self.add(path, "must be a list of strings")
            return None
        if non_empty and not value:
            self.add(path, "must not be empty")
        good = True
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item:
                self.add(_join(path, i), "must be a non-empty string")
                good = False
        strings = [v for v in value if isinstance(v, str)]
        if len(set(strings)) != len(strings):
            self.add(path, "must not contain duplicates")
        return value if good else None

    def glob_list(self, value: object, path: str) -> None:
        items = self.string_list(value, path)
        if items is None:
            return
        for i, pattern in enumerate(items):
            reason = check_relative_glob(pattern)
            if reason:
                self.add(_join(path, i), reason)
            elif "{" in pattern or "}" in pattern:
                self.add(_join(path, i), "detect patterns cannot use {placeholders}")

    def scalar_args(self, value: object, path: str) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            self.add(path, "must be an object of argument names to JSON scalars")
            return None
        for key, item in value.items():
            p = _join(path, str(key))
            if not isinstance(key, str) or not _IDENTIFIER_RE.match(key):
                self.add(p, "argument names must be Python identifiers")
            if isinstance(item, float) and not math.isfinite(item):
                self.add(p, "must be a finite number")
            elif not (item is None or isinstance(item, (str, int, float, bool))):
                self.add(p, "must be a string, number, true/false or null")
            elif isinstance(item, str) and _looks_like_machine_path(item):
                self.add(p, "must not be a machine path (definitions travel to other computers)")
        return value

    # sections -----------------------------------------------------------------

    def definition(self, data: object) -> None:
        if not isinstance(data, dict):
            self.add("", "a loader definition must be a JSON object")
            return

        schema = data.get("schema")
        if "schema" in data:
            if not isinstance(schema, str):
                self.add("schema", f"must be the string '{SCHEMA}'")
            elif schema != SCHEMA:
                if schema.startswith(_SCHEMA_FAMILY):
                    # Another version: its fields may legitimately differ, so
                    # report the version alone rather than a list of key errors.
                    self.add(
                        "schema",
                        f"unsupported version '{schema}'; this ACE-NeuroTools reads '{SCHEMA}' only",
                    )
                    return
                self.add("schema", f"must be '{SCHEMA}' (got {schema!r})")

        self.obj(data, "", "definition")

        if "name" in data:
            name = data["name"]
            if self.text(name, "name"):
                if len(name) > NAME_MAX_LENGTH:
                    self.add("name", f"must be at most {NAME_MAX_LENGTH} characters")
                elif not _NAME_RE.match(name):
                    self.add("name", "must be kebab-case: lowercase letters and digits separated by '-'")
        if "label" in data:
            self.text(data["label"], "label")
        if "description" in data:
            self.text(data["description"], "description", allow_empty=True)
        if "modality" in data:
            modality = data["modality"]
            if modality != "ephys":
                self.add("modality", f"must be 'ephys'; {SCHEMA} describes ephys loaders only (got {modality!r})")

        if "detect" in data:
            self.detect(data["detect"])

        backend = None
        roles: dict[str, FileRule | None] = {}
        if "reader" in data:
            backend, roles = self.reader(data["reader"])
        if "time" in data:
            self.time(data["time"], backend, roles)
        if "channels" in data:
            self.channels(data["channels"], backend)
        if "sync" in data:
            self.sync(data["sync"], backend)

    def detect(self, value: object) -> None:
        d = self.obj(value, "detect", "detect")
        if d is None:
            return
        for key in ("all_of", "any_of", "none_of"):
            if key in d:
                self.glob_list(d[key], f"detect.{key}")
        positive = [d.get("all_of"), d.get("any_of")]
        if not any(isinstance(v, list) and v for v in positive):
            self.add("detect", "needs at least one pattern in all_of or any_of")

    def files(self, value: object, path: str) -> dict[str, FileRule | None]:
        """Validate a ``files`` list. Returns role name -> rule (None if invalid)."""
        roles: dict[str, FileRule | None] = {}
        if not isinstance(value, list):
            self.add(path, "must be a list of file rules")
            return roles
        captured: list[str] = []
        for i, item in enumerate(value):
            p = _join(path, i)
            rule = self.obj(item, p, "file")
            if rule is None:
                continue
            role = rule.get("role")
            if "role" in rule and self.text(role, f"{p}.role"):
                if not _ROLE_RE.match(role):
                    self.add(f"{p}.role", "must be lowercase letters, digits and '_', starting with a letter")
                elif role in roles:
                    self.add(f"{p}.role", f"role '{role}' is already defined")
            if "pattern" in rule:
                self.file_pattern(rule["pattern"], f"{p}.pattern", captured)
            for key in ("exclude_names", "exclude_dirs"):
                if key in rule:
                    names = self.string_list(rule[key], f"{p}.{key}")
                    for j, name in enumerate(names or []):
                        if "/" in name or "\\" in name:
                            self.add(f"{p}.{key}[{j}]", "must be a single name, without '/' or '\\'")
                        elif key == "exclude_dirs" and name in (".", ".."):
                            self.add(f"{p}.{key}[{j}]", "must be a folder name, not '.' or '..'")
            if "pick" in rule:
                self.choice(rule["pick"], f"{p}.pick", PICK_MODES)
            if "required" in rule:
                self.boolean(rule["required"], f"{p}.required")
            if "capture" in rule:
                cap = self.obj(rule["capture"], f"{p}.capture", "capture")
                if cap is not None:
                    var = cap.get("variable")
                    if "variable" in cap and self.text(var, f"{p}.capture.variable"):
                        if not _VARIABLE_RE.match(var):
                            self.add(f"{p}.capture.variable", "must be lowercase letters, digits and '_'")
                        elif var in captured:
                            self.add(f"{p}.capture.variable", f"variable '{var}' is already captured")
                        elif var == "index":
                            self.add(f"{p}.capture.variable", "'index' is reserved for channel templates")
                        else:
                            captured.append(var)
                    if "split" in cap:
                        self.text(cap["split"], f"{p}.capture.split", allow_empty=True)
                        if cap["split"] == "":
                            self.add(f"{p}.capture.split", "must not be empty")
                    if "part" in cap:
                        self.integer(cap["part"], f"{p}.capture.part")
            if isinstance(role, str) and role not in roles:
                roles[role] = None  # existence is what cross-references need
        return roles

    def file_pattern(self, value: object, path: str, captured: list[str]) -> None:
        reason = check_relative_glob(value)
        if reason:
            self.add(path, reason)
            return
        assert isinstance(value, str)
        for var in _PLACEHOLDER_RE.findall(value):
            if var not in captured:
                known = ", ".join(captured) or "none yet"
                self.add(path, f"placeholder '{{{var}}}' is not captured by an earlier file rule (captured: {known})")
        if "{" in _PLACEHOLDER_RE.sub("", value) or "}" in _PLACEHOLDER_RE.sub("", value):
            self.add(path, "has an unmatched '{' or '}'")

    def role_ref(self, value: object, path: str, roles: Mapping[str, object]) -> None:
        if self.text(value, path) and value not in roles:
            known = ", ".join(roles) or "none"
            self.add(path, f"must name a role from reader.files (defined: {known})")

    def reader(self, value: object) -> tuple[str | None, dict[str, FileRule | None]]:
        if not isinstance(value, dict):
            self.add("reader", "must be an object")
            return None, {}
        backend = value.get("backend")
        if not self.choice(backend, "reader.backend", BACKENDS):
            return None, {}
        r = self.obj(value, "reader", f"reader.{backend}")
        assert r is not None
        roles: dict[str, FileRule | None] = self.files(r["files"], "reader.files") if "files" in r else {}

        if backend == "neo":
            self.neo_reader(r, roles)
        else:
            if "files" in r and isinstance(r["files"], list) and not r["files"]:
                self.add("reader.files", "must list at least the signal file")
            if "signal_file" in r:
                self.role_ref(r["signal_file"], "reader.signal_file", roles)
            if "dtype" in r:
                self.choice(r["dtype"], "reader.dtype", SAMPLE_DTYPES)
            if "channel_count" in r:
                self.integer(r["channel_count"], "reader.channel_count", minimum=1)
            if "gain" in r and self.number(r["gain"], "reader.gain") and r["gain"] == 0:
                self.add("reader.gain", "must not be 0")
            if "offset" in r:
                self.number(r["offset"], "reader.offset")
            if "byte_offset" in r:
                self.integer(r["byte_offset"], "reader.byte_offset", minimum=0)
            if "output_dtype" in r:
                self.choice(r["output_dtype"], "reader.output_dtype", OUTPUT_DTYPES)
        return backend, roles

    def neo_reader(self, r: dict[str, Any], roles: Mapping[str, object]) -> None:
        if "path_from" in r:
            pf = r["path_from"]
            if not isinstance(pf, dict):
                self.add("reader.path_from", "must be an object")
            elif self.choice(pf.get("source"), "reader.path_from.source", PATH_SOURCES):
                self.obj(pf, "reader.path_from", f"path_from.{pf['source']}")
                if "file" in pf:
                    self.role_ref(pf["file"], "reader.path_from.file", roles)
        args = self.scalar_args(r["args"], "reader.args") if "args" in r else {}
        block_args = self.scalar_args(r["read_block"], "reader.read_block") if "read_block" in r else {}
        path_arg = r.get("path_argument")
        if "path_argument" in r and self.text(path_arg, "reader.path_argument"):
            if not _IDENTIFIER_RE.match(path_arg):
                self.add("reader.path_argument", "must be a Python identifier")
            elif args and path_arg in args:
                self.add(f"reader.args.{path_arg}", "is the path argument; the loader supplies the path")
        io_name = r.get("io")
        if "io" not in r or not self.text(io_name, "reader.io"):
            return
        self.neo_io(io_name, path_arg if isinstance(path_arg, str) else None, args or {}, block_args or {})

    def neo_io(self, io_name: str, path_arg: str | None, args: Mapping[str, Any], block_args: Mapping[str, Any]) -> None:
        if io_name in DENIED_NEO_IOS:
            self.add("reader.io", f"'{io_name}' is not allowed: {DENIED_NEO_IOS[io_name]}")
            return
        try:
            allowed = neo_io_names()
        except Exception as exc:  # pragma: no cover - neo is a hard dependency
            self.add("reader.io", f"cannot check the reader because neo failed to import: {exc}")
            return
        if io_name not in allowed:
            hint = difflib.get_close_matches(io_name, allowed, n=1)
            extra = f"; did you mean '{hint[0]}'?" if hint else ""
            self.add("reader.io", f"'{io_name}' is not a neo IO in neo.io.iolist{extra}")
            return
        cls = _neo_io_class(io_name)
        init_params, init_var_kw = _parameters(cls.__init__)
        if path_arg is not None and _IDENTIFIER_RE.match(path_arg) and path_arg not in init_params:
            self.add(
                "reader.path_argument",
                f"{io_name} has no '{path_arg}' argument (its arguments: {', '.join(sorted(init_params))})",
            )
        for key, item in args.items():
            if key == path_arg:
                continue  # reported by neo_reader
            if not init_var_kw and key not in init_params:
                self.add(f"reader.args.{key}", f"{io_name} has no argument '{key}'")
            elif key == "mode" and item not in READ_ONLY_MODES:
                self.add(f"reader.args.{key}", f"must open read-only ({', '.join(READ_ONLY_MODES)})")
        read_block = getattr(cls, "read_block", None)
        if read_block is None:
            self.add("reader.io", f"{io_name} has no read_block method")
            return
        block_params, block_var_kw = _parameters(read_block)
        for key in block_args:
            if not block_var_kw and key not in block_params:
                self.add(f"reader.read_block.{key}", f"{io_name}.read_block has no argument '{key}'")

    def time(self, value: object, backend: str | None, roles: Mapping[str, object]) -> None:
        if not isinstance(value, dict):
            self.add("time", "must be an object")
            return
        source = value.get("source")
        if not self.choice(source, "time.source", TIME_SOURCES):
            return
        t = self.obj(value, "time", f"time.{source}")
        assert t is not None
        if backend == "neo" and source != "reader":
            self.add("time.source", "neo readers take times from the reader; use 'reader'")
        if backend == "raw_binary" and source == "reader":
            self.add("time.source", "raw_binary readers need 'clock_file' or 'sample_index'")
        if source == "clock_file":
            if "clock_file" in t:
                self.role_ref(t["clock_file"], "time.clock_file", roles)
            if "clock_dtype" in t:
                self.choice(t["clock_dtype"], "time.clock_dtype", CLOCK_DTYPES)
            if "ticks_per_second" in t:
                tps = t["ticks_per_second"]
                if isinstance(tps, dict):
                    csv = self.obj(tps, "time.ticks_per_second", "csv_value")
                    if csv is not None:
                        if "csv_file" in csv:
                            self.role_ref(csv["csv_file"], "time.ticks_per_second.csv_file", roles)
                        if "column" in csv:
                            self.integer(csv["column"], "time.ticks_per_second.column", minimum=0)
                        if "header_rows" in csv:
                            self.integer(csv["header_rows"], "time.ticks_per_second.header_rows", minimum=0)
                else:
                    self.number(tps, "time.ticks_per_second", positive=True)
            if "effective_rate" in t:
                er = self.obj(t["effective_rate"], "time.effective_rate", "effective_rate")
                if er is not None:
                    if "method" in er:
                        self.choice(er["method"], "time.effective_rate.method", RATE_METHODS)
                    if "first_samples" in er:
                        self.integer(er["first_samples"], "time.effective_rate.first_samples", minimum=2)
        elif source == "sample_index" and "sampling_rate_hz" in t:
            self.number(t["sampling_rate_hz"], "time.sampling_rate_hz", positive=True)

    def channels(self, value: object, backend: str | None) -> None:
        c = self.obj(value, "channels", "channels")
        if c is None:
            return
        source = c.get("source")
        if "source" in c and self.choice(source, "channels.source", CHANNEL_SOURCES):
            if backend == "neo" and source != "reader":
                self.add("channels.source", "neo readers name channels themselves; use 'reader'")
            if backend == "raw_binary" and source != "template":
                self.add("channels.source", "raw_binary channels need names; use 'template'")
            if source == "template" and "template" not in c:
                self.add("channels.template", "is required when source is 'template'")
            if source == "reader":
                for key in ("template", "select_by_index"):
                    if key in c:
                        self.add(f"channels.{key}", "applies only when source is 'template'")
        if "default" in c:
            self.choice(c["default"], "channels.default", CHANNEL_DEFAULTS)
        if "template" in c and self.text(c["template"], "channels.template"):
            template = c["template"]
            others = [v for v in _PLACEHOLDER_RE.findall(template) if v != "index"]
            if INDEX_PLACEHOLDER not in template:
                self.add("channels.template", "must contain '{index}'")
            elif others:
                self.add("channels.template", f"only '{{index}}' may be used (found {{{others[0]}}})")
            elif "{" in _PLACEHOLDER_RE.sub("", template) or "}" in _PLACEHOLDER_RE.sub("", template):
                self.add("channels.template", "has an unmatched '{' or '}'")
        if "select_by_index" in c:
            self.boolean(c["select_by_index"], "channels.select_by_index")

    def sync(self, value: object, backend: str | None) -> None:
        if not isinstance(value, dict):
            self.add("sync", "must be an object")
            return
        strategy = value.get("strategy")
        if not self.choice(strategy, "sync.strategy", SYNC_STRATEGIES):
            return
        s = self.obj(value, "sync", f"sync.{strategy}")
        assert s is not None
        if strategy == "event_labels":
            if backend == "raw_binary":
                self.add("sync.strategy", "raw_binary readers record no events; use digital_threshold or shared_clock")
            if "labels" in s:
                self.string_list(s["labels"], "sync.labels", non_empty=True)
        elif strategy == "digital_threshold":
            if "channel" in s:
                self.text(s["channel"], "sync.channel")
            if "threshold" in s:
                self.number(s["threshold"], "sync.threshold")
            if "edge" in s:
                self.choice(s["edge"], "sync.edge", EDGES)


def validate_definition(data: object) -> list[DefinitionProblem]:
    """Return every problem in a parsed JSON document; empty when valid.

    Never raises for bad input. Checks the ``io`` name of neo readers against
    ``neo.io.iolist`` (importing neo on demand). Does not check the file name;
    :func:`load_definition` adds that rule.
    """
    v = _Validator()
    try:
        v.definition(data)
    except Exception as exc:  # pragma: no cover - defensive: report, never raise
        v.add("", f"could not validate definition: {exc!r}")
    return v.problems


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _build_files(items: list[dict[str, Any]]) -> tuple[FileRule, ...]:
    rules = []
    for item in items:
        cap = item.get("capture")
        rules.append(
            FileRule(
                role=item["role"],
                pattern=item["pattern"],
                exclude_names=tuple(item.get("exclude_names", ())),
                exclude_dirs=tuple(item.get("exclude_dirs", ())),
                pick=item.get("pick", "only"),
                required=item.get("required", True),
                capture=Capture(cap["variable"], cap["split"], cap["part"]) if cap else None,
            )
        )
    return tuple(rules)


def _build(data: dict[str, Any], source: Path | None) -> LoaderDefinition:
    d = data["detect"]
    detect = Detect(
        all_of=tuple(d.get("all_of", ())),
        any_of=tuple(d.get("any_of", ())),
        none_of=tuple(d.get("none_of", ())),
    )

    r = data["reader"]
    files = _build_files(r.get("files", []))
    reader: Reader
    if r["backend"] == "neo":
        pf = r["path_from"]
        reader = NeoReader(
            io=r["io"],
            path_argument=r["path_argument"],
            path_from=PathFrom(pf["source"], pf.get("file")),
            files=files,
            args=dict(r.get("args", {})),
            read_block=dict(r.get("read_block", {})),
        )
    else:
        reader = RawBinaryReader(
            files=files,
            signal_file=r["signal_file"],
            dtype=r["dtype"],
            channel_count=r["channel_count"],
            gain=float(r.get("gain", 1.0)),
            offset=float(r.get("offset", 0.0)),
            byte_offset=r.get("byte_offset", 0),
            output_dtype=r.get("output_dtype", "float32"),
        )

    t = data["time"]
    tps = t.get("ticks_per_second")
    ticks: float | CsvValue | None
    if isinstance(tps, dict):
        ticks = CsvValue(tps["csv_file"], tps["column"], tps.get("header_rows", 0))
    else:
        ticks = float(tps) if tps is not None else None
    er = t.get("effective_rate")
    time = TimeSpec(
        source=t["source"],
        clock_file=t.get("clock_file"),
        clock_dtype=t.get("clock_dtype"),
        ticks_per_second=ticks,
        effective_rate=EffectiveRate(er["method"], er["first_samples"]) if er else None,
        sampling_rate_hz=float(t["sampling_rate_hz"]) if "sampling_rate_hz" in t else None,
    )

    c = data["channels"]
    channels = ChannelSpec(
        source=c["source"],
        default=c["default"],
        template=c.get("template"),
        select_by_index=c.get("select_by_index", False),
    )

    s = data["sync"]
    sync = SyncSpec(
        strategy=s["strategy"],
        labels=tuple(s.get("labels", ())),
        channel=s.get("channel"),
        threshold=float(s["threshold"]) if "threshold" in s else None,
        edge=s.get("edge", "rising") if s["strategy"] == "digital_threshold" else None,
    )

    return LoaderDefinition(
        name=data["name"],
        label=data["label"],
        modality=data["modality"],
        detect=detect,
        reader=reader,
        time=time,
        channels=channels,
        sync=sync,
        description=data.get("description"),
        schema=data["schema"],
        source=source,
        raw=copy.deepcopy(data),
    )


def parse_definition(data: object, *, source: Path | None = None) -> LoaderDefinition:
    """Validate ``data`` and return a :class:`LoaderDefinition`.

    Raises:
        DefinitionError: listing every problem when ``data`` is invalid.
    """
    problems = validate_definition(data)
    if problems:
        raise DefinitionError(problems, source=source)
    assert isinstance(data, dict)
    return _build(data, source)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate key '{key}'")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def _loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_strict_object, parse_constant=_reject_constant)


def load_definition(path: str | Path) -> LoaderDefinition:
    """Read and parse one definition file.

    The file name without ``.json`` must equal the definition's ``name``.

    Raises:
        DefinitionError: the file is not valid JSON or not a valid definition.
        OSError: the file cannot be read.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise DefinitionError([DefinitionProblem("", f"file is not UTF-8 text: {exc}")], source=path) from None
    try:
        data = _loads(text)
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise DefinitionError([DefinitionProblem("", f"invalid JSON: {exc}")], source=path) from None
    problems = validate_definition(data)
    if isinstance(data, dict) and isinstance(data.get("name"), str) and data["name"] != path.stem:
        problems.append(
            DefinitionProblem("name", f"'{data['name']}' must match the file name ('{path.stem}.json')")
        )
    if problems:
        raise DefinitionError(problems, source=path)
    return _build(data, path)


def load_project_definitions(
    project_path: str | Path,
    *,
    reserved_names: Iterable[str] = (),
) -> tuple[list[LoaderDefinition], dict[str, list[DefinitionProblem]]]:
    """Read every ``<project>/loaders/*.json`` definition.

    Invalid files are reported, not raised. A name used by more than one
    definition, or listed in ``reserved_names`` (for example built-in loader
    names), is a problem for every file that uses it, and none of those
    definitions is returned.

    Returns:
        ``(definitions, problems)`` where definitions are sorted by file name
        and ``problems`` maps each failing file's path (as ``str``) to its
        problems. A project without a ``loaders`` folder gives ``([], {})``.
    """
    folder = Path(project_path) / LOADERS_DIRNAME
    if not folder.is_dir():
        return [], {}

    loaded: list[LoaderDefinition] = []
    problems: dict[str, list[DefinitionProblem]] = {}
    for file in sorted(folder.glob("*.json")):
        if not file.is_file():
            continue
        try:
            loaded.append(load_definition(file))
        except DefinitionError as exc:
            problems[str(file)] = list(exc.problems)
        except OSError as exc:
            problems[str(file)] = [DefinitionProblem("", f"cannot read file: {exc}")]

    reserved = set(reserved_names)
    by_name: dict[str, list[LoaderDefinition]] = {}
    for definition in loaded:
        by_name.setdefault(definition.name, []).append(definition)

    kept: list[LoaderDefinition] = []
    for definition in loaded:
        group = by_name[definition.name]
        key = str(definition.source)
        if definition.name in reserved:
            problems.setdefault(key, []).append(
                DefinitionProblem("name", f"'{definition.name}' is already used by a built-in loader")
            )
        elif len(group) > 1:
            others = ", ".join(str(d.source) for d in group if d is not definition)
            problems.setdefault(key, []).append(
                DefinitionProblem("name", f"'{definition.name}' is also defined in {others}")
            )
        else:
            kept.append(definition)
    return kept, problems


# ─────────────────────────────────────────────────────────────────────────────
# Matching (file names only; never reads file contents)
# ─────────────────────────────────────────────────────────────────────────────

def _require_safe(pattern: str) -> None:
    # Validation guarantees safe patterns; re-check because callers may build
    # definitions by hand.
    reason = check_relative_glob(pattern)
    if reason:
        raise ValueError(f"unsafe pattern {pattern!r}: {reason}")


def _glob(directory: Path, pattern: str) -> list[Path]:
    _require_safe(pattern)
    return list(directory.glob(pattern))


def matching_files(definition: LoaderDefinition | Detect, directory: str | Path) -> dict[str, list[Path]]:
    """Entries each ``detect`` pattern matches in ``directory`` (sorted).

    Every pattern from ``all_of``, ``any_of`` and ``none_of`` appears once as
    a key. A missing directory gives empty lists.
    """
    detect = definition.detect if isinstance(definition, LoaderDefinition) else definition
    folder = Path(directory)
    exists = folder.is_dir()
    return {p: sorted(_glob(folder, p)) if exists else [] for p in detect.patterns}


def definition_matches(definition: LoaderDefinition | Detect, directory: str | Path) -> bool:
    """Whether ``directory`` matches the definition's ``detect`` rules.

    Matches are any entries (files or folders) found by
    :meth:`pathlib.Path.glob`, the same test the built-in ``can_handle``
    methods use. A missing directory never matches.
    """
    detect = definition.detect if isinstance(definition, LoaderDefinition) else definition
    folder = Path(directory)
    if not folder.is_dir():
        return False

    def found(pattern: str) -> bool:
        _require_safe(pattern)
        return next(iter(folder.glob(pattern)), None) is not None

    if not all(found(p) for p in detect.all_of):
        return False
    if detect.any_of and not any(found(p) for p in detect.any_of):
        return False
    return not any(found(p) for p in detect.none_of)


def _candidates(folder: Path, rule: FileRule, variables: Mapping[str, str]) -> list[Path]:
    pattern = _PLACEHOLDER_RE.sub(lambda m: globlib.escape(variables[m.group(1)]), rule.pattern)
    found = []
    for path in _glob(folder, pattern):
        if not path.is_file():
            continue
        if any(fnmatch.fnmatchcase(path.name, ex) for ex in rule.exclude_names):
            continue
        if any(part in rule.exclude_dirs for part in path.relative_to(folder).parts[:-1]):
            continue
        found.append(path)
    return found


def _pick(rule: FileRule, candidates: list[Path], folder: Path) -> Path:
    if rule.pick == "only":
        if len(candidates) > 1:
            names = ", ".join(sorted(p.relative_to(folder).as_posix() for p in candidates))
            raise ValueError(f"file rule '{rule.role}' ({rule.pattern}) matches several files in {folder}: {names}")
        return candidates[0]
    if rule.pick == "first_listed":
        return candidates[0]
    if rule.pick == "oldest_modified":
        return sorted(candidates, key=lambda p: p.stat().st_mtime)[0]
    if rule.pick == "first_sorted":
        return sorted(candidates, key=lambda p: p.relative_to(folder).as_posix())[0]
    raise ValueError(f"unknown pick mode {rule.pick!r}")


def resolve_files(definition: LoaderDefinition, directory: str | Path) -> ResolvedFiles:
    """Locate the reader's files in ``directory`` by name, in rule order.

    Only regular files count. ``exclude_names`` are matched (case-sensitive)
    against the file name and ``exclude_dirs`` against folder names between
    ``directory`` and the file. ``pick`` chooses among several matches:

    * ``only`` -- exactly one match is expected; several is an error.
    * ``first_listed`` -- the first in :meth:`pathlib.Path.glob` order (the
      operating system's listing order, which is not sorted).
    * ``oldest_modified`` -- earliest modification time; ties keep listing order.
    * ``first_sorted`` -- first by relative path.

    Raises:
        FileNotFoundError: a required file is missing or ``directory`` is not a folder.
        ValueError: ``only`` matched several files, a capture failed, or a
            placeholder refers to a variable from a missing optional file.
    """
    folder = Path(directory)
    if not folder.is_dir():
        raise FileNotFoundError(f"Recording folder not found: {folder}")
    files: dict[str, Path] = {}
    variables: dict[str, str] = {}
    for rule in definition.files:
        missing = [v for v in _PLACEHOLDER_RE.findall(rule.pattern) if v not in variables]
        if missing:
            raise ValueError(f"file rule '{rule.role}' needs '{{{missing[0]}}}', which no located file provided")
        candidates = _candidates(folder, rule, variables)
        if not candidates:
            if rule.required:
                raise FileNotFoundError(
                    f"No file for '{rule.role}' matching {rule.pattern!r} in {folder}"
                    + (f" (pattern after substitution uses {variables})" if variables else "")
                )
            continue
        chosen = _pick(rule, candidates, folder)
        files[rule.role] = chosen
        if rule.capture is not None:
            variables[rule.capture.variable] = rule.capture.apply(chosen.stem)
    return ResolvedFiles(files=files, variables=variables)


# ─────────────────────────────────────────────────────────────────────────────
# JSON Schema (documentation and GUI forms)
# ─────────────────────────────────────────────────────────────────────────────

# ECMA-262 and Python ``re`` agree on this expression.
_GLOB_REGEX = (
    r"^(?![/~])(?![A-Za-z]:)(?!.*\\)(?!.*\x00)(?!(?:.*/)?\.{1,2}(?:/|$))(?!.*//)(?!.*/$)"
    r"(?!(?:.*/)?(?:[^/]*[^/]\*\*|\*\*[^/])).+$"
)


def definition_json_schema() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) for ``ace-loader/1``.

    The schema describes structure. Some rules need context and are enforced
    only by :func:`validate_definition`: neo IO names and their arguments,
    role and placeholder cross-references, backend/time/channel combinations,
    machine paths inside reader arguments, and the file-name rule.
    """
    glob = {"$ref": "#/$defs/glob"}
    role_ref = {"type": "string", "pattern": ROLE_PATTERN}
    scalar = {"type": ["string", "number", "boolean", "null"]}
    scalar_map = {
        "type": "object",
        "propertyNames": {"pattern": r"^[A-Za-z_][A-Za-z0-9_]*$"},
        "additionalProperties": scalar,
    }
    glob_list = {"type": "array", "items": glob, "uniqueItems": True}
    names = {"type": "array", "items": {"type": "string", "minLength": 1}, "uniqueItems": True}

    def closed(properties: dict[str, Any], required: list[str], **extra: Any) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
            **extra,
        }

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/emelon8/ACE-NeuroTools/schemas/ace-loader-1.json",
        "title": "ACE-NeuroTools ephys loader definition",
        "description": (
            "Describes an ephys acquisition system as configuration. Stored as "
            "<project>/loaders/<name>.json; the file name must equal 'name'."
        ),
        **closed(
            {
                "schema": {"const": SCHEMA},
                "name": {"type": "string", "pattern": NAME_PATTERN, "maxLength": NAME_MAX_LENGTH},
                "label": {"type": "string", "minLength": 1, "pattern": r"\S"},
                "description": {"type": "string"},
                "modality": {"const": "ephys"},
                "detect": {"$ref": "#/$defs/detect"},
                "reader": {"oneOf": [{"$ref": "#/$defs/neo_reader"}, {"$ref": "#/$defs/raw_binary_reader"}]},
                "time": {
                    "oneOf": [
                        {"$ref": "#/$defs/time_reader"},
                        {"$ref": "#/$defs/time_clock_file"},
                        {"$ref": "#/$defs/time_sample_index"},
                    ]
                },
                "channels": {"$ref": "#/$defs/channels"},
                "sync": {
                    "oneOf": [
                        {"$ref": "#/$defs/sync_event_labels"},
                        {"$ref": "#/$defs/sync_digital_threshold"},
                        {"$ref": "#/$defs/sync_shared_clock"},
                    ]
                },
            },
            sorted(FIELDS["definition"][0]),
        ),
        "$defs": {
            "glob": {
                "type": "string",
                "description": "Glob relative to the recording folder, '/' separated.",
                "pattern": _GLOB_REGEX,
            },
            "detect": closed(
                {"all_of": glob_list, "any_of": glob_list, "none_of": glob_list},
                [],
                anyOf=[
                    {"required": ["all_of"], "properties": {"all_of": {"minItems": 1}}},
                    {"required": ["any_of"], "properties": {"any_of": {"minItems": 1}}},
                ],
            ),
            "file": closed(
                {
                    "role": {"type": "string", "pattern": ROLE_PATTERN},
                    "pattern": glob,
                    "exclude_names": {"type": "array", "items": {"type": "string", "pattern": r"^[^/\\]+$"},
                                      "uniqueItems": True},
                    "exclude_dirs": {"type": "array",
                                     "items": {"type": "string", "pattern": r"^(?!\.{1,2}$)[^/\\]+$"},
                                     "uniqueItems": True},
                    "pick": {"enum": list(PICK_MODES), "default": "only"},
                    "required": {"type": "boolean", "default": True},
                    "capture": closed(
                        {
                            "variable": {"type": "string", "pattern": VARIABLE_PATTERN, "not": {"const": "index"}},
                            "split": {"type": "string", "minLength": 1},
                            "part": {"type": "integer"},
                        },
                        ["part", "split", "variable"],
                    ),
                },
                ["pattern", "role"],
            ),
            "files": {"type": "array", "items": {"$ref": "#/$defs/file"}},
            "neo_reader": closed(
                {
                    "backend": {"const": "neo"},
                    "io": {"type": "string", "description": "A class name from neo.io.iolist."},
                    "path_argument": {"type": "string", "pattern": r"^[A-Za-z_][A-Za-z0-9_]*$"},
                    "path_from": {
                        "oneOf": [
                            closed({"source": {"const": "recording_folder"}}, ["source"]),
                            closed({"source": {"const": "file"}, "file": role_ref}, ["file", "source"]),
                            closed({"source": {"const": "file_parent"}, "file": role_ref}, ["file", "source"]),
                        ]
                    },
                    "files": {"$ref": "#/$defs/files"},
                    "args": scalar_map,
                    "read_block": scalar_map,
                },
                sorted(FIELDS["reader.neo"][0]),
            ),
            "raw_binary_reader": closed(
                {
                    "backend": {"const": "raw_binary"},
                    "files": {"$ref": "#/$defs/files", "minItems": 1},
                    "signal_file": role_ref,
                    "dtype": {"enum": list(SAMPLE_DTYPES)},
                    "channel_count": {"type": "integer", "minimum": 1},
                    "gain": {"type": "number", "not": {"const": 0}, "default": 1.0},
                    "offset": {"type": "number", "default": 0.0},
                    "byte_offset": {"type": "integer", "minimum": 0, "default": 0},
                    "output_dtype": {"enum": list(OUTPUT_DTYPES), "default": "float32"},
                },
                sorted(FIELDS["reader.raw_binary"][0]),
            ),
            "time_reader": closed({"source": {"const": "reader"}}, ["source"]),
            "time_clock_file": closed(
                {
                    "source": {"const": "clock_file"},
                    "clock_file": role_ref,
                    "clock_dtype": {"enum": list(CLOCK_DTYPES)},
                    "ticks_per_second": {
                        "oneOf": [
                            {"type": "number", "exclusiveMinimum": 0},
                            closed(
                                {
                                    "csv_file": role_ref,
                                    "column": {"type": "integer", "minimum": 0},
                                    "header_rows": {"type": "integer", "minimum": 0, "default": 0},
                                },
                                ["column", "csv_file"],
                            ),
                        ]
                    },
                    "effective_rate": closed(
                        {
                            "method": {"enum": list(RATE_METHODS)},
                            "first_samples": {"type": "integer", "minimum": 2},
                        },
                        ["first_samples", "method"],
                    ),
                },
                sorted(FIELDS["time.clock_file"][0]),
            ),
            "time_sample_index": closed(
                {"source": {"const": "sample_index"}, "sampling_rate_hz": {"type": "number", "exclusiveMinimum": 0}},
                ["sampling_rate_hz", "source"],
            ),
            "channels": closed(
                {
                    "source": {"enum": list(CHANNEL_SOURCES)},
                    "default": {"enum": list(CHANNEL_DEFAULTS)},
                    "template": {"type": "string", "pattern": r"\{index\}"},
                    "select_by_index": {"type": "boolean", "default": False},
                },
                ["default", "source"],
            ),
            "sync_event_labels": closed(
                {"strategy": {"const": "event_labels"}, "labels": {**names, "minItems": 1}},
                ["labels", "strategy"],
            ),
            "sync_digital_threshold": closed(
                {
                    "strategy": {"const": "digital_threshold"},
                    "channel": {"type": "string", "minLength": 1},
                    "threshold": {"type": "number"},
                    "edge": {"enum": list(EDGES), "default": "rising"},
                },
                ["channel", "strategy", "threshold"],
            ),
            "sync_shared_clock": closed({"strategy": {"const": "shared_clock"}}, ["strategy"]),
        },
    }
