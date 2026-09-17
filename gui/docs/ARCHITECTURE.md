# Workbench architecture

User direction, 2026-09-16: build a separate GUI autonomously, closely following
VS Code layout, using open-source IDE foundations and viridis colors. This
records the implementation choice under that authorization; it does not close
D03 or imply consensus on all Comenius deployment/product decisions.

## Open-source foundations

- [Lumino](https://github.com/jupyterlab/lumino): JupyterLab's BSD-3-Clause
  widget, split-panel, docking and command-palette infrastructure.
- [Monaco](https://github.com/microsoft/monaco-editor): VS Code's MIT editor;
  local JSON workers, schema validation, undo and side-by-side differences.
- [Codicons](https://github.com/microsoft/vscode-codicons): VS Code icons,
  CC-BY-4.0 artwork and MIT supporting code. Attribution ships with the GUI.

Use real IDE components, not a dashboard styled to resemble an IDE. Layout:
menu/title bar, narrow activity bar, resizable explorer, dockable editor tabs,
resizable output panel, status bar. Neutral dark surfaces and fine separators;
viridis purple/blue/teal/green/yellow for active state and scientific traces.
No generated imagery, chat surface, ornamental cards or glow effects.

## Typography

Use native desktop interface fonts: the macOS system font, Segoe UI on Windows,
and Ubuntu/Noto Sans where installed on Linux. Main controls and tabs use regular
13 px text, with 12 px secondary text and compact section labels. Avoid decorative
letter spacing and monospace status badges.

Code, parameter names, revision identifiers and logs use installed editor fonts:
Menlo, Monaco, Consolas, Liberation Mono, then DejaVu Sans Mono before the generic
monospace fallback. Monaco reads the same CSS font stack as the surrounding UI;
code uses 13 px text and logs/data use 12 px, with ligatures disabled. No text
font downloads or bundled proprietary fonts are required.

## Boundaries

`gui/src` → same-origin `/api` → `gui/server/ace_workbench` →
`aceneurotools.evc.api`. The adapter returns JSON representations of the frozen
EVC dataclasses. EVC remains authoritative for history and recovery. Monaco
workers and Codicons fonts are bundled locally; text uses installed system fonts.
No runtime CDN or telemetry.

The launcher binds only to 127.0.0.1. It exposes only explicitly configured roots,
requires a per-launch capability header, rejects foreign origins and unknown
hosts, serializes mutations, confines editable paths to parameter JSON, and
requires file-content hashes to avoid overwriting concurrent edits. It is a
single-user local app, not a hardened hosted service. External CLI writes cannot
participate in the server lock; reload on conflicts and avoid simultaneous EVC
mutations from multiple processes.

Workspaces are selected by explicit local paths at launch. An optional project
root discovers immediate child EVC workspaces, without relocating recordings.
The layout and discovery are an adapter over the existing provisional D06
contract, not a new project file format. Restore presents its target and preserves
dirty disk state through EVC; unsaved editor buffers must be resolved first.

## Recording workflow

The object-oriented workflow is isolated in `gui/src/workflow/` and
`gui/server/ace_workbench/workflow/`. Browser enumeration/upload, conditional
question rendering and run monitoring are separate from backend detector,
pipeline, question, storage, preflight and worker strategies. The scientific
worker consumes a frozen configuration and private input copy; the server owns
EVC finalization. See [the workflow contract and extension guide](WORKFLOW.md).

## Delivery

Incremental commits and pushes on `feat/aceneurotools-workbench`, using the
existing Eli Keldsen Git identity and `elijah-keldsen` GitHub authentication.
No AI co-author trailers. Collective memory remains local per its existing rule;
public architecture, audit and verification evidence live here.
