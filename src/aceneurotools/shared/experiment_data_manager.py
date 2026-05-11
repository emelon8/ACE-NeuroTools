"""
Experiment Data Manager

Manages the import and storage of experiment metadata and analysis parameters.
Loads from the active project repository via an explicit project_path argument.
"""

import logging
import warnings
from pathlib import Path
from typing import Any

from aceneurotools.shared.csv_worker import CSVWorker
from aceneurotools.shared.paths import PROJECT_ROOT


class ExperimentDataManager:
    """Manages experiment metadata and analysis parameters.
    
    This class loads data from two CSV files in the project repository:
    - experiments.csv: Experiment metadata (subject, date, directories, etc.)
    - analysis_parameters.csv: Processing settings for each experiment
    
    Both ``project_path`` and ``data_path`` should be supplied explicitly —
    either directly or via CLI flags / notebook variables. The optional
    ``ACE_NEUROTOOLS_DATA`` environment variable is honored as a last-resort
    default (see :mod:`aceneurotools.shared.paths`); there is no ``.env``
    file lookup.
    
    Attributes:
        line_num: The experiment line number.
        metadata: Dict of experiment metadata from experiments.csv.
        analysis_params: Dict of analysis parameters from analysis_parameters.csv.
    
    Example:
        >>> edm = ExperimentDataManager(
        ...     96,
        ...     project_path="/home/user/projects/my_project",
        ...     data_path="/data/raw"
        ... )
        >>> print(edm.metadata['id'])
        'R230706B'
    """

    def __init__(
        self,
        line_num: int,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        auto_import_metadata: bool = True,
        auto_import_analysis_params: bool = True,
        logging_level: str | int = logging.CRITICAL
    ) -> None:
        """Initialize the data manager for a specific experiment.
        
        Args:
            line_num: Experiment line number (matches 'line number' column in CSVs).
            project_path: Path to project directory containing metadata CSVs.
                Required for most workflows. Defaults to PROJECT_ROOT/data if
                not provided.
            data_path: Base path for raw experimental data.
                Defaults to PROJECT_ROOT/data/downloaded_data if not provided.
            auto_import_metadata: If True, load metadata from experiments.csv on init.
            auto_import_analysis_params: If True, load analysis params on init.
            logging_level: Logging verbosity ('DEBUG', 'INFO', 'WARNING', 'CRITICAL').
        """
        self.line_num: int = line_num
        if project_path is None:
            warnings.warn(
                "project_path was not provided; falling back to PROJECT_ROOT/data. "
                "Pass project_path explicitly to avoid unexpected FileNotFoundError.",
                UserWarning,
                stacklevel=2,
            )
        self.project_path: Path = Path(project_path) if project_path else PROJECT_ROOT / "data"
        self.data_path: Path = Path(data_path) if data_path else PROJECT_ROOT / "data" / "downloaded_data"

        self.metadata: dict[str, Any] | None = None
        self.analysis_params: dict[str, Any] | None = None
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.setLevel(logging_level)

        if auto_import_metadata:
            self.import_metadata()

        if auto_import_analysis_params:
            self.import_analysis_parameters()

    def import_metadata(self) -> None:
        """Load experiment metadata from project_path/experiments.csv.
        
        Populates self.metadata with converted data types. Directory paths
        are resolved relative to self.data_path.
        """
        experiments_csv = self.project_path / "experiments.csv"

        if not experiments_csv.exists():
            raise FileNotFoundError(
                f"Experiments file not found: {experiments_csv}\n"
                f"Did you forget to initialize your project data folder?\n"
                f"Please copy the `experiments_template.csv` from `aceneurotools.shared.metadata_templates` "
                f"into your project directory. See docs/guides/data_management.md for details."
            )

        metadata_unconverted = CSVWorker.csv_row_to_dict(experiments_csv, self.line_num)
        if metadata_unconverted is None:
            raise ValueError(f"Line {self.line_num} not found in {experiments_csv}")

        metadata_converted = CSVWorker.convert_data_types(metadata_unconverted)
        self.metadata = metadata_converted

        # Resolve directory paths
        if self.metadata.get('ephys directory'):
            self.metadata['ephys directory'] = self.data_path / Path(str(self.metadata['ephys directory']))
        if self.metadata.get('calcium imaging directory'):
            self.metadata['calcium imaging directory'] = self.data_path / Path(str(self.metadata['calcium imaging directory']))

    def import_analysis_parameters(self) -> None:
        """Load analysis parameters from project_path/analysis_parameters.csv.
        
        Populates self.analysis_params. If the file doesn't exist or the line
        number isn't found, sets analysis_params to an empty dict (allowing
        pipeline defaults to be used).
        """
        analysis_params_csv = self.project_path / "analysis_parameters.csv"

        if not analysis_params_csv.exists():
            self.logger.warning(
                f"No analysis_parameters.csv found at {analysis_params_csv}.\n"
                f"For full reproducible control, copy the `analysis_parameters_template.csv` "
                f"from `aceneurotools.shared.metadata_templates` into your project directory.\n"
                f"Falling back to built-in pipeline defaults..."
            )
            self.analysis_params = {}
            return

        analysis_params_unconverted = CSVWorker.csv_row_to_dict(analysis_params_csv, self.line_num)
        if analysis_params_unconverted is None:
            self.logger.info(
                f"Line {self.line_num} not found in {analysis_params_csv}. "
                f"Using pipeline defaults."
            )
            self.analysis_params = {}
            return

        analysis_params_converted = CSVWorker.convert_data_types(analysis_params_unconverted)
        self.analysis_params = analysis_params_converted

    def get_pipeline_params(self) -> dict[str, Any]:
        """Return analysis parameters formatted for pipeline.run().
        
        Converts the raw analysis_params dict to kwargs compatible with
        MiniscopePipeline.run() and EphysPipeline.run().
        
        Returns:
            Dict of kwargs to pass to pipeline.run()
        """
        from aceneurotools.shared.config_utils import parse_analysis_params
        return parse_analysis_params(self.analysis_params or {})

    def get_ephys_directory(self) -> Path | None:
        """Return the ephys directory path from metadata."""
        if self.metadata:
            val = self.metadata.get('ephys directory')
            return Path(val) if val else None
        return None

    def get_miniscope_directory(self) -> Path | None:
        """Return the miniscope/calcium imaging directory path from metadata."""
        if self.metadata:
            val = self.metadata.get('calcium imaging directory')
            return Path(val) if val else None
        return None
