# ACENeuroTools development audit — 2026-09-16

Baseline: `2fd7cac` on `proj-comenius`. Implementation branch:
`feat/aceneurotools-workbench`. Repository initially clean and synchronized.

## Findings

| Area | Evidence at baseline | Status |
| --- | --- | --- |
| EVC | `src/aceneurotools/evc/api.py`, porcelain, store, journal, manifests, CSV bridge | Functional Python backend; frozen typed contract |
| Machine interface | `python -m aceneurotools.evc … --json` | Implemented; useful for automation |
| GUI | Comenius plans; no research workspace application | This branch adds an independent `gui/` application |
| Parameters | D05 accepted; JSON schemas + CSV round-trip bridge | JSON authority implemented for experiment/CNMF-E; lab/stats transition incomplete |
| Pipelines | Existing miniscope, ephys, multimodal, stats; opt-in RunRecorder | Existing compute retained; GUI job orchestration is a separate feature |
| Recovery | Dirty-state safety snapshots; forward-only history | Suitable for GUI adapter, with explicit restore review |
| Sharing | LocalDirectoryRemote; D18/D19 open | No cloud synchronization promise |
| Curation | PR #68 `gui-updates`, open and conflicting on audit date | Existing component selector must be integrated separately |
| CI | Fast tests only on main/PR-to-main; lint advisory | Workbench requires its own branch CI |
| Product decisions | D03 and most planning gates still open | User authorizes an autonomous IDE-style implementation; no issue silently closed |

## Scope of this implementation

A local research workbench over existing EVC workspaces: workspace selection,
JSON editing and validation, change inspection, revision recording, history,
comparison, comments, safe restore, journal recovery, result manifests and
integrity verification. A synthetic example exercises real EVC persistence.

The GUI lives outside `src/aceneurotools/evc/`. Its development dependencies are
isolated from the CaImAn environment. Existing researcher datasets are not demo
fixtures. The workbench does not claim to execute, cancel, or curate scientific
pipelines, infer recording formats, synchronize to Box, or host multiple users.

## Audit method

Read collective memory, domain vocabulary, Comenius decisions, EVC implementation
and tests; verify repository state, GitHub issue/PR status and current component
licenses; run the existing fast suite and independent GUI checks. Known older
scientific bugs are assessed separately from the GUI; passing EVC tests does not
validate scientific outputs. Detailed measured results are appended at completion.
