---
status: proposed
---

# Normalize loader text and integrate reviewed definitions

The GUI save race and BOM handling can be fixed in GUI code. Shared loader
validation and dependency integration still require maintainer approval under
AGENTS.md. This proposal does not authorize applying either change or merging.

## Context

Before integration, `gui/loaders.py:153` decodes UTF-8 without removing a BOM,
while `shared/loader_definitions.py:1094` passes text directly to strict JSON
parsing. Dependency `16431cb` already reads files using UTF-8 with BOM support.
The GUI must agree with that CLI without changing original-byte conflict checks.

## Exact changes proposed

Integrate `feat/loader-definitions` at `16431cb`, preserving both changelog
entries, then main at `ded08fd`. Retain main's app.js and features.js foundation
handlers, register the editor discard callback with addUnsaved, and retain Box
navigation protection through canLeave(). No scientific pipeline files change.

The [complete core integration diff](0009-loader-core.patch) is relative to
repair commit `11393be`, including dependency validation hardening and its five
docstrings. The additional shared BOM change is exactly:

```diff
diff --git a/src/aceneurotools/shared/loader_definitions.py b/src/aceneurotools/shared/loader_definitions.py
index 4266ccc..4d40b18 100644
--- a/src/aceneurotools/shared/loader_definitions.py
+++ b/src/aceneurotools/shared/loader_definitions.py
@@ -1183,6 +1183,7 @@ def _loads(text: str) -> Any:
 def check_definition_text(text: str, *, file_stem: str | None = None) -> tuple[Any, list[DefinitionProblem]]:
     """Parse definition JSON text strictly and validate it, without raising.
 
+    An initial UTF-8 BOM is ignored, as when reading definition files.
     Uses the same strict JSON rules as :func:`load_definition` (no duplicate
     keys, no ``NaN``/``Infinity``). When ``file_stem`` is given, the
     definition's ``name`` must equal it, as for a file ``<file_stem>.json``.
@@ -1192,7 +1193,7 @@ def check_definition_text(text: str, *, file_stem: str | None = None) -> tuple[A
         the text is not JSON; ``problems`` is empty when the definition is valid.
     """
     try:
-        data = _loads(text)
+        data = _loads(text.removeprefix("\ufeff"))
     except (ValueError, RecursionError) as exc:  # json.JSONDecodeError is a ValueError
         return None, [DefinitionProblem("", f"invalid JSON: {exc}")]
     problems = validate_definition(data)

```

The complete integration patch is supplied with the maintainer review artifacts;
it also adds a text-validation regression checking initial BOM removal, interior
BOM preservation and duplicate-key rejection.

## Callers and numerical behavior

CLI file reads keep their BOM acceptance. Python check_definition_text callers
gain the same acceptance. Duplicate-key and finite-number restrictions remain.
No recording is opened and no numerical analysis results change. Dependency
validation rejects unsafe Neo path/cache arguments and validates reader metadata.

## Tests and verification

Browser tests use deferred POST and list responses for edits during save,
editor/project changes, closed editors and stale errors. GUI handler and HTTP
route tests cover BOM open, validate, save, original-byte backups and conflicts.
The proposed shared test checks BOM text parity and strict parsing.

After approval, run the full suite, changed-line coverage, browser syntax checks,
documentation coverage, links and strict docs build on the integrated branch.
A sandbox socket failure must be reported as a restriction, not a suite pass.

## Risks and alternatives

Remove exactly one initial marker; preserve embedded characters. Digests and
backups continue using original bytes. GUI-only normalization is implemented
now; leaving shared validation inconsistent is a temporary alternative. Merging
only the older dependency would omit reviewed validation hardening and docs.
