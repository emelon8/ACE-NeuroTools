# Config API

Everything the package reads from user-editable configuration files:
`lab_config.json` (lab identity, study design, paths, run settings),
`stats_config.json` (algorithm parameters), and the per-subject
`analysis_parameters.csv`.

## Lab configuration (`lab_config.json`)

::: aceneurotools.config.lab_config.LabConfig

::: aceneurotools.config.lab_config.ConditionSpec

## Algorithm parameters (`stats_config.json`)

::: aceneurotools.config.stats_config.StatsConfig

::: aceneurotools.config.stats_config.StudyMetadata

## Per-subject analysis parameters (`analysis_parameters.csv`)

::: aceneurotools.config.config_utils.load_analysis_params

::: aceneurotools.config.config_utils.parse_analysis_params

::: aceneurotools.config.config_utils.get_coords_dict_from_analysis_params
