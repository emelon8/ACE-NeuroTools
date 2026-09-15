# Releasing ACE-NeuroTools

Releases are immutable scientific artifacts. A paper should name an exact Git
tag and archive the matching environment, configuration, and input checksums.

## One-time repository setup

1. Reserve the `aceneurotools` project on PyPI.
2. Configure a PyPI Trusted Publisher for this repository, workflow
   `.github/workflows/release.yml`, environment `pypi`.
3. Connect the GitHub repository to Zenodo and enable release archiving.
4. Confirm the canonical repository and documentation URLs.

## Prepare a release

1. Choose a semantic version and update it in `pyproject.toml`,
   `src/aceneurotools/__init__.py`, and `CITATION.cff`.
2. Add the actual release date to `CITATION.cff` and move relevant changelog entries
   out of `Unreleased`.
3. Generate and commit platform lock files:

   ```bash
   conda-lock lock --micromamba -f environment.yml \
     -p linux-64 -p win-64 -p osx-64 -p osx-arm64
   ```

   The current lock covers Linux and Windows. Do not claim macOS release
   support until both macOS platforms resolve and pass smoke tests.

4. Recreate an environment from the relevant lock, install the checkout with
   `pip install --no-deps -e .`, and run:

   ```bash
   pytest tests
   ruff check src tests
   ruff format --check src tests
   pyrefly check
   python -m build
   python -m twine check dist/*
   ```

5. Review `data/`, `configs/`, notebooks, and Git history for publication rights
   before making the repository or Zenodo archive public. The source
   distribution intentionally excludes lab data under `data/`.
6. Record checksums for the exact analysis inputs. Archive the analysis
   configuration and, where policy permits, the raw or derived data needed to
   reproduce the paper figures.

## Publish

Push an annotated tag matching `vMAJOR.MINOR.PATCH`. The release workflow
builds and validates the source distribution and wheel, publishes them to PyPI
using Trusted Publishing, and attaches them to a GitHub release. Zenodo then
archives that GitHub release.

After Zenodo finishes, add its version-specific DOI to the release notes and
the concept DOI to the next `CITATION.cff` update. Use the version-specific DOI
in the paper so reviewers can recover the exact code that produced the results.
