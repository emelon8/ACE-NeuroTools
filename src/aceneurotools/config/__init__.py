"""ACE-NeuroTools configuration subpackage.

Everything the package reads from user-editable configuration files lives
here, so there is a single place to look when adding or changing a setting.

Modules
-------
lab_config    — LabConfig / ConditionSpec / PathsConfig / RunConfig loaded from
                lab_config.json (lab identity, study design, paths, run mode).
stats_config  — StatsConfig (algorithm parameters from stats_config.json) and
                StudyMetadata (legacy study-design container).
config_utils  — Helpers for reading per-subject analysis_parameters.csv and
                mapping its columns onto pipeline keyword arguments.
"""

from aceneurotools.config.config_utils import load_analysis_params, parse_analysis_params
from aceneurotools.config.lab_config import ConditionSpec, LabConfig
from aceneurotools.config.stats_config import StatsConfig, StudyMetadata

__all__ = [
    "LabConfig",
    "ConditionSpec",
    "StatsConfig",
    "StudyMetadata",
    "load_analysis_params",
    "parse_analysis_params",
]
