# Install ACE-NeuroTools in the lab

1. Install [Miniforge](https://github.com/conda-forge/miniforge#download).
2. Open the Miniforge prompt or terminal and run:

   ```sh
   conda create -n ace -c <channel> ace-neurotools
   ```

   Replace `<channel>` with the lab's published channel name. The lab channel
   has not been created yet; maintainer setup is tracked in issue #128. A
   development wheel is not a published conda pilot.
3. Launch **ACE NeuroTools** from the desktop/Start menu on Windows or the
   Applications menu on macOS/Linux. Alternatively:

   ```sh
   conda activate ace
   ace-gui
   ```

The package installs CaImAn and Qt OpenCV and creates the shortcut using
menuinst. No checkout, setup wizard or custom launcher is required. Keep the
application terminal open while using the browser. Its launch address contains
a private token; use that address to reopen the application. Each launch gets a
new token. Close the terminal with Ctrl+C when finished.

Download recordings from Box before selecting their local folder. Open your
project's `experiments.csv` folder in the workbench. See [the GUI guide](gui.md)
for editing settings, cropping, running analyses and reviewing results.
