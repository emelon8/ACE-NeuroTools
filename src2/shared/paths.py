#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Path configuration for the experiment_analysis package.

Paths are loaded from environment variables (via .env file) to support
different project repositories and data locations across machines.

Setup:
    1. Copy .env.example to .env
    2. Set PROJECT_REPO to your active project's directory
    3. Optionally set BASE_FILE_PATH if data lives elsewhere
"""

from pathlib import Path
import os

# Load .env file if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed; rely on system environment variables

# Package root (experiment_analysis/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# =============================================================================
# Project Repository (from environment)
# =============================================================================
# Each project has its own repo with experiments.csv and analysis_parameters.csv
_project_repo_str = os.environ.get("PROJECT_REPO")

if _project_repo_str:
    PROJECT_REPO = Path(_project_repo_str)
else:
    # Fallback to legacy data/ directory for backward compatibility
    PROJECT_REPO = PROJECT_ROOT / "data"

# =============================================================================
# CSV File Paths
# =============================================================================
EXPERIMENTS = PROJECT_REPO / "experiments.csv"
ANALYSIS_PARAMS = PROJECT_REPO / "analysis_parameters.csv"

# Legacy alias for backward compatibility
DATA_DIR = PROJECT_ROOT / "data"

# =============================================================================
# Experimental Data Path
# =============================================================================
# Where the raw experimental data (videos, ephys files) are stored
_base_file_path_str = os.environ.get("BASE_FILE_PATH")

if _base_file_path_str:
    BASE_FILE_PATH = Path(_base_file_path_str)
else:
    BASE_FILE_PATH = PROJECT_ROOT / "data" / "downloaded_data"


# =============================================================================
# Diagnostic output (can be removed once stable)
# =============================================================================
if __name__ == "__main__":
    print(f"PROJECT_REPO:    {PROJECT_REPO}")
    print(f"EXPERIMENTS:     {EXPERIMENTS}")
    print(f"ANALYSIS_PARAMS: {ANALYSIS_PARAMS}")
    print(f"BASE_FILE_PATH:  {BASE_FILE_PATH}")