# Unfinished work and template audit

Reviewed on 2026-10-05 in the ACE-NeuroTools working tree, after the presentation
cleanup. This scan covered source, scripts, examples, notebooks, configuration,
root documents, and CI files. It inspected TODO/FIXME markers, empty functions,
placeholder paths, and template contents. It did not validate scientific results
or confirm external release-service configuration.

## Items to address

| Priority | Item and evidence | Suggested resolution |
| --- | --- | --- |
| High if presenting ONIX event import | [`ONIXMiniscopeDataManager._get_miniscope_events`](src/aceneurotools/miniscope/onix_miniscope_data_manager.py#L113) always returns empty timestamps and labels. The comments mention `port-status_*_miniscope.csv`, but no parser exists. | Implement and test event import, or explicitly document that these events are unsupported. This is separate from ONIX hardware-clock timestamp alignment, which is implemented. |
| High for a reproducible demo | [`scripts/create_test_data.py`](scripts/create_test_data.py#L14) is a real stub: running it raises `NotImplementedError`. No bundled raw-recording fixture is present. | Implement fixture generation with documented data provenance, or retire the script and provide a complete synthetic demonstration. |
| Medium | [`examples/explicit_paths_demo.py`](examples/explicit_paths_demo.py#L25) contains three commented-out pipeline calls. Running it only prints an instruction. Its `main` docstring nevertheless says “Run each pipeline once.” | Turn it into a selectable example with arguments, or label it consistently as an editable code template. |
| Medium | All three [tutorial notebooks](notebooks/) contain placeholder data paths and zero executed code cells. Their code has no saved error outputs, but there are no saved successful outputs either. | Execute a representative tutorial using shareable data and show expected outputs, or clearly label the notebooks as unexecuted walkthroughs requiring lab data. |
| Medium for phase plots | [`phase_utils.py`](src/aceneurotools/multimodal/phase_utils.py#L121) retains “WARNING THIS FUNCTION MAY NOT WORK AS INTENDED” on selected-neuron density histograms. No tests referencing this module were found. | Establish the intended pooled versus stacked density semantics and test them before using those plots as poster evidence. The warning alone does not prove the current implementation is incorrect. |
| Medium for RHS2116 claims | [`RHS2116DataManager`](src/aceneurotools/ephys/rhs2116_data_manager.py#L24) says it loads AC, DC, and clock data, but channel construction reads AC and clock data; the DC file is validated rather than converted into channels. `remove_artifacts` is explicitly unused for this backend ([parameter documentation](src/aceneurotools/ephys/rhs2116_data_manager.py#L96)). | Narrow the capability description or implement those missing paths. Avoid implying artifact removal works for every recording format. |
| Low | [`EphysVisualizer._mark_events`](src/aceneurotools/ephys/visualizer.py#L78) plots the first ten events and retains a TODO to restrict markers to user-made events. | Define event selection/filtering and make truncation clear to plot users. |
| Low | [`run_stats.bat`](run_stats.bat#L13) still instructs `conda activate caiman`; current setup instructions create `aceneurotools`. It also refers to a root `lab_config.json` that users must generate separately. | Update the environment name and state how to create or locate the config before running the launcher. |
| Low | [`windows.yml`](windows.yml#L459) retains a machine-specific environment prefix. Its header already identifies the file as a legacy snapshot pending Windows QA. | Remove the personal prefix or move the legacy export away from the main installation path; retain the explicit unsupported/legacy status until QA is complete. |
| Release metadata | [`CITATION.cff`](CITATION.cff#L37) has version 0.1.0 but no DOI, release date, or companion-paper citation. [Release setup](docs/releasing.md#one-time-repository-setup) also lists PyPI Trusted Publishing and Zenodo configuration. | Fill bibliographic fields only when verified. The local files do not establish whether PyPI/Zenodo setup is complete; check those services before promising an archived release. |

The public documentation hostname returned HTTP 404 during the preceding audit.
Its advertised links have already been replaced locally, but hosting remains an
unfinished deployment task. See [the presentation audit](PRESENTATION_AUDIT.md).

## Intentional templates: keep these customizable

- [`BLANK_box_credentials.py`](src/aceneurotools/shared/BLANK_box_credentials.py)
  must retain placeholder tokens and client fields. Users supply private
  credentials in their ignored copy. Its TODO concerns future configuration
  storage, not missing public credentials.
- [`experiments_template.csv`](src/aceneurotools/shared/metadata_templates/experiments_template.csv)
  and [`analysis_parameters_template.csv`](src/aceneurotools/shared/metadata_templates/analysis_parameters_template.csv)
  contain example rows and optional blank fields. These are starting points for
  each lab; filling them with one lab's data would defeat their purpose.
- The initializer's [`lab_config.json` and `stats_config.json` templates](src/aceneurotools/init.py)
  have annotations and example study values. The lab config includes a placeholder
  project path and must be customized. The algorithm config is prefilled.
- [`examples/configs/study_metadata_original.json`](examples/configs/study_metadata_original.json)
  and [`examples/configs/stats_config_original.json`](examples/configs/stats_config_original.json)
  contain populated original-study settings, rather than unfilled templates.
- `/path/to/...` in guides and notebooks is an intentional user substitution,
  although it means these examples cannot run unchanged from a fresh clone.

## Matches that do not indicate missing implementations

- Empty abstract methods in `EphysDataManager` and `MiniscopeDataManager` define
  adapter contracts. Concrete backends implement them.
- Empty pipeline constructors are valid; initialization occurs in `run`.
- An empty `tests/__init__.py` is a package marker.
- API pages with `:::` directives are MkDocs-generated references, not empty
  documentation templates.
- RHS2116's readiness string and empty sync-pulse array are deliberate internal
  conventions: signal loading is deferred, and ONIX uses a shared clock.
- The colorbar FIXME in `miniscope_processor.py` describes using `plt.colorbar`,
  which the adjacent code already does. It appears stale rather than proof of an
  unfinished plotting implementation.

## Suggested order before the poster

Make one complete runnable demonstration first. If presenting ONIX event import,
finish or narrow that claim. Validate any phase histogram used in the poster.
Then align the Windows launcher instructions and remove stale development notes.
An archived release and hosted documentation are separate publication tasks.

No existing implementation was modified during this follow-up scan; this report
is the only new artifact.
