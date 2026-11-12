---
status: proposed
---

# Describe ephys loaders as JSON definitions in shared code

PR 151 adds `src/aceneurotools/shared/loader_definitions.py` and its two
starting templates. `shared/` helpers outside the non-core list are core under
AGENTS.md, so this proposal records the decision for maintainer review. The
code is included in PR 151 so it can be reviewed in place. Merging PR 151 is
the approval; until then this ADR stays `proposed`.

## Context

Adding an acquisition system today means writing a Python `EphysDataManager`
subclass. Labs that only need to point an existing neo reader at their files,
or read one interleaved binary file, have no configuration-only route.

Definitions are user-editable settings files, and they are read by the CLI
(`ace-neuro loaders`) and by the workbench. To make those two agree, parsing,
validation and folder matching must live in one place:

- `shared/loader_definitions.py:1230`: `check_definition_text` parses text from
  the workbench. `:1258`: `load_definition` reads files as `utf-8-sig`.
  Without the initial-BOM strip at `:1230`, a BOM-prefixed file read by the CLI
  is valid but the same text pasted in the workbench is not.
- `gui/loaders.py:143` decodes bytes strictly. `:238` and `:326` strip one
  initial BOM before showing or saving the text, but `save` (`:313`) computes
  digests and backups from the original bytes, so conflict checks are unchanged.
- `cli.py:525`–`:538` define the built-in loader names that project definitions
  may not reuse. `ace-neuro loaders list` and `detect` (`cli.py:553`, `:626`)
  and the workbench (`gui/loaders.py:152`) pass them to
  `load_project_definitions`; `validate` checks each file against them
  (`cli.py:578`).

Loading channels from a definition, and choosing between several matching
loaders, is a separate change to the ephys data managers proposed in ADR 0008.
ADR 0008 is under review on its own branch and is not part of this PR.

## Decision

Add `aceneurotools.shared.loader_definitions` (schema `ace-loader/1`):

- **Parsing and validation.** Strict JSON: duplicate keys, `NaN` and
  `Infinity` are rejected, and one initial UTF-8 BOM is ignored. Every
  problem is reported with its location. Unknown keys are refused, not kept.
- **Portability.** Every file pattern is a relative glob under the recording
  folder, with at most 32 `/`-separated segments (deeper patterns make
  `pathlib` raise `RecursionError`). No reader argument may be a machine path. A definition name is
  kebab-case, at most 64 characters, and not a Windows device name (`con`,
  `prn`, `aux`, `nul`, `com0`–`com9`, `lpt0`–`lpt9`).
- **Reader safety.** A definition may name only classes in `neo.io.iolist`.
  `PickleIO` and `NeurosharectypesIO` are refused. Neither `args` nor
  `read_block` may set an argument whose name contains `file`, `dir`, `path`,
  `folder`, `cache`, `dll`, `url` or `override`, because the loader alone
  chooses which files a reader opens and neo's cache is unpickled. IOs that take
  `**kwargs` only to pass them to their rawio class (for example `BlackrockIO`,
  `Spike2IO`) are checked against that class's parameters. A reader that has a
  `mode` argument must open read-only: `ro` for `NixIO`, `r` for `NWBIO`, and
  `r` or `ro` otherwise.
- **Matching.** `definition_matches`, `matching_files` and `resolve_files` look
  at file names only. They never open a recording.
- **Names.** Built-in loader names (`neuralynx`, `rhs2116`, and their
  `...datamanager` forms) are refused for project definitions by both the CLI
  and the workbench. This is the strict choice: it can be relaxed later
  without breaking saved files.

The code is the file in PR 151. Review changes to that file, exactly:

Round 1 (reader arguments, `NWBIO` mode, Windows device names):

