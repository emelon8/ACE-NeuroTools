# Install and open ACE Experiments

Use this guide for the lab pilot on **Windows 10/11 with an Intel/AMD processor**
or **macOS 11 or newer, on either an Apple silicon or Intel Mac**. You will install
one prerequisite, download ACE, and run setup once. After setup, open ACE by
double-clicking its launch file. You do not need Git or a separate Python install.

This is a pilot installation from the Comenius checkout, before PyPI GUI releases.
The automated installation checks exercise a small movie and the local server.
They do not establish that every recording format or full neuron extraction works
on every machine. Test a short lab recording before processing a large dataset.

## Before you start

- Use a computer where you can install software. If your lab computer is managed,
  ask your IT team to install Miniforge for your user account.
- Keep the computer connected to the internet and plugged in during setup.
- Allow several gigabytes for the analysis environment and its download cache.
  Recordings and analysis outputs need additional space. Your lab's maintainer
  should help choose an appropriate computer for large analyses.
- Have your lab's project folder available. It must contain `experiments.csv`.
  Ask for the project and a short test recording if you have not received them.

## Windows: one-time setup

### 1. Install Miniforge

Download the [Windows Miniforge installer](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe).
Miniforge installs the tools ACE needs to create its analysis environment.

Open the downloaded installer. Choose **Just Me**, keep its default installation
folder, and retain **Create Start Menu shortcuts**. Leave **Add Miniforge to PATH**
unchecked. Finish the installer.

Open the Start menu, type **Miniforge Prompt**, and open it. This is the window
where you will paste the commands below; use it instead of PowerShell.

Paste this command and press Enter:

```text
conda --version
```

You should see `conda` followed by a version number. If Windows cannot find the
command, confirm that you opened **Miniforge Prompt**.

### 2. Download and extract ACE

