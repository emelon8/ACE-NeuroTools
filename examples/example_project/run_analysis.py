#!/usr/bin/env python3
"""
Example batch analysis script for project-specific configuration.
This script demonstrates how to run analysis for multiple experiments defined in this project.
"""

import sys
import os
from pathlib import Path

# Add the project root to python path if running from this directory
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(project_root))

from src2.miniscope.miniscope_pipeline import MiniscopePipeline
from src2.shared.config_utils import load_analysis_params

# List of experiments to process (must exist in both experiments.csv and analysis_parameters.csv)
EXPERIMENTS = [96]

def main():
    print(f"Running analysis for project located at: {Path(__file__).parent}")
    
    for line_num in EXPERIMENTS:
        print(f"\n{'='*50}")
        print(f"Processing experiment {line_num}")
        print('='*50)
        
        try:
            # 1. Load parameters from the project's analysis_parameters.csv
            # Note: The PROJECT_REPO env var must point to this directory for this to work automatically
            # inside the pipeline. If not set, we can manually load params here.
            
            # Use the project directory where this script is located
            project_dir = Path(__file__).parent
            
            # Manually load params to demonstrate access (pipeline does this internally if PROJECT_REPO is set)
            params = load_analysis_params(line_num, project_path=project_dir)
            
            # 2. Add required runtime parameters
            params['line_num'] = line_num
            params['headless'] = True  # Run without GUI for batch processing
            
            # 3. Run the pipeline
            api = MiniscopePipeline()
            api.run(**params)
            
        except Exception as e:
            print(f"Error processing experiment {line_num}: {e}")

if __name__ == "__main__":
    main()
