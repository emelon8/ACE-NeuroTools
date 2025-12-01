#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Feb  1 14:27:32 2025

@author: lukerichards
"""

from pathlib import Path

# Define project root (assuming paths.py is in the project root or a config/ directory)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # Adjust ".parent" depth as needed

# Directory definitions
DATA_DIR = PROJECT_ROOT / "data"

# File paths 
ANALYSIS_PARAMS = DATA_DIR / "analysis_parameters.csv"  
EXPERIMENTS = DATA_DIR / "experiments.csv"
# Replace DATA_DIR / "downloaded_data" with a different path if you're storing your data elsewhere
BASE_FILE_PATH = DATA_DIR / "downloaded_data" 

print(ANALYSIS_PARAMS)