```diff
diff --git a/src/aceneurotools/shared/loader_definitions.py b/src/aceneurotools/shared/loader_definitions.py
index 4d40b18..593f200 100644
--- a/src/aceneurotools/shared/loader_definitions.py
+++ b/src/aceneurotools/shared/loader_definitions.py
@@ -100,12 +100,12 @@ CLOCK_DTYPES = ("uint32", "uint64", "int32", "int64", "float64")
 OUTPUT_DTYPES = ("float32", "float64")
 READ_ONLY_MODES = ("r", "ro")
 #: Read-only ``mode`` values for neo IOs that accept only some of READ_ONLY_MODES.
-READ_ONLY_MODES_BY_IO: Mapping[str, tuple[str, ...]] = {"NixIO": ("ro",)}
+READ_ONLY_MODES_BY_IO: Mapping[str, tuple[str, ...]] = {"NixIO": ("ro",), "NWBIO": ("r",)}
 
 #: neo reader arguments a definition may not set: they name files, folders or
 #: caches (neo's cache is unpickled with joblib), and the loader alone decides
 #: which files a reader opens.
-_DENIED_ARG_RE = re.compile(r"file|dir|path|folder|cache|dll|url", re.IGNORECASE)
+_DENIED_ARG_RE = re.compile(r"file|dir|path|folder|cache|dll|url|override", re.IGNORECASE)
 
 #: neo IO classes a definition may not name, with the reason.
 DENIED_NEO_IOS: Mapping[str, str] = {
@@ -115,11 +115,14 @@ DENIED_NEO_IOS: Mapping[str, str] = {
 
 NAME_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
 NAME_MAX_LENGTH = 64
+#: Names Windows reserves for devices: ``loaders/nul.json`` is not an ordinary file there.
+WINDOWS_DEVICE_NAME_PATTERN = r"^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])$"
 ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"
 VARIABLE_PATTERN = r"^[a-z][a-z0-9_]*$"
 INDEX_PLACEHOLDER = "{index}"
 
 _NAME_RE = re.compile(NAME_PATTERN)
+_WINDOWS_DEVICE_RE = re.compile(WINDOWS_DEVICE_NAME_PATTERN)
 _ROLE_RE = re.compile(ROLE_PATTERN)
 _VARIABLE_RE = re.compile(VARIABLE_PATTERN)
 _PLACEHOLDER_RE = re.compile(r"\{([^{}]*)\}")
@@ -544,6 +547,24 @@ def _parameters(func: Any) -> tuple[set[str], bool]:
     return names, var_kw
 
 
+def _init_parameters(cls: Any) -> tuple[set[str], bool]:
+    """Named ``__init__`` parameters of a neo IO and whether it accepts other names.
+
+    IOs such as ``BlackrockIO`` take ``**kwargs`` only to pass them to the rawio
+    class they inherit from, so that class's parameters are the real ones.
+    """
+    names, var_kw = _parameters(cls.__init__)
+    if not var_kw:
+        return names, var_kw
+    from neo.rawio.baserawio import BaseRawIO  # type: ignore
+
+    for base in cls.__mro__[1:]:
+        if "__init__" in vars(base) and isinstance(base, type) and issubclass(base, BaseRawIO):
+            base_names, base_var_kw = _parameters(base.__init__)
+            return names | base_names, base_var_kw
+    return names, var_kw
+
+
 def _parameter_default(func: Any, name: str) -> Any:
     """Default value of parameter ``name`` of ``func`` (None if unknown or none)."""
     try:
@@ -712,6 +733,8 @@ class _Validator:
                     self.add("name", f"must be at most {NAME_MAX_LENGTH} characters")
                 elif not _NAME_RE.fullmatch(name):
                     self.add("name", "must be kebab-case: lowercase letters and digits separated by '-'")
+                elif _WINDOWS_DEVICE_RE.fullmatch(name):
+                    self.add("name", f"'{name}' is a reserved device name on Windows; choose another name")
         if "label" in data:
             self.text(data["label"], "label")
         if "description" in data:
@@ -897,7 +920,7 @@ class _Validator:
             self.add("reader.io", f"'{io_name}' is not a neo IO in neo.io.iolist{extra}")
             return
         cls = _neo_io_class(io_name)
-        init_params, init_var_kw = _parameters(cls.__init__)
+        init_params, init_var_kw = _init_parameters(cls)
         if path_arg is not None and _IDENTIFIER_RE.fullmatch(path_arg) and path_arg not in init_params:
             self.add(
                 "reader.path_argument",
@@ -935,6 +958,12 @@ class _Validator:
         for key in block_args:
             if not block_var_kw and key not in block_params:
                 self.add(f"reader.read_block.{key}", f"{io_name}.read_block has no argument '{key}'")
+            elif _DENIED_ARG_RE.search(key):
+                self.add(
+                    f"reader.read_block.{key}",
+                    "cannot be set in a definition: it names files, folders or a cache, "
+                    "and the loader alone chooses which files a reader opens",
+                )
 
     def time(self, value: object, backend: str | None, roles: Mapping[str, object]) -> None:
         if not isinstance(value, dict):
@@ -1481,7 +1510,12 @@ def definition_json_schema() -> dict[str, Any]:
         **closed(
             {
                 "schema": {"const": SCHEMA},
-                "name": {"type": "string", "pattern": NAME_PATTERN, "maxLength": NAME_MAX_LENGTH},
+                "name": {
+                    "type": "string",
+                    "pattern": NAME_PATTERN,
+                    "maxLength": NAME_MAX_LENGTH,
+                    "not": {"pattern": WINDOWS_DEVICE_NAME_PATTERN},
+                },
                 "label": {"type": "string", "minLength": 1, "pattern": r"\S"},
                 "description": {"type": "string"},
                 "modality": {"const": "ephys"},
```

