# Contributing to ACE-NeuroTools

Bug reports and improvements are welcome through the
[issue tracker](https://github.com/emelon8/experiment_analysis/issues) and pull requests.
For bugs, include the version or commit, operating system, recording format,
command, and traceback. Use synthetic or de-identified examples and omit Box
credentials and tokens.

## Development environment

Use the environment in the [installation guide](README.md#installation).
The neuroscience CaImAn package comes from conda-forge; do not substitute the
unrelated PyPI package. The lock includes the testing and documentation tools.

```bash
micromamba activate aceneurotools
pip install --no-deps -e .
```

## Checks before a pull request

Run from the repository root:

```bash
ruff check .
ruff format --check .
pytest tests/ -m "not slow" -p no:cacheprovider
bash scripts/sync_notebooks_for_docs.sh
python scripts/check_docs_links.py
mkdocs build --strict
python -m build
python -m twine check dist/*
python scripts/check_distribution.py dist/*
```

Use `ruff format .` to apply formatting. Add regression tests for behavior
changes and update the affected guides or examples when changing public APIs.
Keep changes focused; describe the scientific effect of altered defaults or
processing algorithms in the pull request.

## Recording fixtures and scientific validation

Tests currently generate synthetic inputs. A full real-recording CNMF-E run is
not included in CI, and `scripts/create_test_data.py` is an unimplemented hook.
If adding a recording fixture, document its provenance, permission to redistribute,
recording format, expected results, and runtime. Keep large raw recordings and
locally generated results out of Git.

For scientific changes, also validate a representative recording locally and
record the configuration, software version, and result checks. A passing unit
test suite alone does not validate an analysis on experimental data.

## Releases and community

Follow the [release checklist](docs/releasing.md) for distribution and citation
metadata, and the [code of conduct](CODE_OF_CONDUCT.md) when participating.
