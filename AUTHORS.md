# Authors

This file records the people who designed, wrote, and maintain ACE-NeuroTools.
For the canonical machine-readable form, see [`CITATION.cff`](CITATION.cff)
and the `[project.authors]` table in [`pyproject.toml`](pyproject.toml).

When adding to this file, prefer GitHub handles and ORCID iDs over personal
email addresses; do not commit information without the person's permission.
TODO(humans) markers below are placeholders that the listed people should
fill in themselves.

## Authors (`pyproject.toml [project.authors]`)

These are the authors who currently appear in the package metadata and on
PyPI / conda-forge listings.

- **Reed Pennock**
  - Email: TODO(humans)
  - ORCID: TODO(humans)
  - Affiliation: TODO(humans)
  - GitHub: TODO(humans) — confirm whether this is `reedpen` (per
    `https://github.com/reedpen/ace.git` remote and the paper-outline
    `reedpen/example-project` reference) or another handle.
- **Luke Richards**
  - Email: TODO(humans)
  - ORCID: TODO(humans)
  - Affiliation: TODO(humans)
  - GitHub: TODO(humans)
- **Eric Melonakos**
  - Email: TODO(humans)
  - ORCID: TODO(humans)
  - Affiliation: TODO(humans)
  - GitHub: `emelon8` (per the canonical repo URL
    [`https://github.com/emelon8/experiment_analysis`](https://github.com/emelon8/experiment_analysis)
    in `pyproject.toml`).

## Contributors

People who have contributed code, documentation, or review without (yet)
appearing in the package metadata.

- **Eli Keldsen** — renamed the project to ACE-NeuroTools (commit
  [`1e72936`](https://github.com/emelon8/experiment_analysis/commit/1e72936)).
- TODO(humans): the git history (`git log --format='%an' | sort -u`) lists
  many additional contributors (e.g. Ethan Whitt, Nathan Philpot, Josie
  Allred, Katherine McCormack, Max Tsai, Isaac Lambert, Kase Haas,
  Reed Fisher). Decide which of these to acknowledge here vs. in the paper's
  acknowledgements section.

## Notes for maintainers

### Canonical repository URL

`pyproject.toml` and the docs consistently use
[`https://github.com/emelon8/experiment_analysis`](https://github.com/emelon8/experiment_analysis)
as the canonical repository URL. The paper-prep notes, however, reference
`reedpen/example-project` in places, and a non-default git remote
(`ace -> https://github.com/reedpen/ace.git`) is configured locally.

> TODO(humans): confirm the canonical GitHub organization and repository
> name for ACE-NeuroTools before submission. If the project will be moved
> to a different org/repo (e.g. a lab-org), update `pyproject.toml`,
> `mkdocs.yml`, `CITATION.cff`, this file, and any docs links in lockstep.

### Author order policy

The order in `pyproject.toml [project.authors]` is the canonical author
order for citation purposes. If the order needs to change for the paper,
update both `pyproject.toml` and `CITATION.cff` together.
