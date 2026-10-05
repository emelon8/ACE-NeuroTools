# Guided experiment GUI — MVP design

Status: [project browsing and CSV editing](../../gui/README.md) are implemented.
The old sample-data prototypes and launcher have been removed. The broader workflows
below remain a future design, not implemented functionality.

Branch: `design/guided-experiments`. Current scope: load existing projects, browse
all experiments, edit labeled metadata/settings, select folders, and follow Box links. No changes to `src` are
authorized for this slice.

## October 3 implementation priorities

The [project roadmap](project-roadmap-2026-10-03.md) incorporates the September 29
meeting and the user's goal for a working backend-connected GUI, actual experiment
runs, and improved visual style. The [source capability inventory](pipeline-capabilities.md)
provides the scientific parity checklist. The first real-data workflow must load
existing experiments from `experiments.csv`, use their Box links, and read/save
compatible metadata and parameters in the existing CSV files.

## Agreed direction

- A fresh frontend, independent of Eli’s IDE-style GUI.
- Modern, clean, professional visual design for nontechnical researchers.
- Projects appear as stacked, titled, expandable folders. Each contains experiments.
- Opening an experiment shows its parameters, recording data, analysis actions, results, and history.
- Cropping and neuron selection happen inside the same application surface.
- Existing command-line scripts, Python APIs, defaults, file formats, and scientific computation remain supported.
- Reuse Eli’s experiment version control backend through a simple History presentation.
- Browse experiments and see what needs attention before asking users to start a wizard.

## Concrete design

### Guided first-time setup

User requirement added September 29, 2026: provide one guided setup process for
the analysis environment, Box integration, and the first experiment. This is a
requirement for the working frontend. Setup is outside the current CSV-viewing slice.

1. **Prepare analysis tools.** Detect an existing compatible environment, explain
   missing dependencies in plain language, and offer a guided installation or
   selection of an existing environment. Verify that the actual worker can
   import its scientific dependencies before reporting readiness. Show progress,
   actionable failures, and a retry path. Preserve existing environments.
2. **Choose the data source.** Offer Box and local recordings. For Box, guide the
   user through the authentication method supported by the existing integration,
   verify access, choose source folders and a local download location, and explain
   any lab-administrator setup required. Never treat entered credentials as a
   successful connection until access is verified. Keep credentials out of
   experiment settings, version history, logs, and exported configurations.
3. **Create or open a project.** Choose its name and folder, initialize or validate
   existing configuration, and retain existing files unless the user deliberately
   chooses to replace them.
4. **Create the first experiment.** Keep the form within its project, select the
   recording type and source data, enter metadata, and validate required files,
   channels, and timestamps. Make defaults and missing information visible.
5. **Review readiness.** Summarize the environment, data connection, project, and
   experiment, then open the experiment workspace. Starting analysis remains an
   explicit action. Allow users to revisit setup later to repair connections or
   choose a different environment.

### Projects and experiment workspace

**Home:** stacked project folders, expanded experiment rows, search, and a Needs attention filter. Show recording type, subject, recording date, and an actionable status. Add/open a project through a folder chooser in the real application. Remember project locations without moving recordings. A missing or disconnected folder stays listed with a Reconnect action. The Add experiment form belongs inside its destination project folder and explicitly names that project; it must not appear as a detached page-level form.

**Experiment:** title and project breadcrumb, current status, Save a version, and Run / Run again. Sections: Overview, Data & settings, Crop, Neurons, Results, History. Hide actions that do not apply to the recording type. A focused editor replaces the content area; no detached crop or neuron windows.

**Data & settings:** labeled fields with units, validation, field help, and an Advanced section. Preserve all supported parameters and unrecognized lab-specific columns. Show recording locations, channels, timestamps, and missing inputs. Avoid displaying serialized files as the primary editor. Project identity and the legacy experiment line number are stable even if the display title changes.

**Crop:** projection preview with drag selection, numeric bounds for precision/accessibility, reset, Apply, and explicit cancel/discard semantics. Coordinates refer to the original image, not the scaled viewport. Validate bounds and orientation. Never crop raw data in place. Show the actual available projections (max/min/mean/median/std/range).

