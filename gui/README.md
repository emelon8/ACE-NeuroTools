# ACENeuroTools Workbench

A local researcher GUI built on **Lumino** (JupyterLab's IDE widgets), **Monaco**
(VS Code's editor), and **VS Code Codicons**. VS Code-inspired layout with a
viridis theme: activity bar, explorer, draggable editor tabs, resizable splits,
command palette, output panel and status bar. No generated imagery or AI UI.

The application is independent of `src/aceneurotools/evc/`; its Python adapter
calls the existing EVC API. It edits real parameter documents and records real
experiment history. [Development audit](docs/AUDIT.md) ·
[Architecture](docs/ARCHITECTURE.md) · [Notices](THIRD_PARTY_NOTICES.md).

## Install from this checkout

Requires Python 3.10+ and Node 22.12+ (Node 24 LTS recommended). From the repository
root, using [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.10 gui/.venv
uv pip install --python gui/.venv/bin/python -r gui/server/requirements-dev.lock
uv pip install --python gui/.venv/bin/python --no-deps -e . -e gui/server
npm --prefix gui ci
npm --prefix gui run build
```

The core package is installed with `--no-deps` intentionally: EVC is pure Python
and the GUI does not execute scientific pipelines. This keeps CaImAn and the
existing scientific environment separate. Do not use this GUI environment to
run a scientific pipeline without installing its full scientific dependencies.
On Windows substitute `gui/.venv/Scripts/python.exe` for the Python path;
Windows packaging and native file dialogs have not been validated.

## Open the synthetic example

```bash
python3 gui/launch.py --demo gui/.demo
```

This opens a browser tab and keeps a local server running. Stop it with Ctrl+C.
The example includes two experiments, three real EVC revisions per experiment,
parameter documents and a manifest-linked CSV with synthetic traces. It does
not contain acquired data or pretend that a scientific analysis ran. Reopening
the demo preserves your edits. Use another empty directory for a fresh example.

## Open existing experiments

```bash
python3 gui/launch.py --workspace /absolute/path/to/experiment
python3 gui/launch.py --workspace /path/to/experiment-a --workspace /path/to/experiment-b
python3 gui/launch.py --project /path/to/parent-containing-experiments
```

An experiment must already contain `.evc/`. `--project` discovers immediate child
EVC workspaces only; it does not reorganize or copy recordings. Use the explorer
selector to switch between registered experiments. An empty workspace can be
initialized using the existing CLI:

```bash
gui/.venv/bin/python -m aceneurotools.evc --dir /path/to/new-experiment init --workspace
```

Create parameter JSON documents under `parameters/`, or use the existing
`import_experiment` Python API to migrate CSV rows, then refresh the GUI. The
GUI does not silently import or write back legacy CSV files.

Optional launcher flags: `--port 8767`, `--no-browser`,
`--author 'Researcher Name <researcher@example.org>'`. History defaults to EVC's
local OS identity when no author is supplied. Git source commits and experiment
revisions are different histories.

## Daily workflow

1. Open `analysis.cnmfe.json` or `experiment.json` in the explorer.
2. Edit in the typed **Parameters** form or the full **JSON** editor. JSON schema
   validation runs locally; the service validates again before writing.
3. **Save** (`Cmd/Ctrl+S`) writes the document. A content hash prevents stale
   buffers from overwriting newer disk edits. Reload after resolving a conflict.
4. Open **Experiment changes**, review the saved key-level differences, write a
   message, and **Record revision**. Unsaved editor buffers must be resolved.
5. Use **History** to compare revisions side by side or add research comments.
6. **Restore revision** asks for review. EVC preserves dirty disk state in a
   safety snapshot and never rewinds HEAD. Record a new revision to retain it.
   The **Recovery journal** can restore those safety snapshots too.
7. In **Results**, inspect manifest provenance, **Verify integrity**, and click a
   text/JSON/CSV/TSV artifact for a preview. Numeric CSV data gets a viridis plot.

Tabs can be dragged into split editors using Lumino's docking targets.
`Cmd/Ctrl+Shift+P` opens the command palette; `Cmd/Ctrl+B` toggles the explorer;
`Cmd/Ctrl+J` toggles output; `Cmd/Ctrl+Shift+G` opens experiment changes.

## Boundaries

- The launcher binds to 127.0.0.1. Open its printed session URL if the browser
  does not open automatically. Tokens are removed from the URL after load and
  stored in that browser tab; a server restart requires its new URL.
- Scientific pipeline execution, cancellation, curation, remote sync, extension
  installation and VS Code extensions are outside this first workbench scope.
- `.evc/ignore` controls tracking, including during status snapshots. The existing
  defaults do **not** ignore every raw recording format. Keep large recordings
  outside tracked paths and review ignore rules before opening a legacy workspace.
- Workbench saves and mutations are serialized in one server process; external
  CLI writers do not share its lock. Avoid concurrent mutation across processes.
- Parameters and preview artifacts are limited to 2 MiB. CSV previews show at
  most 500 rows and five numeric channels; full artifacts remain untouched.
- Result manifests pointing outside the selected workspace are reported as
  outside scope; use the EVC CLI to verify them. No arbitrary path is exposed.
- Tested on macOS with Chromium at 1440×960 and 1024×768. This is a desktop web
  workbench, not a mobile app or a packaged native installer.

## Development checks

```bash
npm --prefix gui run build
npm --prefix gui test
cd gui && npx playwright install chromium && npm run test:e2e
# From repository root:
gui/.venv/bin/python -m pytest gui/server/tests -q
gui/.venv/bin/ruff check gui/server gui/tests/serve.py gui/launch.py
gui/.venv/bin/ruff format --check gui/server gui/tests/serve.py gui/launch.py
```

Tests create temporary synthetic workspaces. The browser test reset endpoint
exists only in `tests/serve.py`, never in the production service. For frontend iteration, rebuild with `npm run build` and reload the browser.
The local launcher serves the editor, workers and API from the same origin.
