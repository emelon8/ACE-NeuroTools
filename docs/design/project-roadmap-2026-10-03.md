# ACE-NeuroTools: working GUI and research roadmap

Planning date: October 3, 2026 (America/Denver).

Sources: the user-supplied September 29 lab-meeting transcript, the current
`design/guided-experiments` checkout, and the existing EVC backend in
`proj-comenius`. The transcript is automatically transcribed: names, algorithm
spellings, and some technical explanations are uncertain. Reported bugs and
resource figures are investigation leads, not established diagnoses.

## Direction

Build a local research workspace that makes experiments easy to organize,
inspect, change, run, and reproduce. Preserve the existing scientific methods
and the script/Python interfaces. Researchers should be able to explore alternate
parameters and recording sections, not just start a fixed pipeline.

The strongest meeting requests were:

- Projects containing experiments, with a separate repository per project.
- Actual data, parameters, crop decisions, neuron contours, and traces in one place.
- A workflow that makes the long processing step between cropping and neuron
  review explicit, with prerequisite checks.
- Clear answers to what excluding a neuron changes and what can be restored.
- Experiment history explaining what happened to the data.
- Interactive traces, parameter exploration, and access to downstream analyses.
- Exporting the same run as a Python script for a supercomputer, with Slurm support.
- Validation on real recordings, including additional recordings from other experiments.

See the transcript's GUI discussion (lines 437–759), missed-neuron discussion
(799–920), recording-order discussion (951–1106), performance discussion
(1131–1194), and exploratory-analysis discussion (1247–1365).

## Current state and practical constraints

Scope update: the user narrowed the immediate work to **Load existing CSV projects**,
with no modifications to `src`. The [experiment GUI](../../gui/README.md) now reads actual
projects, displays all records and Box links, and edits labeled metadata/settings
through the existing CSV helpers with backups. The sample-data
workspaces were removed. Runs, setup, EVC, and Git remain future work; the
broader roadmap below records earlier goals rather than the current acceptance gate.

An existing Python 3.10 scientific environment is present at
`/home/reedpen/.conda/envs/caiman`. Package discovery found CaImAn, NumPy, SciPy,
pandas, matplotlib, OpenCV, Neo, h5py, FreeSimpleGUI, and pytest there. The default
system Python lacks this stack. Package discovery is not proof of successful
imports or a working analysis run; the actual worker environment must be tested.

No raw AVI/NCS recordings or estimates HDF5 files were found by the workspace
file inventory. The bundled experiment CSVs contain historical paths, including
Windows locations, and are not proof that those recordings are present here.
The user clarified that experiments already live in `experiments.csv` and link
to Box. The first real GUI workflow must open that existing CSV/project rather
than require manual recreation. The checked-out `data/experiments.csv` has 118
nonblank records, 16 columns, and 31 rows with a Box link; `data/analysis_parameters.csv` has
114 nonblank records and 54 columns. These are candidate inputs, not proof that the user wants
this particular copy or that all Box links remain accessible. The GUI must let the
user select the authoritative project/CSV and a local recording cache.

Some other bundled CSVs did not decode as UTF-8 during inventory. Import should
report an encoding problem and offer a deliberate encoding selection instead of
silently dropping characters or modifying the original file. Different row counts
between experiment and parameter files also require missing-parameter/default
handling by stable experiment ID.

EVC is not on this design branch yet. Its inspected backend supports a local/shared
folder remote; normal Git transport and repository attachment require a deliberate
adapter. Neither is implemented by the CSV viewer.

## CSV and Box contract

This is the first implementation slice, based on the user's clarification:

1. **Open an existing project/CSV.** Browse to `experiments.csv` and the companion
   `analysis_parameters.csv` when present. Preserve stable `line number` identities,
   CSV headers, additional lab columns, and compatible value serialization.
2. **Load the complete experiment list.** Show metadata, recording paths, Box folder
   links, parameters, and whether required files are already available locally.
   Distinguish missing parameters from missing data; show the defaults actually used.
3. **Resolve recordings through Box or the local cache.** Reuse the existing Box
   integration, verify access, download only required/missing data, and show progress
   and incomplete-download errors. A nonempty directory alone is not sufficient
   evidence that a recording is complete.
4. **Edit and save the existing CSV records.** Preview changes, validate field types
   and dependencies, preserve unrelated rows/columns, detect external modifications,
   and write safely. Reopening the GUI and running an existing script should read
   the same updated values. Do not replace the user's workflow with a new file format.
5. **Run from resolved settings.** Use the existing configuration resolution appropriate
   to the selected workflow, capture the exact effective values and input references,
   and start the real scientific worker. Output and review decisions must identify
   that run even when the CSV is edited later.
6. **Keep source records and results traceable.** Save applicable metadata/parameter
   edits back to their CSVs. Store reviewed estimates/results in preserved run
   artifacts and history; the CSV alone does not hold neuron arrays or video data.

