# Experiment application

A local GUI for browsing projects and editing existing experiment CSVs. It uses
`CSVWorker`, `update_csv_cell`, and `append_row_csv` from the existing tool. All GUI
code lives outside `src`; scripts and scientific processing remain unchanged.
There are no sample-data workspaces or frontend build dependencies.

## Launch

Activate the Python environment you already use for ACE-NeuroTools. From the
repository root:

```bash
python scripts/run_gui.py --project /path/to/project
```

The browser opens at `http://127.0.0.1:8765/`. Omit `--project` to choose a project
in the application. A full path to `experiments.csv` also works. `--no-browser`
leaves browser opening to you; `--port 8780` uses another port. Stop with Ctrl+C.
The GUI needs the existing scientific Python environment, not an empty system Python.

`--project data` opens the repository's actual CSVs: 118 experiments and 114
parameter records. Historical paths and Box IDs are shown as stored; the application
does not authenticate with Box, download recordings, or claim local data readiness.

## Browse and edit

1. Choose **Open project**. The file browser shows folders, CSV files, breadcrumbs,
   Home, and Computer. Open a folder containing `experiments.csv`, then choose
   **Open this project**, or click its `experiments.csv` file. Typing a path is optional.
2. Each opened project appears as an expandable folder containing experiment rows.
   Click anywhere on a row, or focus it and press Enter. Rows identify the subject,
   experiment number, recording date, recording types, and availability of settings.
3. **Experiment details** provides labeled subject, date, recording, treatment,
   channel, and notes fields. Dates use a calendar; recording folders have a chooser;
   Box IDs have links. **Analysis settings** groups timing, cropping, neuron detection,
   motion correction, and other fields. Advanced groups expand when clicked.
4. **Find a field** searches labels, original column names, and current values.
   Unknown lab columns remain editable under **Other fields**. Original keys and
   interpreted reader output are available in **File details**.
5. Choose **Save experiment details** or **Save analysis settings**. Each button saves
   only that section's selected experiment row to its original CSV. Other sections'
   pending changes stay in memory. The application warns before leaving with unsaved
   changes; **Discard changes** discards only the current section's draft.

The experiment number remains fixed so the CSV join stays intact. Duplicate subject,
location, and date columns in the settings file are separate fields under **Recording
details in settings**; they are not automatically synchronized with metadata.

## Missing settings and errors

- Missing settings are marked on the individual rows and listed as clickable subject
  names and experiment numbers above the project. **Missing settings only** filters
  the project lists to affected experiments.
- For a missing settings row, **Add settings for this experiment** prepares a draft;
  saving appends that row. If the file is absent, its columns come from the existing
  parameter template. No example experiment or default values are copied. Blank
  fields remain blank. A malformed settings file must be repaired before writing
  settings; metadata can still be edited without replacing that file.
- Errors persist and name the affected file or field. Validation checks edited
  numbers, dates, boolean choices, numeric Box IDs, and known list/tuple shapes.
  Unchanged legacy values and missing-value markers are preserved.
- Opening a malformed project does not remove previously opened projects. Orphan
  settings records are identified in a disclosure within their project.
- Use **Reload project** after edits made in another application. Unsaved changes
  require a discard confirmation before reload. The GUI checks file hashes and client
  revisions before saving; a stale edit is rejected while the draft remains visible.

## Save behavior

Writes use the existing CSV helpers on a temporary file. The staged CSV is validated
before the original is replaced with `os.replace`. Each save touches one CSV file,
retains column order, unknown fields and other records, and keeps a byte-for-byte copy
of the previous file in `.ace-gui-backups` within the project. The backup location is
shown in **File details** after saving. CSV quoting and record line endings may be
normalized by the existing writers. UTF-8 BOM is preserved. Editing through a CSV
symbolic link is blocked; open the original folder instead.

The in-process server lock serializes GUI writes, and hashes are checked immediately
before replacement. External applications do not share that lock, so simultaneous
writes from those applications should be avoided. Projects are held for this server
session; no new workspace format or saved preferences are introduced.

The server binds to `127.0.0.1`, rejects foreign hosts/origins, and serves only its
own assets and project endpoints. CSV text is inserted as text, never as HTML.
Runs, interactive cropping, neuron selection, setup, and version control remain
outside this slice. See [source findings](../docs/design/csv-viewer-findings.md) for
backend issues recorded without source fixes.

## Validation

```bash
PYTHONPATH=.:src python -m pytest tests/test_gui_csv_projects.py tests/test_gui_server.py tests/test_csv_worker.py
```

Tests cover raw values, stable-number joins, missing/malformed files, selected-row
writes, backups, unknown fields, exact Box IDs, BOM, write failure, new settings,
validation, stale saves, HTTP endpoints, and the unchanged reader.

Browser checks against temporary CSVs covered project grouping, whole-row selection,
calendar editing, folder navigation/picking, Box IDs, notes, real saves, validation,
backups, missing-settings creation, unsaved-change protection, and narrow screens.
The bundled CSVs were only inspected during verification, never edited.
