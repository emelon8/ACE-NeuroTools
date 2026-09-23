# Guided experiment GUI prototype

An interactive design study for a nontechnical experiment workspace. Projects
appear as stacked folders; opening an experiment provides settings, cropping,
neuron review, results, and plain-language history in one interface.

**Status:** disposable prototype, not a working analysis frontend. All recordings,
images, traces, edits, history entries, and runs are demonstrations. No real
experiment files, scientific processes, or version-control storage are connected.
Refreshing or closing the page loses its demo state.

## Start and stop

Requirements: Python 3.10 or newer and a modern browser. No third-party Python
packages, CaImAn installation, Node.js, internet connection, or build step is
needed to run the preview.

From the repository root:

```bash
python scripts/preview_guided_gui.py
```

If your system calls Python 3 `python3`, use that command instead of `python`.
Open [http://127.0.0.1:8765/?variant=A](http://127.0.0.1:8765/?variant=A).
Keep the terminal running while reviewing the design; press **Ctrl+C** to stop
the server. The server serves only this prototype directory and listens on
`127.0.0.1`, so it is accessible from the same computer.

Each browser tab has its own temporary state. The URL stores the layout choice,
not experiment changes or the selected experiment. Reloading starts at Projects.

## Review walkthrough

1. **Browse projects.** Expand or collapse a project folder. Search by project,
   experiment, subject, or experiment number. Use **Show experiments** in the
   attention banner to filter experiments needing review or a data check.
2. **Open an experiment.** Choose **Baseline · session 04**. The Overview shows
   next actions and recording details. The project breadcrumb returns home.
3. **Edit settings.** Open **Data & settings**, change a value, and choose
   **Apply changes**. The lower frequency must be less than the upper frequency.
   Unapplied field edits are discarded when navigating away in this prototype.
4. **Crop.** Open **Crop**, drag a rectangle over the sample image or enter pixel
   boundaries, then choose **Apply crop**. Right must exceed left, and bottom
   must exceed top. **Reset** immediately restores the full demo image bounds.
5. **Review neurons.** Select a contour or numbered button, inspect its sample
   trace, and choose **Keep this neuron** or **Exclude this neuron**. Excluded
   candidates have dashed amber outlines; the selected candidate has a white
   outline. Choose **Apply selection** when ready.
6. **Save and compare.** Choose **Save a version** and describe the change.
   **History → See what changed** compares a saved version with current working
   settings. Restore previews the differences, saves current demo work, and
   adds the restored state as a new entry. These are in-memory demonstrations
   of the intended EVC experience, not calls to the EVC backend.
7. **Run the demo.** Choose **Run experiment**, review the settings, then
   **Start demo run**. Imaging experiments pause at 60% for neuron review.
   Choose **Apply & continue run** to finish, then inspect **Results**.
   Electrophysiology demos finish without the neuron checkpoint. The run dialog
   offers **Stop demo run** while processing. A sample experiment marked
   **Check data** cannot start a run.
8. **Add sample records.** The home screen offers **Add project** and
   **Add experiment**. The experiment form opens inside its destination project
   folder and names that project. These forms add temporary sample entries; they do not
   open folders, inspect recordings, or create files.

## Compare experiment layouts

All three layouts preserve the same stacked project home. Open an experiment
before comparing them with the floating bottom arrows.

| URL choice | Layout | Design question |
| --- | --- | --- |
| `?variant=A` | Tabbed experiment | Does direct access to each task suit repeated use? |
| `?variant=B` | Experiment overview | Does a larger overview make available tasks easier to discover? |
| `?variant=C` | Guided steps | Does a persistent step list help users find their place? |

Left/right keyboard arrows also switch layouts, except in form controls and
editable text. The switcher appears only on a local/file preview. The
**Prototype state** disclosure at the bottom exposes the selected experiment's
working state for design inspection; it is not part of the intended product.

A is the current recommendation. No final layout choice has been recorded.
See [design notes](NOTES.md) for the decision to capture after review.

## Implemented versus proposed

The prototype demonstrates navigation, representative field editing, crop
selection, neuron keep/exclude choices, a temporary version timeline, and a
simulated run/review flow. It intentionally has no backend or persistence.

The following remain production work:

- Real project discovery, folder selection, data import, and file validation.
- Complete parameter coverage and compatibility with existing configuration files.
- Actual recording previews, projections, contours, and activity traces.
- Running and stopping analysis workers, reporting actual progress, and handling
  failure, recovery, and concurrent edits.
- EVC integration, result verification, safe output preservation, and CSV writeback.
- Fully specified draft/apply/cancel semantics and protections against editing
  captured inputs during a run.
- Accessibility audit and supported-browser/platform validation.

The displayed progress percentage is a timer, not a performance estimate. Runs
do not generate output files, re-extract candidates, or update scientific traces.
Neuron choices are demo working-state edits; they are not isolated drafts.
Only the active scientific capabilities appropriate to the sample recording type
are shown, and the parameter form is a representative subset.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `python` is not found | Use `python3` or install Python 3.10 or newer. |
| Address/port already in use | Check whether a preview is already running at the URL. Stop your earlier preview with Ctrl+C before starting another. |
| Browser cannot connect | Run the command on the same computer as the browser and keep its terminal open. Check the terminal for startup errors. |
| Changes disappeared | Reload resets demo state by design. Save a version stores only in-memory history for that tab. |
| Layout switch seems to do nothing | The project home is shared. Open an experiment to compare detail layouts. |
| Real data cannot be selected | Folder picking and scientific data loading are proposed features, not implemented in this preview. |

## Files and validation

| File | Purpose |
| --- | --- |
| `index.html` | Static entry page |
| `style.css` | Layout, typography, responsive styles |
| `app.js` | Sample data, three detail layouts, and demo interactions |
| `../../scripts/preview_guided_gui.py` | Standard-library local preview server |
| `../../docs/design/guided-experiments-mvp.md` | Product scope, EVC mapping, and integration/acceptance criteria |

During the initial design review, Chromium interaction checks covered navigation,
settings edits, numeric crop application, search, neuron toggling, version save
and restore, all three variants, and the simulated review/resume/completion flow.
No browser exceptions were observed in those checks. Desktop screenshots were
visually inspected, and a 390-pixel-wide guided layout showed no horizontal
overflow. These are prototype smoke checks, not scientific or accessibility
validation; crop dragging and all browser/platform combinations were not exhaustively tested.

For source-only checks, use `node --check prototypes/guided-experiments/app.js`
(Node.js is only needed for this developer check) and `git diff --check` from
the repository root. Review the walkthrough above after interaction changes.
The scientific test suite is separate: this prototype changes no scientific code.

Once a design is selected, record the decision in the MVP document, remove the
losing variants, and rewrite the selected interactions with production validation
and backend integration. Do not ship this prototype as the analysis application.
