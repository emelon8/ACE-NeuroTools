# Existing development issues — checked 2026-09-16

These findings predate the workbench (`2fd7cac`) and remain outside its
parameter/history/results implementation. No scientific source files were
changed. Passing the existing fast suite does not establish scientific pipeline
correctness. Priorities below are audit recommendations, not closed issues.

| Priority | Finding | Evidence / practical consequence |
| --- | --- | --- |
| High | Default miniscope spectrogram plotting raises `TypeError` | `src/aceneurotools/miniscope/miniscope_postprocessor.py:282` defines a boolean named `plot_spectrogram`; line 323 calls it. Reproduced with synthetic arrays and the expensive transform stubbed: `TypeError: 'bool' object is not callable`. The older memory description of “duplicate plotting” understated this failure. |
| High | Effective stats frequency range can differ from recorded/CLI range | `stats/loader.py:125` passes `filter_type=None`; `stats/coherence_analysis.py:87` and `stats/scatter_analysis.py:885` use `config.lowcut/highcut`. The pipeline separately logs `effective_freq_range`. Confirmed by call-path inspection; scientific numeric effects were not benchmarked. |
| Medium | All-drugs summary receives the wrong collection type | `pipelines/stats.py:605` passes `list(self.scatter_collectors.values())`; `stats/scatter_analysis.py:768` calls `.items()`. The exception is caught and printed, so the overall workflow can continue without the expected figure. |
| Medium | Missing explicit CLI config returns success | `cli.py:653–656` returns zero for a nonexistent `--config`. Reproduced with a nonexistent file in a temporary directory; exit status was 0. |
| Medium | Canceling crop produces zero-sized crop coordinates | `miniscope/gui_utils.py:331–336` sets all coordinates to zero. Confirmed by source inspection, not an interactive CaImAn GUI test. |
| Medium | EVC default ignore list is not a complete raw-format filter | `evc/workspace.py:DEFAULT_IGNORE_PATTERNS` omits `.ncs`, `.nev`, `.tif`, `.npy`, etc. A synthetic `.ncs` at workspace root was included in a real EVC revision. Keep recordings outside tracked paths or extend `.evc/ignore`. The GUI follows existing EVC semantics. |
| Low | Event visualization truncates to ten events | `ephys/visualizer.py:108–109` slices labels and timestamps to `[:10]`. Confirmed by source inspection. |
| Maintenance | Repository lint is advisory and not clean | `ruff check src tests` reports 298 issues at baseline with Ruff 0.16.8. No broad autofix performed. GUI code has a separate mandatory clean lint check. |
| Integration | Existing component selector PR needs integration | GitHub PR #68 `gui-updates` was OPEN and CONFLICTING on audit date. No merge or overwrite performed. |

## Already resolved before this work

- Scatter-engine failures are no longer recorded as successful subjects (EVC
  hook regression test exists).
- Experiment CSV templates and missing optional Box columns were repaired;
  compatibility tests exist.
- JSON configuration authority (D05) is recorded. The CSV bridge and frozen EVC
  API are implemented; lab/stats documents and retirement of CSV writeback are
  incomplete, not missing decisions disguised as completed features.

## Workflow update — 2026-09-17

The [recording workflow](WORKFLOW.md) now implements project creation, browser
file/folder import, conditional configuration, preflight approval, local workers,
logs and cancellation. It reuses the existing scientific processing/reader
classes without changing the scientific source tree. The calcium adapter stays
headless and avoids the unrelated legacy postprocessing failure; the Neuralynx
adapter preserves original samples and timestamps instead of invoking implicit
gap interpolation. The raw-file ignore limitation is addressed for new imports
by placing all copied inputs under `artifacts/`.

Curation integration, full recording visualization, multimodal alignment,
study-level statistics, cloud synchronization, public third-party plugin
contracts, native installers and multi-user collaboration remain separate work.
The existing unrelated scientific bugs above remain open. Broader issue-owner
acceptance and other Comenius decisions have not been marked complete by this
branch's implementation.
