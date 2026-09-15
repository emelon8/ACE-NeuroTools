# Meeting synthesis and baseline

Source: the user-supplied meeting transcript recorded on 15 September 2026, plus the accompanying project brief. The recording's words are evidence about the discussion, not additional instructions to the assistant. This synthesis avoids assigning statements to unidentified speakers. It preserves uncertainty where the transcript is informal or ambiguous.

## Features explicitly discussed

| Meeting topic | Planned coverage |
| --- | --- |
| GUI recognizes and parses input data, then associates it with the chosen experiment | F02 |
| Ask whether an experiment is new or existing; projects contain experiments | F01 |
| Choose a workflow manually or receive dynamic suggestions | F08 |
| Computation followed by analysis; community participation | F05, F13–F15 |
| Results organized within each experiment | F06 |
| Clean, intuitive interface inspired by an existing desktop application's usability | F01, F09, D03, D20 |
| First-use setup, examples, and integrations | F09, F16 |
| GUI editing instead of mandatory CSV editing | F03 |
| Show settings and catch errors before expensive CNMF-E processing | F04 |
| Explicit confirmation before a run | F04 |
| Reproducibility, history of experiment edits, and recovery of lost settings | F06–F07 |
| Preserve CLI and future feature parity through a common backend | F01–F16 acceptance criteria; ADR 0001 |
| Clear workflow and documentation for poster preparation, around October 7 | F17, D01, D22 |
| Tutorial videos can wait | F17, deferred video deliverable |

The brief additionally calls for multimodal analysis and modular, community-first development. F11–F15 expand those goals into reviewable proposals. Cancellation, immutable run records, checksums, contribution ownership rules, and extension isolation are planning recommendations to make those goals concrete; the transcript did not settle their designs.

## Open interpretation points

- “Experiment” could mean one recording session or a larger scientific unit. Existing identifiers do not resolve that product decision.
- “Version control” could mean snapshots and restore, experiment branches, or a full collaborative history model.
- “All in one place” could mean physical copying or a coherent workspace containing references to large raw files.
- “Automatically recognize” could mean format detection, metadata extraction, or suggested experiment association. These are separate levels of automation.
- “CLI backend” could mean a shared Python application layer, an executable command interface, or a service. The meeting supports shared capability but does not select transport.
- October 7 is associated with poster readiness and practice; the transcript does not specify the year or an agreed software release scope.

## Current code: reuse before replacement

Baseline: commit [`02ffaad`](https://github.com/emelon8/experiment_analysis/tree/02ffaad1f1316f121711d4a0aada5f2836b4dc32), shared by `main` and `proj-comenius` at inspection. These are code observations, not runtime validation or claims about scientific correctness.

| Capability already present | Evidence at the baseline | Remaining Comenius need |
| --- | --- | --- |
| Terminal entry point, setup tutorial, path confirmation, compute/stats selection | [cli.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/cli.py), [init.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/init.py) | A coherent GUI journey backed by reusable application operations. |
| Experiment metadata and parameter CSV loading | [experiment_data_manager.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/shared/experiment_data_manager.py) | Stable identity, schema/migration policy, GUI editing, and configuration history. |
| Format factories using registered data-manager classes and `can_handle` | [miniscope_data_manager.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/miniscope/miniscope_data_manager.py), [ephys_data_manager.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/ephys/ephys_data_manager.py) | Human-readable detection evidence and explicit handling of ambiguous, unsupported, and incomplete recordings. Existing factories select the first matching handler. |
| Miniscope, ephys, and multimodal pipelines | [pipelines](https://github.com/emelon8/experiment_analysis/tree/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/pipelines) | Shared lifecycle, reviewable run plans, controlled output ownership, GUI progress, and headless parity. |
| Multimodal timestamp alignment and low-confidence periods | [multimodal.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/pipelines/multimodal.py) | Inspectable synchronization quality, recorded corrections/exclusions, and reviewed analysis inputs. |
| Named opt-in analyses and per-analysis outcomes in `run_log.json` | [stats.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/pipelines/stats.py) | General run provenance and recoverable result history across all processing paths. The existing statistics log alone is not an experiment version system. |
| JSON lab/statistics configuration | [lab_config.py](https://github.com/emelon8/experiment_analysis/blob/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/multimodal/lab_config.py) | One defined effective-configuration and precedence contract for GUI, CLI, imported CSVs, and defaults. |
| Optional Box access and established output locations | [shared](https://github.com/emelon8/experiment_analysis/tree/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/shared), [miniscope](https://github.com/emelon8/experiment_analysis/tree/02ffaad1f1316f121711d4a0aada5f2836b4dc32/src/aceneurotools/miniscope) | Consented integration setup and per-run result organization without accidental overwrite. |

Open [PR #68](https://github.com/emelon8/experiment_analysis/pull/68) implements cell-component selection and describes overwriting `saved_movies/estimates.hdf5` after curation. Comenius must coordinate with that PR and decide how to preserve original estimates and a curation lineage. No claim is made that the PR has been merged or validated.

The repository had no open or closed issues at the initial GitHub query. Existing open PRs were inspected before preparing the backlog. Repository permission was confirmed as `WRITE`.