**Neurons:** contours over a projection, a numbered candidate list, Keep / Exclude, selected-neuron trace, and kept/excluded counts. Color is accompanied by outline style and text. Preserve original candidate IDs, including excluded candidates, until finalizing a working copy. Existing code translates 1-based display labels into 0-based component indices; the frontend adapter must preserve this mapping exactly. New source extraction produces a new candidate set: old decisions must not silently attach to new indices.

**Run:** validate inputs → review effective settings and changes → save run settings → process → pause for neuron review if needed → finalize downstream analysis → show results. One active run per experiment in the MVP; users can browse other experiments while it runs. MVP should serialize heavy jobs rather than introduce concurrent CaImAn worker pools. Editing/restoring a running experiment must not change the captured run inputs. Report stages and indeterminate progress unless the backend supplies a real denominator.

**Results:** show plots, traces, artifact locations, and the exact run/version that produced them. Mark existing results “From earlier settings” after edits. Missing or changed artifacts get explicit status. An unsuccessful/cancelled run must not replace the latest successful results. Overwriting output paths requires a documented staging/preservation policy before real execution is connected; current scripts may use stable output filenames.

## History vocabulary and existing backend mapping

Backend inspected in `proj-comenius` at `fa9e79b`; only backend source and its API documentation were used. That branch also contains the legacy GUI. The new design branch starts at local `main` (`02ffaad`) and does **not** yet include EVC. Production work must port the backend and required dependencies/tests independently; do not merge the legacy GUI as a shortcut.

| User-facing action | Existing backend contract | Presentation |
| --- | --- | --- |
| Unsaved changes | `ExperimentVersionControl.status()` | Field-level changes rather than JSON diffs |
| Save a version | `record(message)` | Short human description; identical state needs no duplicate version |
| History | `history()` / `show()` | Date, description, run context; IDs in optional details |
| See what changed | `diff(a, b)` plus status for working edits | Old value → new value, units and field names |
| Restore this version | `restore(rev)` | Preview scope; preserve current work first; return settings forward |
| Recover saved work | `recover()` | Include safety snapshots and failed-run entries when appropriate |
| Run provenance | `RunRecorder` lifecycle hooks | Link approved effective settings to completion or failure |
| Check result availability | `verify_manifest()` | Available / missing / changed |

History covers tracked settings, decisions, metadata, and artifact references according to EVC’s workspace policy. It is **not** a raw-recording backup, and restoring a manifest cannot recreate a missing file. The existing restore safety snapshot may live in the recovery journal instead of ordinary history; the frontend must surface it.

The CSV bridge offers `extract`, `import_experiment`, `validate_document`, and `writeback`. Reuse these instead of inventing another experiment format. Audit optional/missing parameter CSV behavior, unknown-column preservation, cross-experiment writes, and concurrent external edits before enabling Save. Detect changed source files and reload/resolve instead of silently overwriting script edits. Saving/restoring GUI state must update the legacy representation deliberately, with a reviewable diff.

## Additive integration boundary

```text
Guided UI
  └─ optional local application adapter
       ├─ projects and experiment field mapping ↔ existing files / EVC bridge
       ├─ History ↔ aceneurotools.evc.api
       └─ worker process ↔ existing pipeline/config APIs
            ├─ preview / crop decision
            ├─ scientific processing
            ├─ neuron-review checkpoint
            └─ existing postprocessing and result writers

Existing scripts and Python callers → existing pipeline/config APIs
```

A local browser-style interface is the design vehicle, not a hosting decision. The actual GUI must launch locally with one user action and keep recordings local. A packaged desktop shell can follow if needed; cloud hosting/accounts are outside this MVP. Keep frontend dependencies optional and avoid importing them from the CLI/scientific core.

Cropping already accepts `crop_coords` with `headless=True`. Neuron review is currently embedded in `MiniscopePostprocessor.postprocess_calcium_movie`: `plot_contours()` and `component_gui()` run before calcium-event detection. Simply running the whole pipeline headlessly suppresses review; running it interactively opens old windows. Neither satisfies this design.

