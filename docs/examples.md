# Examples and workflows

For browser-based analysis, use the [experiment workbench guide](gui.md).
[Create a project from the templates](gui.md#prepare-a-project) and use a short
supported recording with settings appropriate to your data.

## Command-line and Python examples

Read [Getting started](getting_started.md) for complete commands with recording
paths and the distinction between command defaults, saved settings and Python
arguments. [explicit_paths_demo.py](https://github.com/emelon8/ACE-NeuroTools/blob/main/examples/explicit_paths_demo.py) illustrates
explicit paths; its example paths must be replaced. A direct Python call does
not enable every processing step automatically.

## Supercomputer work

No ready-to-submit `submit_job.slurm` is included. Ask your cluster administrator
for its account, resource and environment requirements, and adapt a headless
modality command from Getting started. The installed GUI does not generate
cluster scripts. Resource requirements depend on the recording and settings;
there is no universal memory or time allocation.
After a cluster job saves CaImAn CNMF-E estimates, follow the
[cluster result import guide](guides/cluster_results.md) to register and review
the extraction or recompute component events locally.

## Notebooks

These need your recording and project files, including the settings file expected
by their setup cells. They are rendered without executing scientific analysis:

- [Miniscope tutorial](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Ephys tutorial](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal tutorial](notebooks/multimodal_alignment_tutorial.ipynb)

Before running a notebook locally, review paths, actual channel names and optional
processing settings. The [data guide](guides/data_management.md) describes optional
library/command-line Box access; download files separately for GUI use.