Download the [ACE pilot ZIP](https://github.com/emelon8/ACE-NeuroTools/archive/refs/heads/proj-comenius.zip),
or use the ZIP supplied by your lab's maintainer. Right-click the ZIP, choose
**Extract All**, and put the extracted folder somewhere you will keep it, such
as Documents. Do not run setup inside the ZIP, and avoid a cloud-synced folder.

Open the extracted folder in File Explorer. You should see `README.md`, `scripts`,
`gui`, and `installer`. If you see only another folder, open that folder first.

Click File Explorer's address bar and copy the full folder location. In Miniforge
Prompt, type `cd /d `, then paste that location between double quotes and press
Enter. For example:

```text
cd /d "C:\Users\YOUR-NAME\Documents\ACE-NeuroTools-proj-comenius"
```

Replace the example location with the one you copied. Quotes keep spaces in a
folder name together.

### 3. Run setup

Paste these commands, pressing Enter after each:

```text
conda activate base
python scripts\setup_gui.py
```

Setup selects the Windows packages, creates ACE's separate analysis environment,
installs ACE, and tests movie reading and the local GUI server. Downloads can take
several minutes or longer. Keep the window open until setup finishes.

Successful setup ends with **ACE setup complete. Double-click:** and the location
of **Open ACE Experiments.cmd**. If you see **Setup did not finish**, go to
[If something goes wrong](#if-something-goes-wrong).

### 4. Open ACE

In the extracted ACE folder, double-click **Open ACE Experiments.cmd**. A launch
window briefly opens, and your usual browser should show **ACE Experiments** at
`http://127.0.0.1:8780/`.

This address belongs to the application running on your computer. Opening the
browser does not upload your recordings. If the browser does not open, enter
that address yourself. If the launch window shows an error, keep it open and
follow the troubleshooting section.

## Mac: one-time setup

### 1. Choose and install Miniforge

Open the Apple menu and choose **About This Mac**:

- If it says **Chip: Apple M1/M2/M3/M4/...**, download the
  [Apple silicon Miniforge installer](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.pkg).
- If it says **Processor: Intel**, download the
  [Intel Miniforge installer](https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.pkg).

Open the `.pkg` installer and follow its screens. Keep the default location and
enable **conda initialization for your shell** in the installer options
(look under **Customize** if needed). This makes Miniforge available in Terminal.
Use the installer for your actual Mac type; Apple silicon users should use the
native installer, without running Terminal through Rosetta.

Quit any open Terminal windows. Press Command-Space, type **Terminal**, and open
it. Paste this command and press Return:

```bash
conda --version
```

You should see `conda` followed by a version number. If it says `command not
found`, stop and see troubleshooting before continuing.

### 2. Download and extract ACE

Download the [ACE pilot ZIP](https://github.com/emelon8/ACE-NeuroTools/archive/refs/heads/proj-comenius.zip),
or use the ZIP supplied by your lab's maintainer. Double-click it to extract it.
Move the extracted ACE folder to a permanent location, such as a local folder
in your home directory. Avoid iCloud-synced folders.

Open that folder in Finder. You should see `README.md`, `scripts`, `gui`, and
`installer`. If you see only another folder, open that folder first.

In Terminal, type `cd ` including the space, then drag the ACE folder from Finder
into the Terminal window. Press Return. Dragging fills in its location, including
any spaces; you do not need to type a path.

### 3. Run setup

Paste these commands, pressing Return after each:

```bash
conda activate base
python scripts/setup_gui.py
```

Setup selects packages for your Mac's processor, creates ACE's separate analysis
environment, installs ACE, and tests movie reading and the local GUI server.
Keep the window open during downloads and installation.

Successful setup ends with **ACE setup complete. Double-click:** and the location
of **Open ACE Experiments.command**. If you see **Setup did not finish**, follow
the troubleshooting section.

### 4. Open ACE

In Finder, double-click **Open ACE Experiments.command** in the ACE folder. It
opens a Terminal window and then the GUI in your usual browser at
`http://127.0.0.1:8780/`. If the browser does not open, enter that address yourself.

macOS may ask you to approve opening this downloaded launch file. Follow your
computer's normal security approval process for the code supplied by your lab.
If approval is unavailable, ask your IT team. You can also launch from the
Terminal window used for setup:

```bash
conda activate base
python scripts/start_gui.py
```

After a successful launch, you may close its launch window. The analysis server
runs separately. A window showing a launch error should be kept open so you can
report the message.

## Open your project and check the installation

1. Choose **Open project** in ACE.
2. Select the lab project folder containing `experiments.csv` and confirm it.
3. Select one experiment. Check that its subject, date, and recording location
   match the recording your lab supplied.
4. In **Data & settings**, choose the local recording folder if the stored
   location belongs to another computer. Save your changes.
5. Load a recording preview in **Crop**. A visible movie frame confirms that ACE
   can read this recording on your machine.

Ask the maintainer for analysis settings suitable for the short recording, then
follow the [Experiment GUI guide](guides/experiment_gui.md) for analysis and
review. The bundled `data` folder is not a ready-to-run demonstration project.
ACE starts with no project selected so you can choose your own lab project.

## Open ACE again tomorrow

Double-click **Open ACE Experiments.cmd** (Windows) or **Open ACE
Experiments.command** (Mac). You do not need to run setup or activate Miniforge
again. Reopening the launch file reuses an already-running ACE server.

Closing the browser tab does not stop analysis. Keep the computer awake during
a run. After restarting your computer, use the same launch file again and reopen
your project. Previous completed runs remain in the project's history.

Keep the extracted ACE folder in place. If you move it or download an updated
copy, repeat the setup command from that folder to refresh its installation and
launch file. Rerunning setup updates ACE's dedicated environment and does not
delete your recordings or completed results.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| `conda` is not recognized on Windows | Use **Miniforge Prompt** from the Start menu. |
| `conda: command not found` on Mac | Quit and reopen Terminal. Confirm shell initialization was enabled in Miniforge's installer. If it still fails, ask the lab maintainer to check the Miniforge location and shell setup. |
| `can't open file ... setup_gui.py` | The terminal is in the wrong folder. Repeat the folder selection step; the selected folder must contain `scripts`. |
| Download or network error | Check the internet connection, then rerun setup from the same folder. Do not continue to analysis after a failed setup. |
| `Setup did not finish` | Send the maintainer the last error message and `setup.log` from the ACE folder. Include Windows/Mac version and, for Mac, Intel or Apple silicon. |
| No launch file appeared | Setup has not finished successfully. Check its last message and `setup.log`. |
| Browser cannot connect | Run the ACE launch file first. A browser bookmark alone cannot start the server. If launching reports an error, send that message to the maintainer. |
| Saved environment cannot be found | Run setup again from the extracted ACE folder. |
| Address/port already in use | From the setup terminal, run `python scripts/start_gui.py --port 8781`; open the address printed there. |
| Project opens but recordings are missing | Stored paths may belong to another computer. Choose your recording folder in **Data & settings**, save, and retry the preview. |
| System folder picker does not open | Use ACE's embedded folder browser to select the project or recording. |

For help installing Miniforge itself, see its
[official installation instructions](https://github.com/conda-forge/miniforge#install).
