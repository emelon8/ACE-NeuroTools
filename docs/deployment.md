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

## Read the Docs (hosted site)

Documentation is built and published by [Read the Docs](https://readthedocs.org/) using [`.readthedocs.yaml`](https://docs.readthedocs.io/en/stable/config-file/v2.html) at the repository root.

On each build, RTD:

1. Installs the package and documentation dependencies configured in `.readthedocs.yaml`.
2. Runs `scripts/sync_notebooks_for_docs.sh` so `docs/notebooks/` matches `notebooks/`.
3. Runs `mkdocs build` with `mkdocs.yml`.

**Project setup (dashboard):** import the GitHub repository in Read the Docs, connect the private repo if needed ([private repositories](https://docs.readthedocs.com/platform/latest/guides/creating-project-private-repository.html)), and point the default branch at your main docs branch. The canonical docs URL is configured in `mkdocs.yml` as `site_url` (currently `https://aceneurotools.readthedocs.io/en/latest/`). If your RTD project slug differs, update `site_url` and any hardcoded links accordingly.

**CI:** You can add a GitHub Actions workflow that runs `mkdocs build` on pushes and pull requests (without deploying); production hosting is typically Read the Docs.

## Updating tutorials

Edit files in `notebooks/`, regenerate or copy into `docs/notebooks/` with `scripts/sync_notebooks_for_docs.sh`, then commit.
