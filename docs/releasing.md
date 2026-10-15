# Releasing ACE-NeuroTools

Releases are immutable scientific artifacts. A paper should name an exact Git
tag and archive the matching environment, configuration, and input checksums.

## One-time repository setup

1. Reserve the `aceneurotools` project on PyPI.
2. Configure a PyPI Trusted Publisher for this repository, workflow
   `.github/workflows/release.yml`, environment `pypi`.
3. Connect the GitHub repository to Zenodo and enable release archiving.
4. Confirm the canonical repository and documentation URLs.
5. Create the repository variable `PUBLIC_ARCHIVE_APPROVED_TAG` but leave it
   unset until a particular release passes the publication-rights audit below.
   Configure required human reviewers for the `pypi` GitHub environment as a
   second approval gate.

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
   before pushing a tag or making the repository/Zenodo archive public. Five
   lab CSVs under `data/` are currently Git-tracked: they are excluded from the
   Python source distribution, but **not** from GitHub's tagged source archive.
   Remove or replace them in a future tag if they cannot be published; removing
   them from the latest tree alone does not erase older Git history.
6. Record checksums for the exact analysis inputs. Archive the analysis
   configuration and, where policy permits, the raw or derived data needed to
   reproduce the paper figures.

## Publish

After the audit, set `PUBLIC_ARCHIVE_APPROVED_TAG` to the exact intended tag,
then push an annotated tag matching `vMAJOR.MINOR.PATCH`. A tag without that
matching variable runs tests and validates packages but skips public
publication. The release workflow tests the locked environment, builds strict
documentation, validates the source distribution and wheel, publishes them to
PyPI using Trusted Publishing, and attaches them to a GitHub release. Zenodo
then archives that GitHub release. GitHub can expose a tagged source archive
as soon as the tag is pushed, so finish the rights audit **before** tagging.

After Zenodo finishes, add its version-specific DOI to the release notes and
the concept DOI to the next `CITATION.cff` update. Use the version-specific DOI
in the paper so reviewers can recover the exact code that produced the results.