## Today's target: a demonstrably working GUI

**Target date: October 3, 2026. Completion requires evidence, not an enabled Run
button or a successful simulation.** The GUI must load a real project, persist
settings, show real data, run the existing analysis, support the necessary review
steps in the same interface, and display the outputs associated with that run.

The first acceptance path should be a representative, manageable miniscope
recording. Other existing workflows must be accounted for in the capability
inventory and connected through their existing entry points. Full script/API
parity cannot be claimed until every supported workflow has passed its matching
GUI acceptance checks.

| Order | Deliverable | Completion evidence |
| --- | --- | --- |
| 1 | Open the existing CSV project, verify the scientific environment, and resolve a Box-linked recording | The intended worker imports required packages; the selected experiment resolves to accessible data and valid metadata |
| 2 | Real project/experiment management | Add/open a project; list CSV experiments; edit settings through labeled fields; save and reload without losing unknown columns or overwriting external changes |
| 3 | Real preview and crop | Display an actual projection; save the selected bounds; verify that the same region is passed to the existing crop method |
| 4 | Actual analysis execution | Start an isolated worker using existing pipeline/stage APIs; capture effective parameters; show real stage/log/error information and output paths |
| 5 | Review neurons and continue | Display actual contours and traces; submit keep/exclude decisions before downstream event analysis; preserve original detections and persist curated results |
| 6 | Results and experiment history | Show artifacts from the actual run and their producing settings; preserve previous successful output; save/compare/restore tracked decisions through EVC |
| 7 | Visual finish and acceptance run | Apply a consistent visual system to the real screens; complete the full workflow on real data; verify a representative existing script still works |

Begin a short representative run as soon as the worker is available. Do not wait
for the final visual pass to discover an import, data, memory, or processing issue.
The meeting reported full-recording runs lasting roughly 10–12 hours; use those
reports to choose a feasible acceptance recording, not as a new benchmark.

Run-dependent work needs a selected authoritative CSV, working Box access (or cached recordings), and a writable local data location. Documentation, capability
mapping, persistence boundaries, worker design, UI components, and tests for
configuration/history can advance independently.

### Scientific integration rules for today's implementation

- Reuse scientific APIs; do not rewrite CNMF-E, filtering, event detection, or
  alignment in the frontend.
- Do not equate `headless=True` with a complete GUI integration. It suppresses
  existing neuron review and other inspections. Add an optional interaction seam
  or stage adapter while preserving existing script behavior.
- Neuron review must happen before downstream event detection. The current
  processing stage saves estimates before review; explicitly preserve that original
  result and save the curated result and selected original IDs separately.
- Translate browser image coordinates to the current crop convention. The existing
  crop method uses bottom-left GUI coordinates and flips y for array slicing.
- Keep recorded run inputs fixed. Settings edits produce a new working version;
  they must not modify a job already running.
- A changed crop invalidates later processing and neuron decisions. Changed selection
  invalidates affected downstream products, without silently overwriting originals.
- Distinguish population mean-fluorescence output from individual-neuron traces.
  The existing compute workflow is not equivalent to curated CNMF-E output.
- Report measured progress or stage activity. Remove timer-based success, synthetic
  traces, and fabricated availability states from operational screens.

## Improvement backlog

### P0 — required for real use

1. **Connect the GUI to the backend.** Introduce a local application service and
   worker interface over existing functions; keep frontend dependencies optional.
2. **Persist actual projects, metadata, and analysis parameters.** Round-trip existing
   file formats, preserve additional lab columns, and detect external edits.
3. **Make the workflow state explicit.** Ready → preprocessing → source extraction
   → needs neuron review → downstream analysis → complete/failed/stopped. Explain
   prerequisites and rerun consequences next to the affected action.
4. **Embed real cropping and neuron review.** Actual projection backgrounds,
   original candidate IDs, traces, reversible draft choices, and explicit Apply/Cancel.
5. **Preserve results and experiment history.** Separate raw detections, curated
   estimates, downstream results, run parameters, and working drafts. Show what
   restore actually restores and whether referenced files still exist.
6. **Make failures actionable.** Missing tools/data/timestamps, invalid channel names,
   invalid parameters, Box access failures, worker errors, memory failures, and
   repository failures must produce persistent errors with a recovery action.
7. **Verify scientific and CLI compatibility.** Compare GUI/CLI effective parameters
   and representative outputs; retain the existing scripts and mathematical methods.

### P1 — improve everyday research work

8. **Support interactive exploration.** Zoom/pan traces; inspect selected time
   intervals; link the selected neuron to its contour and activity; save alternative
   parameter/crop choices as named trials and compare their outputs.
