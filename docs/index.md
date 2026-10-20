# ACE-NeuroTools

ACE turns calcium movies and electrical brain recordings into analysis results.
A miniscope records cell activity as video; electrophysiology records electrical
signals from channels. ACE can process each and align recordings made together.

## Start here

- [Install and open ACE](gui_installation.md): current installation status and launch steps.
- [Use the experiment workbench](gui.md): project editing, cropping, analysis, neuron review, and saved results.
- [Command-line getting started](getting_started.md): project files and complete command examples.

Prepare a project using [the CSV templates](gui.md#prepare-a-project), recordings
with their companion files, and settings appropriate to your data. A recording
dataset is not bundled. A project conda package channel is still pending; follow
the source installation guide, which includes dependency and first-launch checks.

## Analysis guides

- [Calcium imaging](guides/calcium_imaging.md)
- [Electrophysiology](guides/ephys.md)
- [Combined-recording alignment](guides/multimodal.md)
- [Data organization and optional command-line Box access](guides/data_management.md)

The GUI saves separate results for each run. Its History screen, Box setup, and
cluster-script export are not connected. Scientific processing depends on the
selected options; validate a short representative recording before a large study.

## Notebooks and developer reference

The notebooks need your own recording and project files. They are examples,
not a bundled demonstration dataset:

- [Miniscope tutorial](notebooks/miniscope_pipeline_tutorial.ipynb)
- [Ephys tutorial](notebooks/ephys_pipeline_tutorial.ipynb)
- [Multimodal tutorial](notebooks/multimodal_alignment_tutorial.ipynb)

See the [API reference](api/index.md), [packaging](packaging.md),
[release checklist](releasing.md), and [documentation build guide](deployment.md).
