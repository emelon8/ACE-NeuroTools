# Data Management in ACE-NeuroTools

ACE-NeuroTools uses a CSV spreadsheet to identify recordings. Each row in `experiments.csv` describes one experiment and points to its raw files. You can keep analysis choices in a second CSV when you need them.

The module CLIs and GUI load supported run settings from the parameter CSV.
Direct Python calls need explicit pipeline kwargs. Batch execution also requires
local recordings and noninteractive settings; CSV metadata alone does not ensure
an unattended run.

The value in the `line number` column is the experiment's ID. It is how a command chooses a row; it is not the row's physical position in a spreadsheet.

## The Core Files

Keep these files in the folder you pass as `--project-path`:

1.  `experiments.csv`: The metadata for each recording session (e.g., date, rat ID, raw data directories, drug doses).
2.  `analysis_parameters.csv` (optional): Per-experiment processing choices (e.g., CNMF-E parameters and filtering cutoffs).

!!! important
    `experiments.csv` is required and must have a `line number` column with a unique ID for each recording. If you create `analysis_parameters.csv`, it also needs that column. The module commands use the chosen ID to find the parameter row; an existing parameter file with no matching row causes an error. A missing parameter file uses built-in defaults. Direct Python `run(...)` calls do not automatically merge parameter values from that file.

## Getting Started: The Templates

Start with the provided templates so the column names match what the software reads. Edit the example values for your own experiment.

