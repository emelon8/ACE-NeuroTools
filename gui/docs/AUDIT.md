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

## Completed workbench status

The implemented workbench now provides an authenticated local launcher, explicit
multi-workspace selection, a real Lumino docking shell, Monaco JSON editing and
schema diagnostics, typed parameter forms, atomic ETag-guarded saves, EVC change
review and revision recording, side-by-side comparison, comments, reviewed
restore, safety-snapshot recovery, result provenance, integrity verification and
bounded text/CSV/TSV/JSON previews. Synthetic example data are persisted through
the same EVC backend. No separate GUI history engine was introduced.

The UI uses the requested technical IDE layout, thin separators, compact controls
and neutral dark surfaces with viridis accents. It bundles genuine open-source
IDE widgets and license notices. There are no generated art assets, AI controls,
marketing dashboards or runtime CDN dependencies.

[Verification evidence](VERIFICATION.md) records the test counts, CI, launcher
smoke, dependency audits and inspected screenshots. [Known scientific and product
issues](KNOWN_ISSUES.md) separates reproduced failures from source-inspection
findings and unimplemented roadmap scope. The original scientific source and
tests are byte-for-byte unchanged on this branch.

Development was delivered as more than 50 separately pushed, nonempty commits
on `feat/aceneurotools-workbench`, authored/committed as Eli Keldsen and attributed
by GitHub to `elijah-keldsen`. No AI authorship trailer was added. The baseline
`proj-comenius` branch was not force-pushed, merged or rewritten. The collective
memory `.comenius/AGENT_MEMORY.md` is updated locally and remains git-ignored
under its existing protocol; these audit documents are the versioned record.
