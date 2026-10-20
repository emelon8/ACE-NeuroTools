# Install and open ACE

ACE runs on your computer and opens its interface in a web browser. The current
installation uses Miniforge to install the analysis tools, then installs ACE from
its Git repository. **A project conda package channel is not published yet.**
There is no current one-command package installation or source-install desktop
shortcut. Publication is tracked in [issue #128](https://github.com/emelon8/ACE-NeuroTools/issues/128).

## Before you begin

If ACE is already installed on your computer, go to [Open ACE again](#open-ace-again).
For a first installation, follow [Install from source](#install-from-source).
If you use a managed computer, you may need IT assistance to install prerequisites.

You can check that the interface opens without a recording. To test previews
and analysis, prepare:

- A writable project folder containing `experiments.csv` and,
  preferably, an `analysis_parameters.csv` file with settings for the same experiment IDs.
- A short supported recording with its original metadata and timestamp files.
- The experiment ID, settings appropriate to the recording, and expected outputs.
- Criteria for keeping or rejecting extracted neurons, if you will review them.

No ready-to-run recording dataset is bundled. Download Box recordings outside
ACE; the installed GUI does not connect to Box or download recordings.

## Install from source

Use a local desktop session on the computer that holds the recordings, rather than a remote
server. No Node.js, frontend build, separate web server, or separately installed
Python is needed.

### 1. Prepare your computer

Use an account allowed to install software and write to the chosen software,
project, and recording locations. Keep the computer online during installation.
Allow several gigabytes for the environment and download cache, plus space for
recordings, copies made by each run, and processing outputs. Required memory and
runtime depend on the recording; start with a short representative recording.

Install [Miniforge using its official instructions](https://github.com/conda-forge/miniforge#install).
Choose the installer matching your operating system and processor: Intel/AMD
Windows, Intel Mac, Apple silicon Mac, or your Linux architecture. Availability
of a Miniforge installer does not establish ACE support for that platform.
The checked-in scientific environment lock covers Linux x86-64 and Windows
x86-64; Mac installations resolve from `environment.yml`. Full recording analysis
still needs acceptance testing on your operating system and hardware.

- **Windows:** use the installer for your user account and its Start menu prompt.
  You do not need to add Miniforge to the system PATH. Open **Miniforge Prompt**
  for the commands below, rather than an unconfigured PowerShell window.
- **macOS/Linux:** follow Miniforge's shell initialization instructions, then
  close and reopen Terminal before continuing.

Install [Git](https://git-scm.com/downloads) too, then reopen your prompt or terminal
so it can find Git. If your computer is managed, ask IT to prepare these tools.

Run each command separately, pressing Enter after each. Copy only the command,
not the surrounding code fences:

```sh
conda --version
```

```sh
git --version
```

Both must print a version. Resolve errors before continuing.

### 2. Download ACE

Choose a permanent, writable parent folder for the ACE software, separate from
your project. Open a terminal in that folder, or type `cd ` followed by
its full path in double quotes. For example, `cd "C:\Users\YourName\Documents"`
on Windows or `cd "/Users/YourName/Documents"` on a Mac; replace the example path
with your actual folder.

```sh
git clone https://github.com/emelon8/ACE-NeuroTools.git
cd ACE-NeuroTools
```

The new `ACE-NeuroTools` folder must contain `environment.yml` and `pyproject.toml`.
Keep this folder in place: the editable installation below uses it whenever ACE
runs. These commands download the repository's default branch. If you need a
specific release or revision, select it before creating the environment and record
which revision you used.

Use this Git checkout for the steps below. Earlier ZIP setup scripts and
**Open ACE Experiments** launch files belong to a different pilot application.

### 3. Install the analysis environment and ACE

From inside `ACE-NeuroTools`, run:

```sh
conda env create -f environment.yml
```

Wait until the command finishes successfully and the prompt returns. Downloads
and dependency resolution may take several minutes or longer. If the command
fails, use [Troubleshooting](#troubleshooting); do not proceed with a partial setup.
If an `aceneurotools` environment already exists, follow
[Update an existing source installation](#update-an-existing-source-installation)
instead of deleting it.

```sh
conda activate aceneurotools
python -m pip install --no-deps -e .
```

The environment supplies the neuroscience **CaImAn >=1.13,<1.14** and Qt-enabled
OpenCV needed for movie processing. `--no-deps` keeps pip from replacing these
conda-managed tools. A pip-only ACE installation is insufficient for full analysis.
Do not install the unrelated PyPI package named `caiman` or replace OpenCV with
`opencv-python-headless`.

### 4. Check the installation

In the same activated environment, run:

```sh
python -m pip check
```

Expected result: `No broken requirements found.` Then run:

```sh
python -c "import caiman, cv2; from importlib.metadata import version; print('ACE:', version('aceneurotools')); print('CaImAn:', caiman.__version__); print('OpenCV:', cv2.__version__); print(next(line.strip() for line in cv2.getBuildInformation().splitlines() if line.strip().startswith('GUI:')))"
```

Expect version numbers and a GUI build entry containing Qt (for example, `QT5`),
without an import error. `GUI: NONE` indicates a headless OpenCV build and needs
repair before movie processing. These checks confirm dependencies can load;
they do not prove that an acquired recording can be analyzed.

To record the source revision used for this installation, also run:

```sh
git rev-parse HEAD
```

Save that revision and the printed versions with the computer's operating system
and processor type so you can identify the installation when reporting a problem.

### 5. Open the GUI

```sh
ace-gui
```

The terminal should print `Experiment application:` followed by a complete local
address, and ACE should open in your browser. If it does not open automatically,
copy that complete address into a browser **on this same computer**. It includes
`#token=...`, which the app needs to connect. Keep that address private and omit
the token from screenshots or problem reports.

Keep the terminal open while using ACE. The default port is 8765. If it is already
occupied, stop the extra ACE instance if appropriate, or run `ace-gui --port 8766`
and use the new printed address. Starting ACE again does not reuse the existing
server automatically.

An interface that opens without a project is expected. If you do not already
have a project, [prepare one from the templates](gui.md#prepare-a-project).
Choose **Open project** and select your project folder or its `experiments.csv`. If the system
picker is unavailable, use ACE's embedded folder browser. You do not need to
start ACE from inside the project folder.

Follow [Use the experiment workbench](gui.md) to select the local recording,
save its location, and load a crop preview. Relative recording paths also need
**Choose data base folder**; that selection must be repeated after restarting
ACE. Absolute recording paths saved in experiment details do not need it.

The workbench guide covers [running an analysis](gui.md#review-and-run-an-analysis)
and [finding saved outputs](gui.md#find-and-reopen-results). Start with a short
recording before processing a complete study. Neuron extraction, ephys, and
combined-recording analysis each require suitable inputs and settings.

## Open ACE again

Open Miniforge Prompt on Windows or your conda-enabled terminal on macOS/Linux:

```sh
conda activate aceneurotools
ace-gui
```

You can run these from any folder. Use the environment name chosen during
installation if it differs. Use the full printed address if the browser does not
open. After an ACE restart the token changes; a previous bookmark will not reconnect you. Reopen
your project to find saved runs in **Results**.

Closing the browser tab leaves the server and analyses running. To return while
the server is still running, use its existing printed address. To stop ACE, finish
or stop any active analysis in the app first, then press **Ctrl+C** in its terminal
(on Mac too). After restarting your computer, repeat the two launch commands.
Keep the computer awake and the terminal open during analysis.

## Update an existing source installation

Record your current source revision before updating. If you collaborate with
others, agree on the revision to use for shared analyses. Finish
or stop running analyses, stop ACE with Ctrl+C, and keep backups of project files
and results before updating. In a conda-enabled terminal, enter the original
`ACE-NeuroTools` software folder and run:

```sh
git status --short
```

If this lists local changes, save or commit them before updating. Ask for help
if you are unsure how to preserve them; do not discard them to force an update.
For a clean checkout on the intended branch, run each command separately:

```sh
git pull --ff-only
conda activate aceneurotools
conda env update -n aceneurotools -f environment.yml
python -m pip install --no-deps -e .
```

If Git refuses the update or any installation step fails, stop and send the error
when [reporting an installation problem](#report-an-installation-problem).
For an incomplete first installation, use
`conda env list` to check whether the environment exists, then either retry
`conda env create -f environment.yml` if absent or use the environment update
command above if present. Do not delete an existing environment as a first remedy.

Repeat [the installation checks](#4-check-the-installation), launch ACE, and retry
a short analysis after an update. If you move the source folder, run
the editable pip installation command from its new location in the activated
environment, then repeat the checks.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| `conda` is not found | On Windows, open Miniforge Prompt. On Mac/Linux, complete Miniforge shell initialization and reopen Terminal; report the error if it still fails. |
| `git` is not found | Install Git and reopen the prompt or terminal. |
| Destination folder already exists during clone | Check the existing checkout and its revision before reusing it, or choose another parent folder. Do not overwrite it. |
| `environment.yml` not found or pip reports no Python project | Enter the downloaded `ACE-NeuroTools` folder containing both `environment.yml` and `pyproject.toml`. |
| Environment already exists | Follow the update instructions. |
| Download, certificate, or dependency-resolution error | Save the complete error and check connectivity. Ask IT about managed network/certificate settings and report dependency-resolution errors with your platform details. Resolve the failure before continuing. |
| `conda activate` asks for initialization | Follow Miniforge's shell initialization instructions, close and reopen the terminal, then retry. |
| `ace-gui` is not found | Activate the environment used for setup. Run `python -m pip show aceneurotools`. If missing, return to the software folder and repeat the editable pip install. |
| ACE worked before the software folder was moved or deleted | Restore the checkout, or install from its new permanent location in the same activated environment. |
| Missing modules, broken requirements, or OpenCV has `GUI: NONE` | Include the dependency-check output in your installation report. Restore the environment from `environment.yml`; do not try unrelated pip packages as replacements. |
| Address already in use | Reopen the running instance using its printed address, or choose another port with `ace-gui --port 8766`. |
| Browser cannot connect | Confirm the terminal still runs ACE, then copy its complete printed local address into a browser on the same computer. |
| Browser asks you to reopen ACE | Use the current launch address including its token, rather than a bookmark from an earlier launch. |
| Project opens but recording is missing | Download the recording first, then choose its local recording folder or data base folder as described in the workbench guide. |
| No desktop shortcut | This is expected for the source installation. Use the two launch commands above. |

## Report an installation problem

[Open a GitHub issue](https://github.com/emelon8/ACE-NeuroTools/issues) or ask your
existing support contact for help. Include the step and exact command that failed,
the error text, operating system and processor type, and outputs from
`conda env list`, `python --version`, and `python -m pip show aceneurotools` when
available. Include the dependency-check output and source revision if you reached
those steps. Remove the private launch token. For analysis failures, also include
the experiment ID, analysis name, and the run's `run.log` from **Results**.

## Package availability

The future conda package is intended to provide an **ACE NeuroTools** shortcut as
well as `ace-gui`. Its channel and installation command must be published and
validated before replacing the source steps here. Until then, use the source
installation above. Package building and publication are described separately in
[the release guide](releasing.md#package-channel-setup).

See [packaging](packaging.md) for the locked CI environment and installed-package
checks, and [conda's environment guide](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html)
for environment management.