You can find the templates in the [source code repository](https://github.com/emelon8/ACE-NeuroTools/tree/proj-comenius/src/aceneurotools/shared/metadata_templates).

1. Run the [initializer](../getting_started.md#3-create-project-configuration) or copy `experiments_template.csv` to your project folder and rename it to `experiments.csv`.
2. Copy `analysis_parameters_template.csv` only when you need to set per-experiment options. Give its row the same `line number` value as the experiment it describes.

## Structuring Your Project

While ACE-NeuroTools is flexible, we highly recommend keeping your CSV files separate from the raw downloaded data. A typical project structure looks like this:

```text
my_awesome_project/
├── data/
│   ├── experiments.csv             # Your copied template
│   └── analysis_parameters.csv     # Optional
└── raw_data/
    ├── Rat01/
    │   └── 2024_01_01/
    │       ├── Miniscope/
    │       └── Ephys/
    └── Rat02/
```

### Absolute vs. Relative Paths

In `experiments.csv`, enter the location of raw data in `calcium imaging directory` or `ephys directory`, depending on the recording. For example, with `--data-path /lab/raw_data` and `calcium imaging directory` set to `Rat01/2024_01_01`, the software looks under `/lab/raw_data/Rat01/2024_01_01`.

*   **Relative Paths (Recommended)**: If you provide a relative path (e.g., `Rat01/2024_01_01/Miniscope`), ACE-NeuroTools will look for this path *relative to the `--data-path`* argument you provide when running the pipeline.
*   **Absolute Paths (Discouraged)**: If you provide an absolute path, ACE-NeuroTools will use it exactly. This makes it very difficult to share your project with collaborators or run it on a supercomputer.

## Running the Pipeline

For an experiment whose `line number` cell contains `5`, run:

```bash
python -m aceneurotools.pipelines.miniscope \
  --line-num 5 \
  --project-path /path/to/my_awesome_project/data \
  --data-path /path/to/my_awesome_project/raw_data
```

The selected row must point to a real supported recording. See [Getting started](../getting_started.md#6-run-a-pipeline) for the ephys and multimodal commands.

## Optional: Box Cloud Integration

If your lab uses Box to store and share raw data, ACE-NeuroTools can automatically download missing files for a specific experiment before the analysis begins. This is an **optional opt-in feature**.

### 1. Enable Box in Metadata
In your `experiments.csv`, fill in the **Box Calcium Folder ID** and/or **Box ephys folder ID** columns for the experiments you want to sync. If these columns are empty, ACE-NeuroTools will only look for data at the local paths provided.

### 2. Configure Authentication

In the [experiment GUI](experiment_gui.md), use **Box connection** to verify the
account and choose a download folder. Saved CCG connection settings live under
`$XDG_CONFIG_HOME/aceneurotools/gui/box.json` (normally
`~/.config/aceneurotools/gui/box.json`); temporary developer tokens stay in
memory. This GUI connection is separate from the legacy script credentials
below and does not write into the package source.

For existing scripts using the library downloader:
To allow the code to talk to Box, you must provide your own API credentials:
1.  **Install the SDK**: Ensure you have the optional dependencies installed: `pip install aceneurotools[box]`
2.  **Locate the Template**: Find `src/aceneurotools/shared/BLANK_box_credentials.py` in the package source.
3.  **Setup your file**: Copy it to `src/aceneurotools/shared/box_credentials.py`.
4.  **Enter Credentials**: Enter your **Client ID**, **Client Secret**, and **User ID** (obtained from the [Box Developer Console](https://app.box.com/developers/console)).

### How it Works
- **Local First**: If the data already exists at the specified local path, the pipeline starts immediately without connecting to Box.
- **Script download checks**: If a folder is missing or empty and a Box ID is
  provided, configured scripts can attempt a download. A nonempty folder does not
  prove a recording is complete. Verify the required movie, timestamp, and
  metadata files before relying on that check.
- **GUI downloads**: Review a Box file selection and its size, then confirm the
  download. A small selected subset can be reused for crop and analysis runs;
  the GUI does not silently expand it to the full recording.
- **Missing credentials**: Local processing can continue when all required files
  are already present. If a requested file is missing, the run cannot process
  it without a working Box connection; check the local paths or configure Box.

## Where results appear

Core miniscope stages save processed movies and configured estimates/options
under the recording's `saved_movies` folder. Other results may remain in memory;
core API calls do not produce the GUI's output inventory. Compute and statistics
workflows accept separate output destinations.

GUI runs preserve private recording and CSV copies in a new
`<project>/.ace-runs/<run-id>/` folder. Each completed run includes an
`output-inventory.json` identifying exported arrays/events and unavailable
results. Neuron review saves its journal in `.ace-neuron-reviews`; each curated
export uses a fresh folder under the chosen destination (default
`<project>/.ace-curations`). Original recordings, estimates, and earlier results
remain available. See the [GUI guide](experiment_gui.md#output-inventory) for
the exported file formats and component-ID mapping.

The modality commands may place derived files inside the recording directory under `--data-path`. Keep enough free space there and distinguish generated files from raw inputs.

| Run or option | What to check | Location |
| --- | --- | --- |
| Miniscope preprocessing | Cropped, detrended, or corrected movie when that step runs | `saved_movies/` inside the calcium-imaging directory |
| Miniscope CNMF-E with `save_estimates=True` | `estimates.hdf5`, containing extracted cell estimates | `saved_movies/` inside the calcium-imaging directory |
| Ephys with plotting enabled | Signal or spectrogram window | Displayed interactively; the module command does not save a plot file by default |
| Multimodal alignment | Aligned times and phase results | Available on the Python `MultimodalPipeline` result object; the module command does not automatically export a report |
| `ace-neuro` compute/statistics launcher | Signal files, figures, statistics, and `run_log.json`, depending on selected mode | The configured `output_dir` and `calcium_signal_dir` in `lab_config.json` |

The [miniscope](miniscope.md), [ephys](ephys.md), and [multimodal](multimodal.md) guides explain which switches produce each result.

## Adding New Columns

You are free to add as many custom columns to `experiments.csv` as you like (e.g., `behavioral_score`, `genotype`). ACE-NeuroTools will automatically load these into the `ExperimentDataManager.metadata` dictionary, making them accessible to your custom downstream analysis scripts.
