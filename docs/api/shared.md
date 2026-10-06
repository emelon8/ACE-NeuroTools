# Shared Modules API

This section details the shared data structures and configuration utilities of the pipeline.

## Experiment Data Manager
::: aceneurotools.shared.experiment_data_manager.ExperimentDataManager

## Configuration helpers (`analysis_parameters.csv`)
::: aceneurotools.shared.config_utils.load_analysis_params

::: aceneurotools.shared.config_utils.parse_analysis_params

## Path Resolution
::: aceneurotools.shared.paths

## Misc Functions
::: aceneurotools.shared.misc_functions
    options:
      filters:
        - "!^_"
        - "!^load_obj$"

## Loading saved scientific objects

`load_obj(filename)` opens `.npz` arrays with `allow_pickle=False` and `.hdf5`/`.h5`
files as read-only HDF5 handles. Use the returned object as a context manager to
close the file after reading. Unsupported extensions, including pickle files,
raise `ValueError`.

```python
from aceneurotools.shared.misc_functions import load_obj

with load_obj("postprocessing.npz") as arrays:
    neuron_ids = arrays["neuron_ids"]
    filtered_signal = arrays["filtered_temporal_projection"]
```

::: aceneurotools.shared.misc_functions.load_obj
    options:
      docstring_style: null
      show_docstring_description: false
