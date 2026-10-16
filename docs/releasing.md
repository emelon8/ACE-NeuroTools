# Build and release the conda pilot

The Python distribution is `aceneurotools`; the conda package is
`ace-neurotools`. Both commands, `ace-neuro` and `ace-gui`, are installed by the
package. Version numbers come from git tags through setuptools-scm. Development
builds carry a `.dev` version. Release builds require a clean tagged checkout and
a matching version heading in `CHANGELOG.md`.

## Lab channel setup

There is no existing lab channel. Complete issue #128 before publishing:

1. Create a lab-owned Anaconda.org account/channel.
2. Set repository variable `LAB_CONDA_OWNER` to that account name.
3. Set `LAB_CONDA_TOKEN` in the GitHub `lab-conda` environment to a scoped upload
   token for that account. Keep credentials outside source files and CSVs.
4. Review the changelog, create an appropriate prerelease tag such as
   `v0.1.0a1`, and push it only after the ordered PR series is merged.

The Conda package workflow builds and tests on Windows, Intel Mac, Apple silicon
and Linux. Every platform builds a noarch Python package, runs import/CLI/GUI
checks, installs it using conda, and verifies menuinst metadata and native
shortcuts. Only after every platform succeeds does a tag upload the Linux-built
noarch artifacts to the lab channel. No force-overwrite is used. Normal PRs and
branch pushes never publish. This workflow replaces native installer jobs and
custom launcher scripts.

FreeSimpleGUI is not available from conda-forge. Its small companion recipe at
`recipe/freesimplegui/` builds the unmodified hash-pinned PyPI source for the lab
channel; it must be published alongside ACE. No pip command runs during conda
installation. CaImAn and Qt OpenCV are conda run dependencies. The recipe also
lists CaImAn's otherwise omitted Python metadata requirements.

## Local build

Install rattler-build, setuptools-scm and Python using conda-forge, then run:

```sh
export ACE_VERSION=$(python scripts/release_version.py)
rattler-build build --recipe recipe/freesimplegui -c conda-forge --output-dir conda-output
rattler-build build --recipe recipe -c ./conda-output -c conda-forge --output-dir conda-output
```

The same recipe is `noarch: python`; platform-specific CaImAn/OpenCV binaries are
resolved when the package is installed. CI exercises actual native installs,
not cross-compiled substitutes. Keep the root `conda-lock.yml` for the scientific
regression environment. Do not add installer locks or rendered environments.

## After the pilot is stable

Record lab feedback, update the changelog and tag a stable release. Submit a
recipe to conda-forge/staged-recipes using a versioned source archive and its
SHA-256 instead of the local `path` used for CI development builds. Submit the
FreeSimpleGUI prerequisite too if it is still absent. Follow conda-forge review;
do not publish a package to conda-forge directly.

References: [rattler-build recipes](https://rattler-build.prefix.dev/latest/reference/recipe_file/),
[menuinst shortcuts](https://conda.github.io/menuinst/defining-shortcuts/), and
[conda-forge staged recipes](https://github.com/conda-forge/staged-recipes).
