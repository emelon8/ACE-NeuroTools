# Changelog

All notable changes to the experiment_analysis package will be documented in this file.

---

## [Unreleased] - Project Compartmentalization

### Overview

This release introduces a new configuration system that allows each research project to maintain its own self-contained repository with experiment metadata and analysis parameters. This enables full reproducibility: when a project is published, its repository contains everything needed to replicate the analysis.

### Breaking Changes

> [!CAUTION]
> The way configuration files are handled has changed significantly. Please read the migration guide below.

- **YAML config files have been removed.** Pipeline CLIs now only accept `--line-num`.
- **Pipeline entry points now require `--line-num`.** You must specify the experiment line number explicitly.
- **`paths.py` now reads from environment variables.** The `PROJECT_REPO` environment variable (typically set in `.env`) determines where CSVs are loaded from.

### New Features

#### Project Repository Structure

Each project now lives in its own Git repository with:

```
your-project-repo/
├── experiments.csv           # Experiment metadata (relevant rows only)
├── analysis_parameters.csv   # Processing settings per experiment
├── run_analysis.py           # Optional batch script
└── README.md                 # Methods documentation
```

This structure is designed to become public alongside publication for full reproducibility.

#### Environment-Based Configuration

Instead of hardcoded paths, the package now uses a `.env` file to locate your project:

```bash
# .env (in experiment_analysis root, not committed to git)
PROJECT_REPO=/path/to/your-project-repo
```

#### New CLI Interface

```bash
# Run analysis for experiment 96
python -m src2.miniscope.miniscope_pipeline --line-num 96

# Run in headless mode (no GUI)
python -m src2.miniscope.miniscope_pipeline --line-num 96 --headless
```

#### New Functions

- `load_analysis_params(line_num)`: Load analysis parameters for an experiment
- `parse_analysis_params(params)`: Convert CSV columns to pipeline kwargs
- `ExperimentDataManager.get_pipeline_params()`: Get parameters formatted for pipeline.run()

---

## Migration Guide

### Step 1: Install python-dotenv

```bash
pip install python-dotenv
```

Or add to your environment:
```bash
conda install -c conda-forge python-dotenv
```

### Step 2: Create Your Project Repository

Create a new Git repository for your project:

```bash
mkdir my-sleep-study
cd my-sleep-study
git init
```

### Step 3: Create experiments.csv

Copy the relevant rows from the master experiments.csv into your project:

```csv
line number,id,date,calcium imaging directory,ephys directory,...
90,R230601A,2023-06-01,experiments/R230601A/miniscope,experiments/R230601A/ephys,...
91,R230602B,2023-06-02,experiments/R230602B/miniscope,experiments/R230602B/ephys,...
```

### Step 4: Create analysis_parameters.csv

Define your processing settings. Empty cells use pipeline defaults:

```csv
line number,filenames,crop,crop_square,detrend_method,run_CNMFE,n_processes
90,["0.avi"],true,"(131,430,471,110)",median,true,12
91,["0.avi"],true,"(100,400,450,120)",median,true,12
```

#### Available Columns

| Column | Type | Description |
|--------|------|-------------|
| `line number` | int | Links rows to experiments.csv |
| `filenames` | list | Video files to process, e.g., `["0.avi"]` |
| `crop` | bool | Enable cropping |
| `crop_square` | tuple | Crop coordinates `(x, y, w, h)` |
| `crop_with_crop` | tuple | Alternative crop coordinates |
| `detrend_method` | str | "median", "mean", or empty |
| `df_over_f` | bool | Compute ΔF/F |
| `parallel` | bool | Use multiprocessing |
| `n_processes` | int | Number of workers |
| `run_CNMFE` | bool | Run CNMF-E source extraction |
| `remove_components_with_gui` | bool | Interactive component curation |
| `find_calcium_events` | bool | Detect calcium transients |
| `event_height` | float | Peak detection threshold |
| `filter_data` | bool | Apply bandpass filter |
| `cut` | list | Filter cutoffs in Hz, e.g., `[0.1, 1.5]` |

For ephys:
| `channel_name` | str | Channel to analyze |
| `remove_artifacts` | bool | Apply artifact removal |
| `filter_type` | str | "butter", "fir", or empty |
| `filter_range` | list | Bandpass cutoffs |
| `compute_phases` | bool | Compute instantaneous phase |

### Step 5: Configure experiment_analysis

Create a `.env` file in the experiment_analysis root:

```bash
cd /path/to/experiment_analysis
cp .env.example .env
```

Edit `.env` to point to your project:

```bash
PROJECT_REPO=/path/to/my-sleep-study
```

### Step 6: Update Your Scripts

**Before (deprecated):**
```bash
python miniscope_pipeline.py --config my_config.yaml
```

**After:**
```bash
python -m src2.miniscope.miniscope_pipeline --line-num 90
```

**Before (in Python):**
```python
from src2.shared.config_utils import load_config, parse_miniscope_config

config = load_config("my_config.yaml")
params = parse_miniscope_config(config)
api.run(line_num=90, **params)
```

**After (in Python):**
```python
from src2.shared.config_utils import load_analysis_params

params = load_analysis_params(90)
api.run(line_num=90, **params)
```

Or using ExperimentDataManager:
```python
from src2.shared.experiment_data_manager import ExperimentDataManager

edm = ExperimentDataManager(90)
params = edm.get_pipeline_params()
api.run(line_num=90, **params)
```

---

## Switching Between Projects

To work on a different project, simply update your `.env`:

```bash
# Edit .env
PROJECT_REPO=/path/to/different-project

# Or use a one-liner
echo 'PROJECT_REPO=/path/to/different-project' > .env
```

---

## Creating a Batch Processing Script

Each project can include a `run_analysis.py` for batch processing:

```python
#!/usr/bin/env python3
"""Batch analysis script for my sleep study."""

from src2.miniscope.miniscope_pipeline import MiniscopePipeline
from src2.shared.config_utils import load_analysis_params

EXPERIMENTS = [90, 91, 92, 93]

def main():
    for line_num in EXPERIMENTS:
        print(f"\n{'='*50}")
        print(f"Processing experiment {line_num}")
        print('='*50)
        
        params = load_analysis_params(line_num)
        params['line_num'] = line_num
        params['headless'] = True  # No GUI for batch mode
        
        api = MiniscopePipeline()
        api.run(**params)

if __name__ == "__main__":
    main()
```

---

## Files Changed

| File | Change |
|------|--------|
| `.env.example` | **NEW** - Template for environment configuration |
| `.gitignore` | Added `.env` to prevent committing local paths |
| `src2/shared/paths.py` | Loads paths from environment variables |
| `src2/shared/config_utils.py` | Added `load_analysis_params()`, removed YAML functions |
| `src2/shared/experiment_data_manager.py` | Added `get_pipeline_params()` method |
| `src2/miniscope/miniscope_pipeline.py` | New CLI with required `--line-num` |
| `src2/ephys/ephys_pipeline.py` | New CLI with required `--line-num` |

---

## Questions?

If you encounter issues during migration, please check:

1. Is `PROJECT_REPO` set correctly in your `.env`?
2. Does your project's `experiments.csv` have the required columns?
3. Does `analysis_parameters.csv` have a `line number` column matching your experiments?

Run the paths diagnostic to verify your configuration:

```bash
python -c "from src2.shared.paths import *; print(f'PROJECT_REPO: {PROJECT_REPO}')"
```
