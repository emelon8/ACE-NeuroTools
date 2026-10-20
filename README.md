# ACE-NeuroTools: Calcium imaging and electrophysiology

**[Read the documentation](https://ace-neurotools.readthedocs.io/en/latest/)** ·
[Install and open ACE](https://ace-neurotools.readthedocs.io/en/latest/gui_installation/) ·
[First-run walkthrough](https://ace-neurotools.readthedocs.io/en/latest/lab_walkthrough/)

ACE turns supported calcium movies and electrical brain recordings into analysis
results. Use the local browser application to edit experiment details, crop
movies, review and run analyses, inspect extracted neurons, and find saved results.

**Start here:** begin with [Install and open ACE](docs/gui_installation.md), then
[Use the experiment workbench](docs/gui.md) and the
[first-run walkthrough](docs/lab_walkthrough.md). A project package channel is not
yet published; follow the source installation guide. No ready-to-run recording
dataset is bundled.

## What it does

| Workflow | Inputs | Available processing |
| --- | --- | --- |
| Calcium imaging | Supported UCLA/ONIX miniscope movies, metadata and timestamps | Cropping, normalization, motion correction, CNMF-E cell extraction and event detection, depending on settings |
| Electrophysiology | Neuralynx or RHS2116/ONIX recordings | Channel import and requested artifact removal, filtering and phases |
| Combined recordings | Calcium and electrical recordings with synchronization information | Timestamp alignment and requested event comparisons |

This is alpha research software. Validate representative recordings and review
scientific results before using them in a report. Record the software revision
and settings with the study; see [CITATION.cff](CITATION.cff) for citation metadata.

## Install from source

Install Miniforge and Git, then run in a conda-enabled terminal:

```sh
git clone https://github.com/emelon8/ACE-NeuroTools.git
cd ACE-NeuroTools
conda env create -f environment.yml
conda activate aceneurotools
python -m pip install --no-deps -e .
ace-gui
```

The [step-by-step installation guide](docs/gui_installation.md) covers choosing
Miniforge, dependency checks, first launch, reopening, updates, and recovery.
Use that guide for a first installation; the commands above are a quick reference.
The source install does not create a desktop shortcut. `environment.yml` supplies the
neuroscience CaImAn package and Qt OpenCV. A pip-only install cannot run the full
analysis, and the project named `caiman` on PyPI is unrelated. The root
`conda-lock.yml` reproduces the CI environment; see [packaging](docs/packaging.md).

Keep the application terminal open. If the browser does not open, use the full
printed launch address, including its token. The server defaults to
`127.0.0.1:8765`; choose another port with `ace-gui --port 8766`.

## Prepare a project and run an analysis

The GUI opens a folder containing `experiments.csv`; `analysis_parameters.csv`
stores optional settings for matching experiment IDs.
[Create your project from the supplied templates](docs/gui.md#prepare-a-project),
then select a short supported recording and settings appropriate to your data.
Download Box recordings outside ACE and select their local folder. The installed GUI has no Box setup/download
service, cluster-script export, or connected experiment revision history.

Each GUI run copies its inputs and writes separate outputs under
`<project>/.ace-runs/<run-id>/`. Repeating a run preserves previous results.
The [workbench guide](docs/gui.md) explains saving edits, drawing a crop, mandatory
run review, cancellation, result files, and neuron review/event export.

For command-line analysis, replace the paths and ID with your own:

```sh
python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data --headless
python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data --headless
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project --data-path /path/to/raw_data --headless
```

The ID matches the `line number` column; it is not a spreadsheet row position.
Commands merge shared defaults and recognized saved settings. Direct Python
`run()` calls use explicit arguments and method defaults; they do not
automatically merge CSV run switches. Calcium Python calls default to no CNMF-E
extraction; the command enables extraction and selects `0.avi` by default.
Read [Getting started](docs/getting_started.md) before copying these commands.

Shared analysis uses `CalciumImaging…` names; historical `Miniscope…` imports and
the old module command remain aliases. Hardware readers retain Miniscope names.
See [naming and acquisition formats](docs/guides/calcium_imaging.md#naming-and-acquisition-formats).

## Documentation and examples

- [Documentation home](docs/index.md) and [hosted documentation](https://ace-neurotools.readthedocs.io/en/latest/)
- [Calcium imaging](docs/guides/calcium_imaging.md), [ephys](docs/guides/ephys.md), and [combined recordings](docs/guides/multimodal.md)
- [Data organization](docs/guides/data_management.md), [examples](docs/examples.md), and [API reference](docs/api/index.md)
- [Build and preview the docs](docs/deployment.md)

## Development and testing

Tests generate small synthetic inputs. `tests/data/sample_recording/` is not a
bundled dataset, and `scripts/create_test_data.py` is an unimplemented hook.
The ordinary suite does not establish that a complete acquired recording analysis
works on every computer. In the prepared analysis environment:

```sh
python -m pytest tests/ -m "not slow"
```

CI runs this selection in the locked environment and checks the installed wheel,
GUI assets, and documentation. See [backend testing](docs/backend_testing.md),
[packaging](docs/packaging.md), and [releasing](docs/releasing.md) for development and packaging.

## License

ACE-NeuroTools is licensed under GPL-3.0-or-later; see [LICENSE](LICENSE).
CaImAn permits GPLv2 or later; ACE uses that option under GPL-3.0-or-later.
