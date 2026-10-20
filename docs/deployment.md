# Build and publish the documentation

## Build locally

Use Python 3.10 or newer in a separate environment. No CaImAn installation or
recording dataset is needed: API pages are read from source, and notebooks are
rendered without running their analysis cells. From the repository root:

```sh
python -m pip install ".[docs]"
python scripts/check_docs_links.py
bash scripts/sync_notebooks_for_docs.sh
python -m mkdocs build --strict
python -m mkdocs serve
```

Open the address printed by `mkdocs serve`. Commit Markdown, configuration,
and notebooks in `notebooks/`; copied `docs/notebooks/`, `site/`, and caches are
build products. On Windows, run the notebook sync in Git Bash, or copy the three
`.ipynb` files from `notebooks/` into `docs/notebooks/` before building.

## Read the Docs

[ACE-NeuroTools](https://app.readthedocs.org/projects/ace-neurotools/) uses the
root `.readthedocs.yaml`: Python 3.10, installation of `.[docs]`, notebook sync,
local-link checking, and a strict MkDocs build. The published site is
[ace-neurotools.readthedocs.io](https://ace-neurotools.readthedocs.io/en/latest/).
The previous address without the hyphen is obsolete.

The docs extra in `pyproject.toml` is the installation source for both CI and
Read the Docs. PyMdown Extensions is constrained below 12.2 because newer
versions require a Markdown argument that mkdocstrings 1.0.x does not pass to
its highlighter. This caused the API-page crash in
[build 35277395](https://app.readthedocs.org/projects/ace-neurotools/builds/35277395/).
Change that compatibility constraint only after testing the complete API build
in a fresh environment. Installing unconstrained docs tools separately can
reintroduce the incompatible version.

CI installs the same docs extra in a fresh environment, checks local links, syncs
notebooks, and runs a strict build. A passing local build does not publish the
site; Read the Docs must build the merged commit successfully.
