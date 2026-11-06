# Experiment workbench (`ace-gui`) — contributor notes

The GUI wraps the analysis library; it does not change it. GUI code calls the
public pipeline APIs and command-line entry points in `aceneurotools.pipelines`
and the analysis packages, and reads the same CSV settings and defaults as the
CLI ([ADR 0001](../../../docs/adr/0001-shared-gui-cli-capabilities.md)). A change
that needs different scientific behavior belongs in those packages, reviewed on
its own, not in a GUI-only copy.

User documentation lives in [docs/gui.md](../../../docs/gui.md).

## Adding a feature

New screens are features, so they do not need another branch in `server.py`
or edits throughout `app.js` and `index.html`.

1. Create `gui/<feature>.py` with a `FEATURE = Feature(...)` declaring its API
   routes, browser scripts/styles and HTML fragments
   ([routes.py](routes.py) documents scopes, locking and responses).
2. Add the module to `ENABLED` in [features.py](features.py), one per line.
3. Create the browser files named in the feature (`gui/<feature>.js`, optional
   `.css`/`.html`). They load after the core scripts and register with
   `aceFeatures` ([features.js](features.js)):
   - `addWorkspaceView` adds a tab beside Overview/Results for the open experiment.
   - `addPage` adds a project-level page to the left navigation.
   - `addUnsaved(check, discard)` makes navigation warn about unsaved drafts;
     `discard` runs if the user leaves anyway. Feature drafts never block the
     experiment's own crop preview or run review.
   - `fragment` loads one of the feature's HTML files into a container.
4. Test routes over HTTP against a real `ProjectServer` (see
   `tests/test_gui_routes.py`), and add parity tests whenever the feature
   reproduces a CLI or pipeline call.

Feature routes keep the server's protections: local origin only, the launch
token on every `/api/` request, JSON POST bodies, and the same 400/409 errors.
Hold the server lock (`locked=True`) only for short CSV or JSON writes.

## Run plans

[run_plan.py](run_plan.py) is the one description of reviewed work for batch
queues, Output script and supercomputer export (single runs from Review & run
still go through `Runs.start`). Build plans from current `Runs.review` results
(`POST /api/run-plan/preview` rejects reviews whose CSVs changed since), never
from unreviewed settings. Each entry keeps the CSV recording values so exporters
can resolve them elsewhere; the plan's project path, file list and generated
commands still use this computer's paths. `invocation()` gives the equivalent
command line (bash and PowerShell quoting) and Python call; when no CLI entry
point exists, `cli` is `None` and `cli_note` says why. Its `notes` explain that
commands read the recording folder directly and warn when a confirmed file
selection limited the GUI run.

## Public repository

Do not add lab-specific values (cluster names, accounts, paths, environment
names) to code, defaults, templates, tests or docs. Ask for site details at the
point of use and keep them out of the repository.
