# Data Management in ACE-NeuroTools

ACE-NeuroTools uses a declarative, CSV-based approach to managing experimental data. Instead of writing custom scripts for every recording session, you maintain a master list of experiments and their analysis parameters in two CSV files.

The module CLIs and GUI load supported run settings from the parameter CSV.
Direct Python calls need explicit pipeline kwargs. Batch execution also requires
local recordings and noninteractive settings; CSV metadata alone does not ensure
an unattended run.

## The Core Files

At the root of your project directory, ACE-NeuroTools expects to find two files:

1.  `experiments.csv`: The metadata for each recording session (e.g., date, rat ID, raw data directories, drug doses).
2.  `analysis_parameters.csv`: The algorithmic parameters used to process the data (e.g., CNMF-E parameters, filtering thresholds).

> [!IMPORTANT]
> Both files must have a `line number` column. This is the unique identifier that links an experiment's metadata to its analysis parameters, and it is the primary argument passed to all ACE-NeuroTools pipelines.

## Getting Started: The Templates

When starting a new project, utilize our provided templates as a starting point. These templates contain all necessary headers in the expected format. 

You can find the templates in the [source code repository](https://github.com/emelon8/experiment_analysis/tree/main/src/aceneurotools/shared/metadata_templates).

1. Copy `experiments_template.csv` to your project folder and rename it to `experiments.csv`.
2. Copy `analysis_parameters_template.csv` to your project folder and rename it to `analysis_parameters.csv`.

## Structuring Your Project

While ACE-NeuroTools is flexible, we highly recommend keeping your CSV files separate from the raw downloaded data. A typical project structure looks like this:

```text
my_awesome_project/
├── data/
│   ├── experiments.csv             # Your copied template
│   └── analysis_parameters.csv     # Your copied template 
└── raw_data/
    ├── Rat01/
    │   └── 2024_01_01/
    │       ├── Miniscope/
    │       └── Ephys/
    └── Rat02/
```

### Absolute vs. Relative Paths

In `experiments.csv`, you specify the location of your raw data in the `calcium imaging directory` and `ephys directory` columns.

*   **Relative Paths (Recommended)**: If you provide a relative path (e.g., `Rat01/2024_01_01/Miniscope`), ACE-NeuroTools will look for this path *relative to the `--data-path`* argument you provide when running the pipeline.
*   **Absolute Paths (Discouraged)**: If you provide an absolute path, ACE-NeuroTools will use it exactly. This makes it very difficult to share your project with collaborators or run it on a supercomputer.

## Running the Pipeline

Once your CSV files are populated, you can run the pipeline by specifying the `line_num` and the paths to your project and data directories:

```python
from aceneurotools.pipelines.miniscope import MiniscopePipeline

pipeline = MiniscopePipeline()

# Run the experiment on line 5 of your CSVs
pipeline.run(
    line_num=5,
    project_path="/path/to/my_awesome_project/data",  # Where the CSVs live
    data_path="/path/to/my_awesome_project/raw_data",  # Where the base data folders live
    run_CNMFE=True,  # Direct Python API defaults to no source extraction
    headless=True,
)
```

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
- **Graceful Fallback**: If Box IDs are present but you haven't configured your credentials, the system will print a reminder with setup instructions and proceed using only what is available locally.

### Where are the outputs saved?

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

## Adding New Columns

You are free to add as many custom columns to `experiments.csv` as you like (e.g., `behavioral_score`, `genotype`). ACE-NeuroTools will automatically load these into the `ExperimentDataManager.metadata` dictionary, making them accessible to your custom downstream analysis scripts.
