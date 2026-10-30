# Package installation and dependencies

For first-time installation, use [Install and open ACE](gui_installation.md).
The current source route includes dependency checks, first launch, reopening,
updates, and troubleshooting. The source installation creates command-line
entry points, but no desktop shortcut; shortcuts belong to the future conda
package. A successful HTTP smoke check does not verify movie processing or a
full acquired-recording analysis.

`ace-neuro` launches the command-line tools. `ace-gui` opens the installed local
browser application on **127.0.0.1:8765**. Use `ace-gui --port 0 --no-browser` to
allocate an available port for an automated check, or choose a different port.
The application and its HTML, JavaScript, CSS and assets live inside
`aceneurotools.gui`; launching does not depend on the current working directory.

The application browses CSV projects, previews crops, edits settings and runs
analysis in private run folders. With the optional Box SDK installed, the GUI
can connect to Box and download selected recording files. Cluster-script export
is deferred.

## Scientific prerequisites

The full analysis environment requires **CaImAn >=1.13,<1.14** and
**Qt-enabled OpenCV >=4.6**, installed with conda-forge. `environment.yml` lists
these prerequisites explicitly. The PyPI project `caiman` is unrelated software;
it is deliberately absent from Python package metadata. CaImAn calls
`cv2.destroyAllWindows()` while reading AVI files, including in headless runs;
a headless OpenCV build cannot satisfy that operation.

`opencv-python` is absent from the default pip requirements to prevent pip from
overwriting the conda OpenCV installation. For core-only pip workflows, install
`aceneurotools[pip-opencv]` explicitly. This does not install CaImAn or replace the
full conda environment. In conda environments install the wheel with `--no-deps`.

## Reproducibility and installed-package smoke test

The root `conda-lock.yml` is the only checked-in lock. CI creates its environment
from that file; no installer-specific lock or rendered per-platform environment
is maintained. `environment.yml` is the human-edited environment specification.

```sh
python -m build
python scripts/smoke_installed_package.py --wheel dist/<built-wheel>.whl
```

The smoke check creates a clean temporary environment, installs the built wheel,
and launches its installed `ace-neuro` and `ace-gui` commands from outside the
checkout. It checks packaged assets and the live HTTP health endpoint, then
stops the server. The installed GUI uses the runtime dependencies declared by the wheel.
