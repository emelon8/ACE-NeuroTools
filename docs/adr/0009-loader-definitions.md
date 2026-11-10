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

- `shared/loader_definitions.py:1225`: `check_definition_text` parses text from
  the workbench. `:1253`: `load_definition` reads files as `utf-8-sig`.
  Without the initial-BOM strip at `:1225`, a BOM-prefixed file read by the CLI
  is valid but the same text pasted in the workbench is not.
- `gui/loaders.py:143` decodes bytes strictly. `:235` and `:323` strip one
  initial BOM before showing or saving the text, but `save` (`:310`) computes
  digests and backups from the original bytes, so conflict checks are unchanged.
- `cli.py:525`–`:538` define the built-in loader names that project definitions
  may not reuse. The CLI (`:553`, `:626`, and `validate`) and the workbench
  (`gui/loaders.py:152`) both pass them to `load_project_definitions`.

Loading channels from a definition, and choosing between several matching
loaders, is a separate change to the ephys data managers proposed in ADR 0008.
ADR 0008 is under review on its own branch and is not part of this PR.

## Decision

Add `aceneurotools.shared.loader_definitions` (schema `ace-loader/1`):

- **Parsing and validation.** Strict JSON: duplicate keys, `NaN` and
  `Infinity` are rejected, and one initial UTF-8 BOM is ignored. Every
  problem is reported with its location. Unknown keys are refused, not kept.
- **Portability.** Every file pattern is a relative glob under the recording
  folder. No reader argument may be a machine path. A definition name is
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

The code is the file in PR 151. Its review-round-1 changes to that file were:

```diff
-READ_ONLY_MODES_BY_IO: Mapping[str, tuple[str, ...]] = {"NixIO": ("ro",)}
+READ_ONLY_MODES_BY_IO: Mapping[str, tuple[str, ...]] = {"NixIO": ("ro",), "NWBIO": ("r",)}
-_DENIED_ARG_RE = re.compile(r"file|dir|path|folder|cache|dll|url", re.IGNORECASE)
+_DENIED_ARG_RE = re.compile(r"file|dir|path|folder|cache|dll|url|override", re.IGNORECASE)
+WINDOWS_DEVICE_NAME_PATTERN = r"^(?:con|prn|aux|nul|com[0-9]|lpt[0-9])$"
+_WINDOWS_DEVICE_RE = re.compile(WINDOWS_DEVICE_NAME_PATTERN)
+def _init_parameters(cls: Any) -> tuple[set[str], bool]:
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
+                elif _WINDOWS_DEVICE_RE.fullmatch(name):
+                    self.add("name", f"'{name}' is a reserved device name on Windows; choose another name")
-        init_params, init_var_kw = _parameters(cls.__init__)
+        init_params, init_var_kw = _init_parameters(cls)
+            elif _DENIED_ARG_RE.search(key):
+                self.add(f"reader.read_block.{key}", "cannot be set in a definition: ...")
+                    "not": {"pattern": WINDOWS_DEVICE_NAME_PATTERN},
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
modes and Windows device names), schema and validator agreement, and the two
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
