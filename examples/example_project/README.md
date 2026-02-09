# Example Project

This directory demonstrates the structure of a self-contained project repository.

## Structure

- **`experiments.csv`**: Contains metadata for experiments specific to this project. Copy relevant rows from the master `experiments.csv`.
- **`analysis_parameters.csv`**: Contains analysis parameters for each experiment.
- **`run_analysis.py`**: A script to run batch analysis for the experiments in this project.

## Usage

1.  **Configure Environment**:
    Point the `PROJECT_REPO` environment variable to this directory.
    
    ```bash
    # In .env file at the root of experiment_analysis
    PROJECT_REPO=/absolute/path/to/experiment_analysis/examples/example_project
    ```

2.  **Run Analysis**:
    You can run the analysis using the CLI or the batch script.

    **Using CLI:**
    ```bash
    # Must have PROJECT_REPO set in .env
    python -m src2.miniscope.miniscope_pipeline --line-num 96
    ```

    **Using Batch Script:**
    ```bash
    python examples/example_project/run_analysis.py
    ```

## Notes

- The `experiments.csv` file should contain the same columns as the master `experiments.csv`.
- The `analysis_parameters.csv` file should have a `line number` column matching `experiments.csv`.
