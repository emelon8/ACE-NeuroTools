# Previewing and publishing documentation (maintainers)

## What gets committed

- **Source:** `docs/` (Markdown, API stubs, assets), `mkdocs.yml`, and tutorial notebooks under `notebooks/` (synced into `docs/notebooks/` before a build).
- **Not committed:** `site/` (MkDocs HTML output) and `.cache/` (mkdocs-jupyter cache). Both are listed in `.gitignore`.

## Local preview

```bash
micromamba create -n aceneurotools -f conda-lock.yml  # Linux or Windows
micromamba activate aceneurotools
pip install --no-deps -e .
bash scripts/sync_notebooks_for_docs.sh
python scripts/check_docs_links.py
mkdocs serve
```

The committed lock covers Linux and Windows. On macOS, create the environment
from `environment.yml` instead; that platform is not covered by the lock.

Open the URL MkDocs prints (usually `http://127.0.0.1:8000`).

Before committing documentation, also check the complete static build:

```bash
bash scripts/sync_notebooks_for_docs.sh
mkdocs build --strict
```

The notebook sync copies source notebooks; it does not execute them. The build
validates documentation navigation and links and renders API references from
local Python source. A successful build verifies rendering, not scientific
results from the example analyses.

The published navigation includes the experiment GUI guide and current design
notes. Guides link to other pages within `docs/`; references to repository source
outside that directory use GitHub links so they also work in the generated site.

## Read the Docs (hosted site)

Documentation is built and published by [Read the Docs](https://readthedocs.org/) using [`.readthedocs.yaml`](https://docs.readthedocs.io/en/stable/config-file/v2.html) at the repository root.

On each build, RTD:

1. Installs the docs dependencies from `docs/requirements.txt`. It does not install the package itself, because CaImAn is only available from conda-forge; mkdocstrings reads the API from `src/`. Keep that file in sync with the `docs` extra in `pyproject.toml`.
2. Runs `scripts/sync_notebooks_for_docs.sh` so `docs/notebooks/` matches `notebooks/`.
3. Runs `mkdocs build` with `mkdocs.yml`.

**Hosting status:** the previously advertised
`https://aceneurotools.readthedocs.io/en/latest/` returned HTTP 404 during the
2026-10-05 audit. Repository documentation and local previews are available.

**Project setup (dashboard):** import the GitHub repository in Read the Docs,
select the branch to publish, and complete a successful build. Verify the
public address before adding `site_url` to `mkdocs.yml` and updating the package
metadata and documentation links. The checked-in RTD configuration alone does
not establish a live site.

**CI:** The existing GitHub Actions workflow runs the local link checker and
`mkdocs build --strict` on pushes and pull requests targeting `main`. Read the
Docs manages hosted publication separately.

## Updating tutorials

Edit files in `notebooks/`, then regenerate or copy into `docs/notebooks/` with
`scripts/sync_notebooks_for_docs.sh` before preview/build. Commit the source
notebooks, rather than their ignored generated copies in `docs/notebooks/`.