9. **Expose existing downstream analyses.** Ephys channels, spectrograms, multimodal
   alignment, coherence, cross-correlation, events, and project/cohort statistics.
   Generate a source-backed capability checklist so less visible features and
   advanced CaImAn parameters are not omitted.
10. **Export reproducible jobs.** Generate a standalone Python run script from the
    same resolved settings used by the GUI. Add Slurm templates with explicit
    environment, input/output locations, CPUs, and memory. Treat interactive neuron
    review as a separate checkpoint/job stage rather than an HPC prompt.
11. **Complete guided setup.** Validate/select or provision the analysis environment,
    guide Box integration or local-data setup, then create the first project and
    experiment. Offer repair/reconnect actions after first use.
12. **Add project repository attachment.** Validate destination/access, retain the
    existing connection until replacement passes, separate local save from publish,
    compare shared changes, and preserve both histories on conflicts. Define the
    Git/EVC interoperability contract before implementing transport.
13. **Make neuron review practical at scale.** Keyboard next/previous and keep/exclude,
    filters for reviewed/unreviewed candidates, a progress count, and resumable review.
    Define shared-review ownership before introducing multi-reviewer writes.
14. **Clarify results.** Explain which signal/analysis each view represents, show
    the producing settings and run, identify stale results, and export useful plots/data.
15. **Strengthen input validation and lab defaults.** Preview movie-segment order,
    check timestamps against frames, validate events/channels, and allow project
    channel defaults with per-experiment overrides. Keep Bonsai acquisition integration
    separate from the analysis GUI unless a specific shared-data contract is defined.

### P2 — performance, quality control, and future science

16. **Investigate movie ordering and concatenation.** Reproduce the reported
    `0, 1, 10, 11` behavior with numbered segments, verify the timestamp alignment,
    and isolate whether ACE file discovery or CaImAn ordering causes it. Submit an
    upstream issue/patch only after the ownership is demonstrated.
17. **Profile memory and parallel processing.** Measure peak memory by stage,
    worker count, repeated movie allocations, and decompressed volume. The current
    processor already keeps a reference instead of the reported full deep copy;
    inspect remaining copies rather than applying that fix again. The residual-view
    path still copies a movie. Benchmark improvements against unchanged outputs.
18. **Add missed-neuron quality control.** Compare raw/corrected movies, detected
    regions, and residual/background activity. The existing “movie without neurons”
    helper masks pixels; do not label that as a validated CNMF reconstruction residual.
    Manual ROI addition requires a defined trace-extraction and provenance policy.
19. **Establish a representative recording suite.** Short smoke recordings plus
    longer recordings from multiple sessions/conditions, regression baselines,
    expected artifacts, frame/timestamp checks, and repeatable environment setup.
20. **Explore new scientific analyses as separate modules.** Pre/post-event windows,
    autocorrelation, cross-correlation, PCA/clustering, latent/hidden-state models,
    and dynamical-system analyses are research candidates from the meeting. Specify
    hypotheses and methods with scientific review, consult the literature, and
    validate on another experiment before making them standard GUI options.
21. **Prepare release and training materials.** Update project naming/links if the
    repository was renamed, verify contributor/author records, provide a short
    first-run guide, real-data screenshots, and a release checklist. Repository
    visibility and naming claims in the meeting should be verified before changes.

## Visual-style plan

Keep the clean professional direction and the meeting's positive feedback on the
colors. Improve clarity and polish alongside the real integration:

- A restrained green/neutral palette; red for blocking errors, amber for required
  review, and visible text/icon labels alongside color.
- Consistent typography, spacing, form sizes, button hierarchy, and panel borders.
  Remove developer/demo terminology from the operational workflow.
- Project folders with readable experiment rows and a clear next action.
  Keep Add experiment inside its destination project.
- One experiment header with status, Run/Rerun, and **Experiment history**.
  Make the Crop → Processing → Neuron review → Results sequence visible.
- Large data viewers with a stable control panel; zoomable/pannable traces,
  projection controls, selected-neuron feedback, and explicit apply/cancel controls.
- Intentional empty, loading, unavailable, paused, failed, and stale-result states.
  Keyboard access and readable contrast are part of the finish.
- Use real data in the viewer; the demo workspaces have been removed.

## Completion and prioritization

**Today is successful only when a real experiment completes through the GUI and
its outputs and review decisions can be reopened.** A mock error walkthrough,
a settings form, or a completed timer does not satisfy that gate.

Full capability parity has its own gate: every supported user-facing script,
public pipeline option, advanced configuration group, visualization, and
history operation has an identified GUI route and verified behavior. Internal
implementation helpers and developer maintenance scripts should be accounted for
without requiring nontechnical researchers to invoke arbitrary Python code.

Prioritize the real-data workflow, correctness of review/results, and failure
recovery before new research algorithms or remote collaboration. The durable
scientific core is the shared foundation for the GUI, existing scripts, and
exported HPC jobs.
