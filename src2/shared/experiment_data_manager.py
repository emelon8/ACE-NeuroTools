#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Experiment Data Manager

Manages the import and storage of experiment metadata and analysis parameters.
Loads from the active project repository (configured via PROJECT_REPO in .env).
"""

import logging
from src2.shared.csv_worker import CSVWorker


class ExperimentDataManager:
    """Manages experiment metadata and analysis parameters.
    
    This class loads data from two CSV files in the active project repository:
    - experiments.csv: Experiment metadata (subject, date, directories, etc.)
    - analysis_parameters.csv: Processing settings for each experiment
    
    The project repository location is configured via the PROJECT_REPO
    environment variable (typically set in a .env file).
    
    Attributes:
        line_num: The experiment line number.
        metadata: Dict of experiment metadata from experiments.csv.
        analysis_params: Dict of analysis parameters from analysis_parameters.csv.
    
    Example:
        >>> edm = ExperimentDataManager(96)
        >>> print(edm.metadata['id'])
        'R230706B'
        >>> params = edm.get_pipeline_params()
        >>> api = MiniscopePipeline()
        >>> api.run(line_num=96, **params)
    """

    def __init__(
        self, 
        line_num: int,
        auto_import_metadata: bool = True,
        auto_import_analysis_params: bool = True,
        logging_level: str = "CRITICAL"
    ):
        """Initialize the data manager for a specific experiment.
        
        Args:
            line_num: Experiment line number (matches 'line number' column in CSVs).
            auto_import_metadata: If True, load metadata from experiments.csv on init.
            auto_import_analysis_params: If True, load analysis params on init.
            logging_level: Logging verbosity ('DEBUG', 'INFO', 'WARNING', 'CRITICAL').
        """
        self.line_num = line_num
        self.metadata: dict = None
        self.analysis_params: dict = None
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging_level)

        if auto_import_metadata:
            self.import_metadata()

        if auto_import_analysis_params:
            self.import_analysis_parameters()

    def import_metadata(self):
        """Load experiment metadata from PROJECT_REPO/experiments.csv.
        
        Populates self.metadata with converted data types. Directory paths
        are resolved relative to BASE_FILE_PATH.
        """
        from src2.shared.paths import EXPERIMENTS, BASE_FILE_PATH
        
        if not EXPERIMENTS.exists():
            raise FileNotFoundError(
                f"Experiments file not found: {EXPERIMENTS}\n"
                f"Make sure PROJECT_REPO is set correctly in your .env file."
            )
        
        metadata_unconverted = CSVWorker.csv_row_to_dict(EXPERIMENTS, self.line_num)
        if metadata_unconverted is None:
            raise ValueError(f"Line {self.line_num} not found in {EXPERIMENTS}")
        
        metadata_converted = CSVWorker.convert_data_types(metadata_unconverted)
        self.metadata = metadata_converted
        
        # Resolve directory paths
        if self.metadata.get('ephys directory'):
            self.metadata['ephys directory'] = BASE_FILE_PATH / self.metadata['ephys directory']
        if self.metadata.get('calcium imaging directory'):
            self.metadata['calcium imaging directory'] = BASE_FILE_PATH / self.metadata['calcium imaging directory']

    def import_analysis_parameters(self):
        """Load analysis parameters from PROJECT_REPO/analysis_parameters.csv.
        
        Populates self.analysis_params. If the file doesn't exist or the line
        number isn't found, sets analysis_params to an empty dict (allowing
        pipeline defaults to be used).
        """
        from src2.shared.paths import ANALYSIS_PARAMS
        
        if not ANALYSIS_PARAMS.exists():
            self.logger.info(
                f"No analysis_parameters.csv found at {ANALYSIS_PARAMS}. "
                f"Using pipeline defaults."
            )
            self.analysis_params = {}
            return
        
        analysis_params_unconverted = CSVWorker.csv_row_to_dict(ANALYSIS_PARAMS, self.line_num)
        if analysis_params_unconverted is None:
            self.logger.info(
                f"Line {self.line_num} not found in {ANALYSIS_PARAMS}. "
                f"Using pipeline defaults."
            )
            self.analysis_params = {}
            return
        
        analysis_params_converted = CSVWorker.convert_data_types(analysis_params_unconverted)
        self.analysis_params = analysis_params_converted

    def get_pipeline_params(self) -> dict:
        """Return analysis parameters formatted for pipeline.run().
        
        Converts the raw analysis_params dict to kwargs compatible with
        MiniscopePipeline.run() and EphysPipeline.run().
        
        Returns:
            Dict of kwargs to pass to pipeline.run()
        """
        from src2.shared.config_utils import parse_analysis_params
        return parse_analysis_params(self.analysis_params or {})

    def get_ephys_directory(self):
        """Return the ephys directory path from metadata."""
        return self.metadata.get('ephys directory')
    
    def get_miniscope_directory(self):
        """Return the miniscope/calcium imaging directory path from metadata."""
        return self.metadata.get('calcium imaging directory')