A focused technical spike must establish a GUI-only orchestration/checkpoint adapter over the current stage APIs, with optional backward-compatible interaction hooks only if needed. Reuse scientific methods; do not duplicate computation or monkey-patch GUI functions. CLI defaults continue to invoke existing interactions. The frontend needs a real pause/resume or persisted-stage boundary before downstream events are computed; selecting neurons only after final results have been calculated would produce inconsistent results. Audit other plot and inspection windows too, including motion correction and electrophysiology plots.

Use the same configuration resolution as the selected existing entry point. CLI commands and direct `run(...)` calls do not necessarily merge CSV values the same way. Capture the resolved effective values shown on Review before running, including their source, rather than silently substituting frontend defaults.

## MVP scope and sequence

1. **Browse and edit:** open existing projects; stacked folders and experiments; field-based metadata/settings editing; validation; existing file compatibility; History via EVC. Import an existing project without requiring migration of its recordings.
2. **One complete miniscope workflow:** in-app preview/crop; existing processing; in-app neuron review; downstream processing; progress/failure/stop handling; results tied to run settings. Support reopening saved estimates for review without forcing source extraction again when inputs remain valid.
3. **Other existing public workflows:** ephys (single/multiple/all channels), multimodal alignment, compute, and statistics. Use the same experiment shell; cohort statistics belongs at project level with an explicit experiment selector. Maintain a capability inventory until parity with supported user-facing scripts is achieved.

This is a staged MVP, not a claim that the first miniscope slice covers everything the library can do. No scientific feature is removed from existing scripts. Shared remote publication, project collaboration, scheduling, advanced batch orchestration, and a new data-storage system can wait.

## Acceptance checks before real release

- Representative CLI and Python calls behave as before with no GUI installation required.
- GUI and CLI effective parameters match for an equivalent experiment; compare scientific outputs on a representative recording.
- Crop coordinates round-trip across image scaling and existing storage conventions.
- Keep/exclude decisions preserve component IDs and feed downstream event calculations correctly.
- No child interaction windows open during GUI runs; required inspections are embedded or explicitly offered as saved plots.
- Optional CSVs, unknown columns, missing files, and external edits are handled without data loss.
- History save/compare/restore uses EVC, exposes safety recovery, and never implies raw-data backup.
- Run inputs stay fixed; stop/failure preserve the last successful outputs; results identify their producing settings.
- Editing a crop invalidates dependent results and neuron decisions; reviewing existing estimates invalidates only affected downstream products.

## Current implementation

Launch with `python scripts/run_gui.py --project /path/to/project` from the
analysis environment. The current GUI has expandable project folders, clickable experiment rows, and
grouped field editors, with square controls, strong rules, serif headings, and
no decorative cards, gradients, animations, or dashboard sidebar.

It loads actual CSV records, preserves unknown fields and exact text, and detects
external changes before inspection. Missing or invalid settings remain visible;
no defaults, execution, history, or connection success are simulated. Explicit saves
reuse existing CSV write helpers on a staged file, preserve other records, and keep
backups. New settings rows are added only after the user chooses Add settings and Save.

## Repository attachment and visible error handling

The user requested an easy way to attach another Git repository and clear errors
when setup is incorrect. The future integration should offer a project-level repository
address/branch, separate Check connection and Attach/Switch actions, separate local
save and publish actions, and preservation of the current connection on failure.
Editing the proposed destination invalidates earlier checks. Publishing must never
force-overwrite someone else's shared history.

A standard Git repository is a new integration requirement. The inspected EVC
backend provides `LocalDirectoryRemote`; it does not establish standard Git
transport/interoperability, Git-host authentication, or a pull/merge workflow.
Separate-branch recovery is a proposed Git-adapter interaction, not an existing EVC feature. Define the tracked-file/export contract
and preservation rules before connecting it to real repositories.

Blocking errors should be persistent, prominent, keyboard-focused alert panels:
what failed, what was preserved, what is blocked, and a concrete recovery action.
Keep details available without requiring users to interpret a traceback. Checks
need actual evidence before marking environments, accounts, data, or remotes ready.
Local saving and remote publishing remain distinct, with no assumption that a saved
version has been shared or that sharing backs up raw recordings.

Repository attachment and setup are outside the current project and CSV editing slice.
