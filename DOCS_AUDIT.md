# Documentation verification — 20 October 2026

Reviewed current main at `24812c347bcc315f0b629b2765a1672404c20127` in an isolated
checkout. Earlier local Comenius copies include different applications; this
pass targets the installed `aceneurotools.gui` application launched by `ace-gui`.

## Findings and repairs

| Finding | Evidence | Repair |
| --- | --- | --- |
| Read the Docs crashes while rendering API pages | [Hosted build 35277395](https://app.readthedocs.org/projects/ace-neurotools/builds/35277395/) and an identical local reproduction: mkdocstrings 1.0.6 calls PyMdown 12.3 Highlight without the required Markdown argument | Bound `pymdown-extensions` below 12.2 in [docs extras](pyproject.toml) and [environment specification](environment.yml). Installation now selects 12.1. |
| No docs check in main CI; existing docstring indentation fails a strict build | [CI](.github/workflows/ci.yml), [load_obj docstring](src/aceneurotools/shared/misc_functions.py) | Added a fresh Python 3.10 install/build job, corrected three docstring continuation indents, and enabled local-link checking and strict mode in [Read the Docs](.readthedocs.yaml). |
| Install instructions direct lab members to a channel that is not published | [Installation](docs/gui_installation.md), [packaging](docs/packaging.md), `ace-gui` entry point in [pyproject](pyproject.toml) | Marked the package route as pending, supplied current source setup for maintainers and repeatable launch/reopening steps for lab members. |
| GUI guide too brief to support a nontechnical test session | Actual labels/actions in [index.html](src/aceneurotools/gui/index.html), [app.js](src/aceneurotools/gui/app.js), [analysis.js](src/aceneurotools/gui/analysis.js), [neurons.js](src/aceneurotools/gui/neurons.js) | Expanded [GUI guide](docs/gui.md) with prerequisites, output locations, and troubleshooting. Public installation and usage guides are linked in site navigation; internal testing assignments are kept outside the published documentation. |
| Old pilot instructions overstate installed features | [Local recording resolver](src/aceneurotools/gui/recordings.py), [server routes](src/aceneurotools/gui/server.py), History text in app.js | Explain that Box downloads happen outside this GUI, cluster export is deferred, and saved runs/backups are not connected revision history. Distinguish old launch scripts from `ace-gui`. |
| Incomplete examples omit data paths, overpromise extraction, or imply identical Python and command defaults | [Pipeline defaults](src/aceneurotools/shared/pipeline_defaults.py), [CLI parameter merge](src/aceneurotools/shared/cli_utils.py), [calcium signature](src/aceneurotools/pipelines/calcium_imaging.py) | Corrected README and getting-started/modality guides. Explain `0.avi` versus all movies, crop behavior, explicit extraction and parameter precedence. |
| Ephys filter example uses a band type as the filter family | [Ephys loader](src/aceneurotools/ephys/ephys_loader.py) | Use `butter`/`fir` and explain optional filtering/phases and bandpass cutoffs. |
| Multimodal guide conflates Python and command defaults and links to a missing synchronization section | [Combined pipeline](src/aceneurotools/pipelines/multimodal.py), shared defaults | Distinguish defaults, optional results and estimates saving; added the referenced synchronization section. |
| README/home claim a bundled recording fixture and a usable regeneration script | [Fixture script](scripts/create_test_data.py), repository tree | Remove those claims. Lab must supply project, recording and suitable settings. |
| Older example links to removed environment files, downloader line numbers, PySimpleGUI, and claims the module command selects all movies | [Single-AVI script](examples/single_avi_smoke_test.py), current credentials template and shared defaults | Replaced its [checklist](examples/single_avi_setup_checklist.md) with a scoped maintainer path, CCG-only instructions, FreeSimpleGUI recovery and explicit movie selection. |
| Site links use the obsolete unhyphenated hostname | Supplied build URL/project metadata | Use `ace-neurotools.readthedocs.io`; update package READMEs and the canonical site URL. |

## Verification

- Reproduced the exact hosted `Highlight.__init__() missing ... 'md'` failure in
  a fresh Python 3.10 environment with current docs tools and PyMdown 12.3.
- Installed the corrected `.[docs]` extra, including the core package, in that
  environment. The resolver replaced PyMdown 12.3 with 12.1; `pip check` passed.
- Synced tutorials and ran `python -m mkdocs build --strict --clean` successfully
  without installing CaImAn or OpenCV in the docs environment. API documentation
  uses source inspection; notebooks were not executed.
- `python scripts/check_docs_links.py` passed, as did `git diff --check`.
- Existing GUI settings/defaults, launch authentication and neuron review/export
  checks: **49 passed**. The initial sandbox run could not bind local servers;
  the rerun with local-server access passed.
- Inspected rendered guide/navigation pages in a local browser preview.

## Subagent review follow-up

Three independent reviews checked nontechnical user instructions, analysis/API
accuracy, and build/CI behavior. They identified and prompted repairs to:

- The ephys example: `run()` returns `None`; retrieve the channel from the
  pipeline's data manager after running.
- The lab checklist: use the visible **Notes** field label.
- Package metadata: update repository and documentation URLs as well as prose.
- The legacy single-AVI reference: explicitly mark its existing numeric/string
  experiment-ID lookup bug and direct lab acceptance testing to the GUI instead.

The build reviewer independently completed a strict clean build and link check.

## Remaining limits

This pass does not publish the site or confirm a hosted rebuild; the corrected
commit must reach Read the Docs first. Its package installation and build were
reproduced locally rather than by changing dashboard settings.

A lab member's installation on a clean Windows/Mac computer, an acquired recording
from beginning to end, Box permissions/transfers, scientific cell acceptance,
and numerical interpretation still need lab acceptance testing. The checklist
requires supplied data and settings; it is not a self-contained demonstration.

Notebook conversion still prints pre-existing Pandoc notices about unclosed HTML
divs. They do not fail the strict MkDocs build; scientific notebook cells were
not executed or revalidated by this pass.
