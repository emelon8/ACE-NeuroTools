# Install and open ACE in the lab

**The lab's conda package channel has not been published yet.** The command
`conda create -n ace -c <channel> ace-neurotools` is a future distribution path,
not an installation command you can use today. Maintainer setup is tracked in
[issue #128](https://github.com/emelon8/ACE-NeuroTools/issues/128).

## For lab members

Ask the maintainer to prepare ACE on your computer using the source installation
below, or supply a tested package and its actual channel name. You also need:

- Your own practice copy of a project folder containing `experiments.csv`.
- A short recording with its original metadata and timestamp files.
- Suitable analysis settings and, for neuron review, the lab's acceptance criteria.
- Enough free space for copies of recordings and analysis results.

Once the maintainer has prepared the environment:

1. Open **Miniforge Prompt** on Windows, or a terminal on macOS/Linux.
2. Paste `conda activate aceneurotools` and press Enter.
3. Paste `ace-gui` and press Enter. ACE should open in your browser.
4. Keep that terminal open while working. If the browser does not open, copy the
   complete address printed after **Experiment application:**, including its token.
5. Follow [Use the experiment workbench](gui.md) or the [lab walkthrough](lab_walkthrough.md).

Repeat the activation and launch steps next time. Opening a browser bookmark
alone does not start ACE. Close ACE with Ctrl+C in its terminal after work has
finished. If your maintainer used a different environment name, use that name
in the activation command.

## For maintainers: install the current source

Install [Miniforge](https://github.com/conda-forge/miniforge#download) and
[Git](https://git-scm.com/downloads) first. In Miniforge Prompt on Windows, or a
terminal configured for conda on macOS/Linux, run these commands one at a time:

```sh
git clone https://github.com/emelon8/ACE-NeuroTools.git
cd ACE-NeuroTools
conda env create -f environment.yml
conda activate aceneurotools
python -m pip install --no-deps -e .
ace-gui
```

This creates the analysis environment from `environment.yml`, including the
neuroscience CaImAn package and Qt-enabled OpenCV. Do not install the unrelated
PyPI package named `caiman`, or replace conda's OpenCV with a headless build.
The root `conda-lock.yml` is the locked CI environment; see
[packaging](packaging.md) for reproducibility and installed-package checks.
Native platform support still needs acceptance testing on your lab's computers;
preparing an environment is not evidence that a full recording analysis works.

The source installation provides `ace-gui` but does not create the packaged desktop
shortcut. The conda recipe is designed to create that shortcut when the lab
package is published. Do not use the old Comenius ZIP setup scripts or assume
that the earlier **Open ACE Experiments** launch files match the installed app.

Before handing a computer to a tester, open their practice project, load a crop
preview, and complete a short analysis with the agreed settings. No ready-to-run
recording dataset is bundled. Setup downloads can take several minutes or longer;
large analyses need additional memory, time, and disk space.

## Once the lab package is published

The maintainer must replace the placeholder channel in the documentation with
the published name and test installation on a clean computer. At that point:

```sh
conda create -n ace -c <published-lab-channel> ace-neurotools
conda activate ace
ace-gui
```

These commands describe the future package path only. That installation is
intended to provide an **ACE NeuroTools** shortcut as well as `ace-gui`.