Round 2 (pattern depth):

```diff
diff --git a/src/aceneurotools/shared/loader_definitions.py b/src/aceneurotools/shared/loader_definitions.py
index 593f200..7a02da6 100644
--- a/src/aceneurotools/shared/loader_definitions.py
+++ b/src/aceneurotools/shared/loader_definitions.py
@@ -120,6 +120,9 @@ WINDOWS_DEVICE_NAME_PATTERN = r"^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])$"
 ROLE_PATTERN = r"^[a-z][a-z0-9_]*$"
 VARIABLE_PATTERN = r"^[a-z][a-z0-9_]*$"
 INDEX_PLACEHOLDER = "{index}"
+#: Most '/'-separated segments a pattern may have. pathlib.Path.glob builds one
+#: nested selector per segment, so a few hundred raise RecursionError.
+MAX_GLOB_SEGMENTS = 32
 
 _NAME_RE = re.compile(NAME_PATTERN)
 _WINDOWS_DEVICE_RE = re.compile(WINDOWS_DEVICE_NAME_PATTERN)
@@ -468,8 +471,8 @@ def check_relative_glob(pattern: object) -> str | None:
 
     Patterns are evaluated with :meth:`pathlib.Path.glob` under the recording
     folder. They must use ``/`` separators and may not be absolute, start with
-    ``~`` or a drive letter, contain backslashes, or have empty, ``.`` or
-    ``..`` segments.
+    ``~`` or a drive letter, contain backslashes, have empty, ``.`` or ``..``
+    segments, or have more than :data:`MAX_GLOB_SEGMENTS` segments.
     """
     if not isinstance(pattern, str):
         return "must be a string"
@@ -492,6 +495,8 @@ def check_relative_glob(pattern: object) -> str | None:
         return "must not contain '.' segments"
     if "" in segments:
         return "must not contain empty segments ('//' or a trailing '/')"
+    if len(segments) > MAX_GLOB_SEGMENTS:
+        return f"must have at most {MAX_GLOB_SEGMENTS} '/'-separated segments"
     if any("**" in seg and seg != "**" for seg in segments):
         return "'**' must be a whole segment, as in 'sub/**/file.ext'"
     return None
@@ -1467,7 +1472,7 @@ def resolve_files(definition: LoaderDefinition, directory: str | Path) -> Resolv
 # the control-character lookahead rejects them before ``$`` could differ.
 _GLOB_REGEX = (
     r"^(?![/~])(?![A-Za-z]:)(?!.*\\)(?!.*[\x00-\x1f\x7f])(?!(?:.*/)?\.{1,2}(?:/|$))(?!.*//)(?!.*/$)"
-    r"(?!(?:.*/)?(?:[^/]*[^/]\*\*|\*\*[^/])).+$"
+    r"(?!(?:.*/)?(?:[^/]*[^/]\*\*|\*\*[^/]))(?!(?:[^/]*/){32}).+$"
 )
 
 
```

## Effect on callers and results

- **Analyses:** no change. No pipeline or ephys-manager file changes.
  `EphysDataManager.create()` still uses only the built-in Python loaders, and
  nothing here reads signal data. Numerical results do not change.
- **CLI:** new `ace-neuro loaders list|validate|detect`. Existing invocations
  parse as before.
- **Python:** new public API, rendered in the Shared Utils API page.

## Tests

`tests/test_loader_definitions.py` covers parsing, every validation rule (with
regressions for override and `read_block` arguments, `**kwargs` IOs, `NWBIO`
modes, Windows device names and pattern depth), schema and validator agreement, and the two
reference definitions in `tests/data/loaders/`, which reproduce the built-in
loaders' detection and file search. `tests/test_cli_loaders.py` and
`tests/test_gui_loaders.py` cover the commands and routes, including a test
that the CLI and the workbench reserve the same names.

## Risks and alternatives

- **The deny list is by argument name.** A future neo reader could take a
  file under a name the pattern misses. Mitigation: the pattern is broad, and
  ADR 0008's loader passes the path itself. An explicit per-reader allow-list
  is the stricter alternative, but it would need updating for every neo release.
- **Reserving built-in names** blocks a project from overriding a built-in
  loader by name. ADR 0008 can relax this once an `ephys loader` column makes
  the choice explicit.
- **Alternative: keep definitions in GUI code only.** Rejected. The CLI and
  the workbench would drift, against ADR 0001.
