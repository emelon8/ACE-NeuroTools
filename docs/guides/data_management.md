# Data Management in ACE-NeuroTools

ACE-NeuroTools uses a declarative, CSV-based approach to managing experimental data. Instead of writing custom scripts for every recording session, you maintain a master list of experiments and their analysis parameters in two CSV files.

This approach ensures that your analysis pipelines can be run in large batches without manual intervention.

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
    data_path="/path/to/my_awesome_project/raw_data"  # Where the base data folders live
)
```

### Where are the outputs saved?

By default, ACE-NeuroTools saves all intermediate and final analysis results (such as HDF5 files, filtered movies, and generated plots) **directly adjacent to the raw data**.

If your `calcium imaging directory` is set to `Rat01/2024_01_01/Miniscope`, the pipeline will create analysis folders inside that specific `Miniscope` directory. This keeps the derived data organized alongside the raw data it came from.

## Adding New Columns

You are free to add as many custom columns to `experiments.csv` as you like (e.g., `behavioral_score`, `genotype`). ACE-NeuroTools will automatically load these into the `ExperimentDataManager.metadata` dictionary, making them accessible to your custom downstream analysis scripts.
