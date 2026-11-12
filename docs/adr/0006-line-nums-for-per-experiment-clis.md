---
status: accepted
---

# Accept several experiments in the per-experiment commands

## Context

`ComputePipeline` and `StatsPipeline` accept several experiments
(`--line-nums`, `pipelines/compute.py:233`, `pipelines/stats.py:783`). The
per-experiment commands accept exactly one:

- `pipelines/calcium_imaging.py:402` (`main()`)
- `pipelines/ephys.py:304` (argparse inline under `if __name__ == "__main__"`)
- `pipelines/multimodal.py:360` (argparse inline under `if __name__ == "__main__"`)

All three repeat the same steps: `build_run_params`, `apply_headless_policy`,
`validate_run_params`, then `run()`, printing errors with `print_cli_error` and
exiting 1 when headless (`calcium_imaging.py:413-436`, `ephys.py:313-338`,
`multimodal.py:369-393`). Batch scripts and scheduler job arrays must therefore
start one Python process per experiment, re-importing CaImAn each time.

## Proposed change

Add four helpers and an error list to `shared/cli_utils.py` and use them in all
three commands:

- `add_experiment_arguments(parser)`: a required, mutually exclusive
  `--line-num N` / `--line-nums N [N ...]` pair (repeating `--line-nums` adds
  more), plus `--fail-fast`.
- `parse_experiment_args(parser, argv)`: parses and rejects `--fail-fast` without
  `--line-nums` and negative `--line-nums` values.
- `selected_line_nums(args)`: the requested experiments in order, repeats
  removed.
- `run_pipeline_for_experiments(...)`: runs the pipeline and returns the exit code.
- `RUN_ERRORS`: the errors a batch reports per experiment (`AceNeuroError`,
  `FileNotFoundError`, `ValueError`).

The ephys and multimodal commands move into `main(argv=None)` functions, as
calcium imaging already has, so tests can call them directly.

Failure handling:

| Case | Behavior |
| --- | --- |
| `--line-num N` (one experiment) | Unchanged: invalid settings raise; a run error prints, then exits 1 when headless or is re-raised. |
| `--line-nums` | The project and data paths are checked once; if they are invalid nothing runs and the exit code is 1. Each experiment gets a new pipeline instance and its own saved settings. A settings or run error (`RUN_ERRORS`) is printed with its cause and the next experiment runs. Other exceptions, including `KeyboardInterrupt`, stop the command after printing the summary so far. |
| `--line-nums --fail-fast` | Stops at the first failure and lists experiments not run. |
| Exit code with `--line-nums` | 1 when any experiment failed or was not run, headless or not, so schedulers and scripts can detect partial failure. |

A summary (`Completed X of N experiments`, then each failure with its cause,
then any experiments not run) is printed at the end. Standard output is flushed
before each error message so logs that merge both streams stay in order. Open
matplotlib figures are closed between experiments.

## Compatibility

- `--line-num` keeps working with the same parameters, precedence
  (defaults → CSV → CLI) and headless policy. `tests/parity_probe.py` still
  observes `run()` in the `__main__` namespace when the module runs with `runpy`.
- argparse's message when neither option is given changes from "the following
  arguments are required: --line-num" to "one of the arguments --line-num
  --line-nums is required".
- Numerical calculations are unchanged. CLI entry points and calcium worker cleanup change as shown in the exact patch below.
- Runs in one process share CaImAn and matplotlib state. Each experiment gets a
  new pipeline object; module-level state is shared, and long batches keep one
  CaImAn import. Users who need full isolation can still run one experiment per
  process.

## Alternatives

- Leave the commands single-experiment and generate one command per experiment
  in GUI and job exports. This works today and is the fallback.
- Add a `--continue-on-error` flag instead of continuing by default. Rejected:
  continuing matches `StatsPipeline`, which records skipped subjects and
  continues.

## Unblocks

Simpler plain-shell and scheduler exports from the GUI (one command per
analysis, or one job-array task per experiment chunk) and a command-line
equivalent of the GUI's sequential batch queue.

## Risks

- Experiments share one process. Module-level state, the loaded CaImAn module
  and matplotlib's backend carry over: calcium processing switches matplotlib to
  an interactive backend, and if an experiment fails before postprocessing
  switches it back, the next experiment starts with that backend. Single runs
  already behave this way.
- Errors outside `RUN_ERRORS` (for example a `TypeError` from malformed saved
  settings, or a locked CSV file) stop the whole batch rather than one
  experiment; the summary so far is printed first.
- Calcium processing now stops the CaImAn worker pool after a failure too. For
  serial runs this means CaImAn's `stop_server` also runs after a failure, as it
  already did after a success.
- Users who need full isolation should keep running one experiment per process.

## Tests

- `tests/test_cli_line_nums.py`: exclusive and repeatable flags, negative IDs,
  `--fail-fast` rules, per-experiment saved settings, new instances and copied
  defaults, failures with their causes (also without `--headless`), fail-fast and
  stopped-batch summaries (including a stop while closing figures), invalid paths
  reported once and an empty `--data-path` ignored as for one experiment, merged stdout/stderr order
  (in a subprocess), freeing a failed experiment, closing figures, unchanged
  `--line-num` behavior, and that each command passes its own pipeline, defaults
  and settings loader.
- `tests/test_calcium_imaging_processor_cleanup.py`: the worker pool is stopped
  once after success and after a failure at every stage, results are saved before
  it is stopped, a failing stop is only a warning, and quality scoring still runs
  inside the cleanup block.

## Verification

The patch below is the code and test change (`src/` and `tests/`) against base
`78acb6b` (main after PRs #152 and #153); the documentation changes are in the
PR. It was accepted when PR #154 was merged after adversarial review. The review
ran the full default suite (`pytest tests -m "not slow"`), changed-line coverage,
documentation coverage, the documentation link check and the strict MkDocs build;
the results are in the PR. Representative recording validation is handled
separately by the lab, as `AGENTS.md` describes.

## Diff

```diff
diff --git a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
index 15f1c35..c169f53 100644
--- a/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
+++ b/src/aceneurotools/calcium_imaging/calcium_imaging_processor.py
@@ -117,45 +117,49 @@ class CalciumImagingProcessor:
             print('Setting up cluster for caiman parallel processing on your computer')
             c, dview, n_processes = cm.cluster.setup_cluster(backend='multiprocessing', n_processes=n_processes, single_thread=False)
 
-        #Apply motion correction, then saves a memory map to opts_caiman to prepare for CNMFE.
-        self.data_manager = self.motion_correction_manager(self.data_manager, dview, apply_motion_correction, inspect_motion_correction)
+        # Stop the CaImAn worker pool even when processing fails, so a failed run
+        # does not leave workers behind (CaImAn refuses to start a new pool while
+        # they are alive, which would fail every later run in the same process).
+        try:
+            #Apply motion correction, then saves a memory map to opts_caiman to prepare for CNMFE.
+            self.data_manager = self.motion_correction_manager(self.data_manager, dview, apply_motion_correction, inspect_motion_correction)
 
-        #Prepare additional analysis parameters for CNMFE
-        self.data_manager, images = self.cnmfe_parameter_handler(self.data_manager, plot_params=plot_params)
+            #Prepare additional analysis parameters for CNMFE
+            self.data_manager, images = self.cnmfe_parameter_handler(self.data_manager, plot_params=plot_params)
 
-        #intialize CNMFE object
-        self.data_manager.CNMFE_obj = cm.source_extraction.cnmf.CNMF(n_processes=n_processes, dview=dview, Ain=None, params=self.data_manager.opts_caiman)
+            #intialize CNMFE object
+            self.data_manager.CNMFE_obj = cm.source_extraction.cnmf.CNMF(n_processes=n_processes, dview=dview, Ain=None, params=self.data_manager.opts_caiman)
 
-        #reupdate data_manager.movie with motion-corrected movie, otherwise the movie returned below is the same if you did not motion correct
-        self.data_manager.movie = cm.movie(images, fr=self.data_manager.fr)
+            #reupdate data_manager.movie with motion-corrected movie, otherwise the movie returned below is the same if you did not motion correct
+            self.data_manager.movie = cm.movie(images, fr=self.data_manager.fr)
 
-        #run CNMFE. Do not run unless you have optimal parameters or the neuron estimates will be junk
-        if run_CNMFE:
-            print('Running CNMFE...')
-            try:
-                self.data_manager.CNMFE_obj.fit(images)
-            except (ValueError, MemoryError, RuntimeError) as e:
-                print('CNMFE failed to run. Please check the parameters and try again.')
-                print('No estimates were saved to disk. Do not continue to post-processing or multimodal analysis')
-                raise ProcessingError(f"CNMFE failed: {e}") from e
-
-            if save_estimates:
-                # Store quality evidence with the fitted estimates for later review.
-                # The CNN footprint classifier is not intended for one-photon CNMF-E data.
+            #run CNMFE. Do not run unless you have optimal parameters or the neuron estimates will be junk
+            if run_CNMFE:
+                print('Running CNMFE...')
                 try:
-                    quality_params = self.data_manager.CNMFE_obj.params
-                    quality_params.set('quality', {'min_SNR': 3, 'rval_thr': 0.85, 'use_cnn': False})
-                    self.data_manager.CNMFE_obj.estimates.evaluate_components(images, quality_params, dview=dview)
-                except Exception as exc:
-                    print(f'Warning: component quality scores could not be computed: {exc}')
-
-        #save results 'estimates' to disk and update data_manager with their filepaths
-        self.data_manager = self._save_processed_data(self.data_manager, save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params)
-
-        try:
-            cm.stop_server(dview=dview)
-        except (OSError, AttributeError) as e:
-            print(f"Warning: could not stop CaImAn processing server: {e}")
+                    self.data_manager.CNMFE_obj.fit(images)
+                except (ValueError, MemoryError, RuntimeError) as e:
+                    print('CNMFE failed to run. Please check the parameters and try again.')
+                    print('No estimates were saved to disk. Do not continue to post-processing or multimodal analysis')
+                    raise ProcessingError(f"CNMFE failed: {e}") from e
+
+                if save_estimates:
+                    # Store quality evidence with the fitted estimates for later review.
+                    # The CNN footprint classifier is not intended for one-photon CNMF-E data.
+                    try:
+                        quality_params = self.data_manager.CNMFE_obj.params
+                        quality_params.set('quality', {'min_SNR': 3, 'rval_thr': 0.85, 'use_cnn': False})
+                        self.data_manager.CNMFE_obj.estimates.evaluate_components(images, quality_params, dview=dview)
+                    except Exception as exc:
+                        print(f'Warning: component quality scores could not be computed: {exc}')
+
+            #save results 'estimates' to disk and update data_manager with their filepaths
+            self.data_manager = self._save_processed_data(self.data_manager, save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params)
+        finally:
+            try:
+                cm.stop_server(dview=dview)
+            except (OSError, AttributeError) as e:
+                print(f"Warning: could not stop CaImAn processing server: {e}")
 
         # Capture outputs in a structured result for callers that prefer the
         # dataclass API over interrogating data_manager directly.
diff --git a/src/aceneurotools/pipelines/calcium_imaging.py b/src/aceneurotools/pipelines/calcium_imaging.py
index 7499d68..336840e 100644
--- a/src/aceneurotools/pipelines/calcium_imaging.py
+++ b/src/aceneurotools/pipelines/calcium_imaging.py
@@ -17,18 +17,16 @@ from aceneurotools.calcium_imaging.pipeline_results import (
 )
 from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS, accept_legacy_keywords, alias_attribute
 from aceneurotools.shared.cli_utils import (
-    apply_headless_policy,
-    build_run_params,
-    run_allowed_keys,
-    validate_run_params,
+    add_experiment_arguments,
+    parse_experiment_args,
+    run_pipeline_for_experiments,
+    selected_line_nums,
 )
 from aceneurotools.shared.config_utils import get_coords_dict_from_analysis_params
 from aceneurotools.shared.csv_worker import update_csv_cell
 from aceneurotools.shared.exceptions import (
-    AceNeuroError,
     DataNotFoundError,
     PipelineExecutionError,
-    print_cli_error,
 )
 from aceneurotools.shared.pipeline_defaults import pipeline_defaults
 
@@ -386,7 +384,13 @@ class CalciumImagingPipeline:
         )
 
 
-def main():
+def main(argv=None):
+    """Run ``python -m aceneurotools.pipelines.calcium_imaging`` for one or several experiments.
+
+    ``--line-num`` runs one experiment as before. ``--line-nums`` runs several in this
+    process, continuing past failures unless ``--fail-fast`` is given, and exits with
+    code 1 if any experiment failed or was not run.
+    """
     parser = argparse.ArgumentParser(
         description="Run Calcium Imaging Analysis Pipeline",
         formatter_class=argparse.RawDescriptionHelpFormatter,
@@ -397,10 +401,12 @@ Examples:
 
   # Run in headless mode (no GUI) for batch processing
   python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /path/to/project --headless
+
+  # Run several experiments one after another, continuing past failures
+  python -m aceneurotools.pipelines.calcium_imaging --line-nums 96 97 101 --project-path /path/to/project --headless
 """
     )
-    parser.add_argument('--line-num', type=int, required=True,
-                        help="Experiment line number from experiments.csv")
+    add_experiment_arguments(parser)
     parser.add_argument('--project-path', type=str, required=True,
                         help="Path to project directory (containing experiments.csv)")
     parser.add_argument('--data-path', type=str,
@@ -408,32 +414,23 @@ Examples:
     parser.add_argument('--headless', action='store_true',
                         help="Run in headless mode (no GUI)")
 
-    args = parser.parse_args()
-
-    # Default parameters
-    defaults = pipeline_defaults("calcium_imaging")
+    args = parse_experiment_args(parser, argv)
 
     from aceneurotools.shared.config_utils import load_analysis_params
-    run_params = build_run_params(
-        defaults=defaults,
-        allowed_keys=run_allowed_keys(CalciumImagingPipeline.run),
-        line_num=args.line_num,
+    code = run_pipeline_for_experiments(
+        pipeline_name="calcium_imaging",
+        pipeline_cls=CalciumImagingPipeline,
+        defaults=pipeline_defaults("calcium_imaging"),
+        line_nums=selected_line_nums(args),
         project_path=args.project_path,
         data_path=args.data_path,
         headless=args.headless,
         csv_loader=load_analysis_params,
+        batch=args.line_nums is not None,
+        fail_fast=args.fail_fast,
     )
-    apply_headless_policy(pipeline_name="calcium_imaging", run_params=run_params)
-    validate_run_params(pipeline_name="calcium_imaging", run_params=run_params)
-
-    api = CalciumImagingPipeline()
-    try:
-        api.run(**run_params)
-    except (AceNeuroError, FileNotFoundError, ValueError) as e:
-        print_cli_error(e, include_cause=args.headless)
-        if args.headless:
-            sys.exit(1)
-        raise
+    if code:
+        sys.exit(code)
 
 
 # Compatibility for existing scripts.
diff --git a/src/aceneurotools/pipelines/ephys.py b/src/aceneurotools/pipelines/ephys.py
index 12188c0..8cde1d7 100644
--- a/src/aceneurotools/pipelines/ephys.py
+++ b/src/aceneurotools/pipelines/ephys.py
@@ -9,16 +9,12 @@ from aceneurotools.ephys.ephys_data_manager import EphysDataManager
 from aceneurotools.ephys.ephys_loader import load_ephys_for_analysis
 from aceneurotools.shared.pipeline_defaults import pipeline_defaults
 from aceneurotools.shared.cli_utils import (
-    apply_headless_policy,
-    build_run_params,
-    run_allowed_keys,
-    validate_run_params,
-)
-from aceneurotools.shared.exceptions import (
-    AceNeuroError,
-    PipelineExecutionError,
-    print_cli_error,
+    add_experiment_arguments,
+    parse_experiment_args,
+    run_pipeline_for_experiments,
+    selected_line_nums,
 )
+from aceneurotools.shared.exceptions import PipelineExecutionError
 from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
 
 
@@ -288,7 +284,13 @@ class EphysPipeline:
 
 
 
-if __name__ == "__main__":
+def main(argv=None):
+    """Run ``python -m aceneurotools.pipelines.ephys`` for one or several experiments.
+
+    ``--line-num`` runs one experiment as before. ``--line-nums`` runs several in this
+    process, continuing past failures unless ``--fail-fast`` is given, and exits with
+    code 1 if any experiment failed or was not run.
+    """
     parser = argparse.ArgumentParser(
         description="Run Ephys Analysis Pipeline",
         formatter_class=argparse.RawDescriptionHelpFormatter,
@@ -299,10 +301,12 @@ Examples:
 
   # Run in headless mode (no GUI) for batch processing
   python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project --headless
+
+  # Run several experiments one after another, continuing past failures
+  python -m aceneurotools.pipelines.ephys --line-nums 96 97 101 --project-path /path/to/project --headless
 """
     )
-    parser.add_argument('--line-num', type=int, required=True,
-                        help="Experiment line number from experiments.csv")
+    add_experiment_arguments(parser)
     parser.add_argument('--project-path', type=str, required=True,
                         help="Path to project directory (containing experiments.csv)")
     parser.add_argument('--data-path', type=str,
@@ -310,29 +314,24 @@ Examples:
     parser.add_argument('--headless', action='store_true',
                         help="Run in headless mode (no GUI)")
 
-    args = parser.parse_args()
-
-    # Default parameters
-    defaults = pipeline_defaults("ephys")
+    args = parse_experiment_args(parser, argv)
 
     from aceneurotools.shared.config_utils import load_analysis_params
-    run_params = build_run_params(
-        defaults=defaults,
-        allowed_keys=run_allowed_keys(EphysPipeline.run),
-        line_num=args.line_num,
+    code = run_pipeline_for_experiments(
+        pipeline_name="ephys",
+        pipeline_cls=EphysPipeline,
+        defaults=pipeline_defaults("ephys"),
+        line_nums=selected_line_nums(args),
         project_path=args.project_path,
         data_path=args.data_path,
         headless=args.headless,
         csv_loader=load_analysis_params,
+        batch=args.line_nums is not None,
+        fail_fast=args.fail_fast,
     )
-    apply_headless_policy(pipeline_name="ephys", run_params=run_params)
-    validate_run_params(pipeline_name="ephys", run_params=run_params)
-
-    e = EphysPipeline()
-    try:
-        e.run(**run_params)
-    except (AceNeuroError, FileNotFoundError, ValueError) as e:
-        print_cli_error(e, include_cause=args.headless)
-        if args.headless:
-            sys.exit(1)
-        raise
+    if code:
+        sys.exit(code)
+
+
+if __name__ == "__main__":
+    main()
diff --git a/src/aceneurotools/pipelines/multimodal.py b/src/aceneurotools/pipelines/multimodal.py
index f247c65..51aedc5 100644
--- a/src/aceneurotools/pipelines/multimodal.py
+++ b/src/aceneurotools/pipelines/multimodal.py
@@ -19,13 +19,13 @@ from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline
 from aceneurotools.pipelines.ephys import EphysPipeline
 from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS, accept_legacy_keywords, alias_attribute
 from aceneurotools.shared.cli_utils import (
-    apply_headless_policy,
-    build_run_params,
-    run_allowed_keys,
-    validate_run_params,
+    add_experiment_arguments,
+    parse_experiment_args,
+    run_pipeline_for_experiments,
+    selected_line_nums,
 )
 from aceneurotools.shared.config_utils import load_analysis_params
-from aceneurotools.shared.exceptions import AceNeuroError, PipelineExecutionError, print_cli_error
+from aceneurotools.shared.exceptions import PipelineExecutionError
 from aceneurotools.shared.pipeline_defaults import pipeline_defaults
 
 
@@ -344,7 +344,13 @@ class MultimodalPipeline:
         self.phase_bin_edges_calcium_imaging = bin_edges2
 
 
-if __name__ == "__main__":
+def main(argv=None):
+    """Run ``python -m aceneurotools.pipelines.multimodal`` for one or several experiments.
+
+    ``--line-num`` runs one experiment as before. ``--line-nums`` runs several in this
+    process, continuing past failures unless ``--fail-fast`` is given, and exits with
+    code 1 if any experiment failed or was not run.
+    """
     parser = argparse.ArgumentParser(
         description="Run Multimodal Analysis Pipeline",
         formatter_class=argparse.RawDescriptionHelpFormatter,
@@ -355,10 +361,12 @@ Examples:
 
   # Run in headless mode (no GUI) for batch processing
   python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project --headless
+
+  # Run several experiments one after another, continuing past failures
+  python -m aceneurotools.pipelines.multimodal --line-nums 97 101 --project-path /path/to/project --headless
 """
     )
-    parser.add_argument('--line-num', type=int, required=True,
-                        help="Experiment line number from experiments.csv")
+    add_experiment_arguments(parser)
     parser.add_argument('--project-path', type=str, required=True,
                         help="Path to project directory (containing experiments.csv)")
     parser.add_argument('--data-path', type=str,
@@ -366,28 +374,23 @@ Examples:
     parser.add_argument('--headless', action='store_true',
                         help="Run in headless mode (no GUI)")
 
-    args = parser.parse_args()
+    args = parse_experiment_args(parser, argv)
 
-    # Default parameters
-    defaults = pipeline_defaults("multimodal")
-
-    run_params = build_run_params(
-        defaults=defaults,
-        allowed_keys=run_allowed_keys(MultimodalPipeline.run),
-        line_num=args.line_num,
+    code = run_pipeline_for_experiments(
+        pipeline_name="multimodal",
+        pipeline_cls=MultimodalPipeline,
+        defaults=pipeline_defaults("multimodal"),
+        line_nums=selected_line_nums(args),
         project_path=args.project_path,
         data_path=args.data_path,
         headless=args.headless,
         csv_loader=load_analysis_params,
+        batch=args.line_nums is not None,
+        fail_fast=args.fail_fast,
     )
-    apply_headless_policy(pipeline_name="multimodal", run_params=run_params)
-    validate_run_params(pipeline_name="multimodal", run_params=run_params)
-
-    api = MultimodalPipeline()
-    try:
-        api.run(**run_params)
-    except (AceNeuroError, FileNotFoundError, ValueError) as e:
-        print_cli_error(e, include_cause=args.headless)
-        if args.headless:
-            sys.exit(1)
-        raise
+    if code:
+        sys.exit(code)
+
+
+if __name__ == "__main__":
+    main()
diff --git a/src/aceneurotools/shared/cli_utils.py b/src/aceneurotools/shared/cli_utils.py
index 4c38152..f7d95e6 100644
--- a/src/aceneurotools/shared/cli_utils.py
+++ b/src/aceneurotools/shared/cli_utils.py
@@ -2,14 +2,20 @@
 
 from __future__ import annotations
 
+import argparse
+import copy
 import inspect
+import sys
 import warnings
 from collections.abc import Callable
 from pathlib import Path
 from typing import Any
 
 from aceneurotools.shared.calcium_imaging_names import options_for_keys
-from aceneurotools.shared.exceptions import ConfigurationError
+from aceneurotools.shared.exceptions import AceNeuroError, ConfigurationError, print_cli_error
+
+#: Errors reported per experiment instead of ending a multi-experiment command.
+RUN_ERRORS = (AceNeuroError, FileNotFoundError, ValueError)
 
 
 def run_allowed_keys(run_callable: Callable[..., Any]) -> set[str]:
@@ -60,7 +66,7 @@ def validate_common_inputs(*, line_num: Any, project_path: Any, data_path: Any =
         raise ConfigurationError(
             "line_num must be a non-negative integer.",
             stage="validate_cli_inputs",
-            hint="Pass --line-num with a valid experiment row number.",
+            hint="Pass --line-num or --line-nums with valid experiment row numbers.",
         )
     if not isinstance(project_path, (str, Path)) or not str(project_path).strip():
         raise ConfigurationError(
@@ -149,3 +155,164 @@ def apply_headless_policy(*, pipeline_name: str, run_params: dict[str, Any]) ->
         run_params["plot_params"] = False
 
     return run_params
+
+
+def add_experiment_arguments(parser: argparse.ArgumentParser) -> None:
+    """Add ``--line-num`` / ``--line-nums`` (one is required) and ``--fail-fast``.
+
+    ``--line-nums`` may be repeated; the values are added together.
+    """
+    group = parser.add_mutually_exclusive_group(required=True)
+    group.add_argument('--line-num', type=int,
+                       help="Experiment line number from experiments.csv")
+    group.add_argument('--line-nums', type=int, nargs='+', action='extend', metavar='N',
+                       help="Several experiment line numbers, run one after another with each experiment's "
+                            "saved settings (repeating the flag adds more)")
+    parser.add_argument('--fail-fast', action='store_true',
+                        help="With --line-nums, stop at the first experiment that fails")
+
+
+def parse_experiment_args(parser: argparse.ArgumentParser, argv: list[str] | None = None) -> argparse.Namespace:
+    """Parse arguments added by :func:`add_experiment_arguments` and check how they combine."""
+    args = parser.parse_args(argv)
+    if args.fail_fast and args.line_nums is None:
+        parser.error("--fail-fast applies only with --line-nums")
+    if args.line_nums is not None and any(line_num < 0 for line_num in args.line_nums):
+        parser.error("--line-nums takes non-negative experiment row numbers")
+    return args
+
+
+def selected_line_nums(args: argparse.Namespace) -> list[int]:
+    """Return the requested experiments in order, without repeats."""
+    if args.line_num is not None:
+        return [args.line_num]
+    return list(dict.fromkeys(args.line_nums))
+
+
+def _failure_summary(error: BaseException) -> str:
+    text = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
+    cause = error.__cause__
+    if cause is not None:
+        text += f" (cause: {type(cause).__name__}: {cause})" if str(cause) else f" (cause: {type(cause).__name__})"
+    return text
+
+
+def _print_batch_summary(
+    line_nums: list[int],
+    completed: list[int],
+    failed: list[tuple[int, str]],
+    not_run: list[int],
+    stopped: tuple[int | None, BaseException] | None = None,
+) -> int:
+    print(f"\nCompleted {len(completed)} of {len(line_nums)} experiments.", flush=True)
+    for line_num, summary in failed:
+        print(f"  Failed: {line_num} — {summary}", file=sys.stderr)
+    if stopped:
+        line_num, error = stopped
+        where = f" at {line_num}" if line_num is not None else ""
+        print(f"  Stopped{where} by {_failure_summary(error)}", file=sys.stderr)
+    if not_run:
+        reason = "the stop" if stopped else "--fail-fast"
+        print(f"  Not run after {reason}: {' '.join(map(str, not_run))}", file=sys.stderr)
+    sys.stderr.flush()
+    return 1 if failed or not_run else 0
+
+
+def run_pipeline_for_experiments(
+    *,
+    pipeline_name: str,
+    pipeline_cls: type,
+    defaults: dict[str, Any],
+    line_nums: list[int],
+    project_path: str,
+    data_path: str | None,
+    headless: bool,
+    csv_loader: Callable[..., dict[str, Any]],
+    batch: bool,
+    fail_fast: bool = False,
+) -> int:
+    """Run a per-experiment pipeline CLI and return its exit code.
+
+    ``batch`` is False for ``--line-num``, which keeps the original
+    single-experiment behavior: invalid settings raise, and a run error exits 1
+    when headless or is re-raised. ``batch`` is True for ``--line-nums``, even
+    with one experiment:
+
+    - The project and data paths are checked once; if they are invalid, nothing runs
+      and the exit code is 1.
+    - Each experiment gets a new pipeline instance, a fresh copy of the defaults and
+      its own saved settings.
+    - A failed experiment (an error in ``RUN_ERRORS``) is reported with its cause and
+      the next one runs, unless ``fail_fast``. The exit code is 1 when any experiment
+      failed or was not run.
+    - Any other exception, including ``KeyboardInterrupt``, stops the command: the
+      summary so far is printed and the exception is re-raised.
+
+    Only the error text of a failure is kept, so a failed experiment's data can be
+    freed before the next one.
+    """
+    if not batch and len(line_nums) != 1:
+        raise ValueError("A single-experiment run needs exactly one line number.")
+
+    def prepare(line_num: int) -> dict[str, Any]:
+        run_params = build_run_params(
+            defaults=copy.deepcopy(defaults),
+            allowed_keys=run_allowed_keys(pipeline_cls.run),
+            line_num=line_num,
+            project_path=project_path,
+            data_path=data_path,
+            headless=headless,
+            csv_loader=csv_loader,
+        )
+        apply_headless_policy(pipeline_name=pipeline_name, run_params=run_params)
+        validate_run_params(pipeline_name=pipeline_name, run_params=run_params)
+        return run_params
+
+    if not batch:
+        run_params = prepare(line_nums[0])
+        try:
+            pipeline_cls().run(**run_params)
+        except RUN_ERRORS as exc:
+            print_cli_error(exc, include_cause=headless)
+            if headless:
+                return 1
+            raise
+        return 0
+
+    try:
+        # An empty --data-path is ignored, as build_run_params does for each experiment.
+        validate_common_inputs(line_num=0, project_path=project_path, data_path=data_path or None)
+    except ConfigurationError as exc:
+        print_cli_error(exc)
+        print(f"No experiments were run ({len(line_nums)} requested).", file=sys.stderr)
+        return 1
+
+    completed: list[int] = []
+    failed: list[tuple[int, str]] = []
+    current: int | None = None
+    attempted = 0  # Experiments started so far; the rest have not run.
+    try:
+        for index, line_num in enumerate(line_nums, start=1):
+            attempted, current = index, line_num
+            print(f"\n[{index}/{len(line_nums)}] Experiment {line_num}", flush=True)
+            try:
+                pipeline_cls().run(**prepare(line_num))
+            except RUN_ERRORS as exc:
+                sys.stdout.flush()  # Keep merged stdout/stderr logs in order.
+                print(f"Experiment {line_num} failed:", file=sys.stderr)
+                # A batch never re-raises a run error, so always show its cause here.
+                print_cli_error(exc, include_cause=True)
+                failed.append((line_num, _failure_summary(exc)))
+                if fail_fast:
+                    break
+            else:
+                completed.append(line_num)
+            finally:
+                # Release figures between experiments; each run can create many.
+                if "matplotlib.pyplot" in sys.modules:
+                    sys.modules["matplotlib.pyplot"].close("all")
+            current = None
+    except BaseException as exc:
+        _print_batch_summary(line_nums, completed, failed, line_nums[attempted:], stopped=(current, exc))
+        raise
+    return _print_batch_summary(line_nums, completed, failed, line_nums[attempted:])
diff --git a/tests/test_calcium_imaging_processor_cleanup.py b/tests/test_calcium_imaging_processor_cleanup.py
new file mode 100644
index 0000000..6679182
--- /dev/null
+++ b/tests/test_calcium_imaging_processor_cleanup.py
@@ -0,0 +1,119 @@
+"""The CaImAn worker pool is stopped whether calcium processing succeeds or fails."""
+
+from types import SimpleNamespace
+
+import numpy as np
+import pytest
+
+from aceneurotools.calcium_imaging import calcium_imaging_processor as module
+from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor
+from aceneurotools.shared.exceptions import ProcessingError
+
+
+@pytest.fixture
+def processor(monkeypatch):
+    stops = []
+    processor = object.__new__(CalciumImagingProcessor)
+    processor.data_manager = SimpleNamespace(
+        opts_caiman=None, CNMFE_obj=None, estimates_filepath=None, motion_corrected_movie_filepath=None, fr=20.0
+    )
+    monkeypatch.setattr(module.cm.cluster, "setup_cluster", lambda **kwargs: ("cluster", "worker-pool", 2))
+    monkeypatch.setattr(module.cm, "stop_server", lambda dview=None: stops.append(dview))
+    monkeypatch.setattr(processor, "motion_correction_manager", lambda dm, *args: dm)
+    monkeypatch.setattr(processor, "cnmfe_parameter_handler", lambda dm, plot_params=False: (dm, np.zeros((3, 4, 4))))
+    monkeypatch.setattr(module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: SimpleNamespace())
+    monkeypatch.setattr(processor, "_save_processed_data", lambda dm, *args: dm)
+    return processor, stops
+
+
+def test_successful_run_stops_the_worker_pool_once(processor):
+    processor, stops = processor
+    processor.process_calcium_movie(parallel=True, run_CNMFE=False)
+    assert stops == ["worker-pool"]
+    assert processor.result.estimates_filepath is None
+
+
+@pytest.mark.parametrize("stage", ["motion_correction_manager", "cnmfe_parameter_handler", "_save_processed_data"])
+def test_failed_run_still_stops_the_worker_pool(processor, monkeypatch, stage):
+    processor, stops = processor
+
+    def fail(*args, **kwargs):
+        raise ProcessingError(f"{stage} failed")
+
+    monkeypatch.setattr(processor, stage, fail)
+    with pytest.raises(ProcessingError, match=f"{stage} failed"):
+        processor.process_calcium_movie(parallel=True, run_CNMFE=False)
+    assert stops == ["worker-pool"]
+    assert not hasattr(processor, "result"), "no result is reported for a failed run"
+
+
+def test_cnmfe_failure_still_stops_the_worker_pool(processor, monkeypatch):
+    processor, stops = processor
+
+    def fit(images):
+        raise MemoryError("not enough memory")
+
+    monkeypatch.setattr(module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: SimpleNamespace(fit=fit))
+    with pytest.raises(ProcessingError, match="CNMFE failed: not enough memory"):
+        processor.process_calcium_movie(parallel=True, run_CNMFE=True)
+    assert stops == ["worker-pool"]
+
+
+def test_serial_runs_make_the_same_stop_call_as_before(processor):
+    processor, stops = processor
+    processor.process_calcium_movie(parallel=False, run_CNMFE=False)
+    assert stops == [None]
+
+
+def test_a_failing_stop_is_only_a_warning(processor, monkeypatch, capsys):
+    processor, _ = processor
+
+    def stop(dview=None):
+        raise OSError("already stopped")
+
+    monkeypatch.setattr(module.cm, "stop_server", stop)
+    processor.process_calcium_movie(parallel=True, run_CNMFE=False)
+    assert "Warning: could not stop CaImAn processing server: already stopped" in capsys.readouterr().out
+
+
+class FittedCNMF:
+    """Records the quality-score calls the processor makes after a successful fit."""
+
+    def __init__(self, fail_scoring=False):
+        self.calls = []
+        self.fail_scoring = fail_scoring
+        self.params = SimpleNamespace(set=lambda group, values: self.calls.append(("set", group, values)))
+        self.estimates = SimpleNamespace(evaluate_components=self.evaluate)
+
+    def fit(self, images):
+        self.calls.append(("fit", images.shape))
+
+    def evaluate(self, images, params, dview=None):
+        if self.fail_scoring:
+            raise RuntimeError("scores unavailable")
+        self.calls.append(("evaluate", images.shape, params is self.params, dview))
+
+
+@pytest.mark.parametrize("fail_scoring", [False, True])
+def test_quality_scores_are_computed_inside_the_cleanup_block(processor, monkeypatch, capsys, fail_scoring):
+    processor, stops = processor
+    fitted = FittedCNMF(fail_scoring)
+    monkeypatch.setattr(module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: fitted)
+    processor.process_calcium_movie(parallel=True, run_CNMFE=True, save_estimates=True)
+
+    expected = [("fit", (3, 4, 4)), ("set", "quality", {"min_SNR": 3, "rval_thr": 0.85, "use_cnn": False})]
+    if fail_scoring:
+        assert fitted.calls == expected
+        assert "Warning: component quality scores could not be computed: scores unavailable" in capsys.readouterr().out
+    else:
+        assert fitted.calls == expected + [("evaluate", (3, 4, 4), True, "worker-pool")]
+    assert stops == ["worker-pool"]
+
+
+def test_successful_run_saves_results_before_stopping_the_worker_pool(processor, monkeypatch):
+    processor, stops = processor
+    events = []
+    monkeypatch.setattr(module.cm, "stop_server", lambda dview=None: events.append(("stop", dview)))
+    monkeypatch.setattr(processor, "_save_processed_data", lambda dm, *args: events.append(("save",)) or dm)
+    processor.process_calcium_movie(parallel=True, run_CNMFE=False)
+    assert events == [("save",), ("stop", "worker-pool")]
diff --git a/tests/test_cli_line_nums.py b/tests/test_cli_line_nums.py
new file mode 100644
index 0000000..3d29b68
--- /dev/null
+++ b/tests/test_cli_line_nums.py
@@ -0,0 +1,413 @@
+"""Per-experiment CLIs accept one or several experiments with explicit failure handling."""
+
+import argparse
+import gc
+import importlib
+import runpy
+import sys
+import weakref
+
+import pytest
+
+from aceneurotools.shared import cli_utils
+from aceneurotools.shared.cli_utils import (
+    add_experiment_arguments,
+    parse_experiment_args,
+    run_pipeline_for_experiments,
+    selected_line_nums,
+)
+from aceneurotools.shared.exceptions import ConfigurationError, DataNotFoundError
+
+
+class FakePipeline:
+    """Accepts the keys the ephys headless policy sets, like the real EphysPipeline.run."""
+
+    calls: list = []
+    instances: list = []
+    failing: set = set()
+    hook = None
+
+    def run(
+        self,
+        line_num,
+        project_path,
+        data_path=None,
+        channel_name="CH1",
+        plot_channel=True,
+        plot_spectrogram=True,
+        plot_phases=True,
+        filter_range=None,
+        headless=False,
+    ):
+        FakePipeline.instances.append(self)
+        FakePipeline.calls.append(
+            {
+                "line_num": line_num,
+                "channel_name": channel_name,
+                "plots": (plot_channel, plot_spectrogram, plot_phases),
+                "filter_range": list(filter_range),
+            }
+        )
+        if FakePipeline.hook:
+            FakePipeline.hook(self, line_num, filter_range)
+        if line_num in FakePipeline.failing:
+            raise DataNotFoundError(f"recording {line_num} missing")
+
+
+@pytest.fixture(autouse=True)
+def reset_fake():
+    FakePipeline.calls, FakePipeline.instances, FakePipeline.failing, FakePipeline.hook = [], [], set(), None
+
+
+def parser():
+    result = argparse.ArgumentParser()
+    add_experiment_arguments(result)
+    return result
+
+
+def run(tmp_path, line_nums, *, headless=True, fail_fast=False, saved=None, batch=None):
+    saved = saved or {}
+    return run_pipeline_for_experiments(
+        pipeline_name="ephys",
+        pipeline_cls=FakePipeline,
+        defaults={"channel_name": "CH1", "plot_channel": True, "filter_range": [0.5, 4]},
+        line_nums=line_nums,
+        project_path=str(tmp_path),
+        data_path=None,
+        headless=headless,
+        csv_loader=lambda line_num, project_path: saved.get(line_num, {}),
+        batch=len(line_nums) > 1 if batch is None else batch,
+        fail_fast=fail_fast,
+    )
+
+
+def test_line_num_and_line_nums_are_exclusive_and_one_is_required(capsys):
+    assert selected_line_nums(parse_experiment_args(parser(), ["--line-num", "7"])) == [7]
+    assert selected_line_nums(parse_experiment_args(parser(), ["--line-nums", "9", "7", "9"])) == [9, 7]
+    for argv in ([], ["--line-num", "1", "--line-nums", "2"]):
+        with pytest.raises(SystemExit):
+            parse_experiment_args(parser(), argv)
+    capsys.readouterr()
+
+
+def test_repeated_line_nums_add_up_and_negative_ids_are_rejected(capsys):
+    args = parse_experiment_args(parser(), ["--line-nums", "1", "2", "--line-nums", "3", "1"])
+    assert selected_line_nums(args) == [1, 2, 3]
+    with pytest.raises(SystemExit) as raised:
+        parse_experiment_args(parser(), ["--line-nums", "3", "-1"])
+    assert raised.value.code == 2
+    assert "--line-nums takes non-negative experiment row numbers" in capsys.readouterr().err
+
+
+def test_fail_fast_is_rejected_without_line_nums(capsys):
+    with pytest.raises(SystemExit) as raised:
+        parse_experiment_args(parser(), ["--line-num", "1", "--fail-fast"])
+    assert raised.value.code == 2
+    assert "--fail-fast applies only with --line-nums" in capsys.readouterr().err
+    assert parse_experiment_args(parser(), ["--line-nums", "1", "--fail-fast"]).fail_fast is True
+
+
+def test_each_experiment_uses_its_own_saved_settings_and_new_instance(tmp_path):
+    assert run(tmp_path, [1, 2], saved={2: {"channel_name": "CH2"}}) == 0
+    assert [(call["line_num"], call["channel_name"]) for call in FakePipeline.calls] == [(1, "CH1"), (2, "CH2")]
+    # The headless policy turns every ephys plot off, for every experiment.
+    assert all(call["plots"] == (False, False, False) for call in FakePipeline.calls)
+    first, second = FakePipeline.instances
+    assert first is not second
+
+
+def test_defaults_are_copied_for_each_experiment(tmp_path):
+    def mutate(pipeline, line_num, filter_range):
+        filter_range.append(99)
+
+    FakePipeline.hook = mutate
+    assert run(tmp_path, [1, 2, 3]) == 0
+    assert [call["filter_range"] for call in FakePipeline.calls] == [[0.5, 4]] * 3
+
+
+def test_failed_experiment_is_reported_and_the_next_one_runs(tmp_path, capsys):
+    FakePipeline.failing = {2}
+    assert run(tmp_path, [1, 2, 3], headless=False) == 1
+    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2, 3]
+    captured = capsys.readouterr()
+    assert "Completed 2 of 3 experiments." in captured.out
+    assert "Failed: 2 — DataNotFoundError: recording 2 missing" in captured.err
+
+
+def test_a_failed_experiment_is_released_before_the_next_one(tmp_path):
+    """Only the error text is kept, so the failed pipeline (and its data) can be freed."""
+    FakePipeline.failing = {1}
+    released, first = [], {}
+
+    def check(pipeline, line_num, filter_range):
+        if line_num == 1:
+            first["ref"] = weakref.ref(pipeline)
+        else:
+            FakePipeline.instances.clear()  # Drop the test's own reference to experiment 1.
+            gc.collect()
+            released.append(first["ref"]() is None)
+
+    FakePipeline.hook = check
+    assert run(tmp_path, [1, 2]) == 1
+    assert released == [True]
+
+
+def test_figures_are_closed_between_experiments(tmp_path):
+    import matplotlib
+
+    matplotlib.use("Agg")
+    import matplotlib.pyplot as plt
+
+    open_at_start = []
+
+    def draw(pipeline, line_num, filter_range):
+        open_at_start.append(len(plt.get_fignums()))
+        plt.figure()
+
+    FakePipeline.hook = draw
+    FakePipeline.failing = {2}
+    assert run(tmp_path, [1, 2, 3]) == 1
+    assert open_at_start == [0, 0, 0] and plt.get_fignums() == []
+
+
+def test_fail_fast_stops_and_lists_experiments_not_run(tmp_path, capsys):
+    FakePipeline.failing = {2}
+    assert run(tmp_path, [1, 2, 3], fail_fast=True) == 1
+    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2]
+    assert "Not run after --fail-fast: 3" in capsys.readouterr().err
+
+
+def test_errors_outside_run_failures_stop_the_batch(tmp_path):
+    def broken(pipeline, line_num, filter_range):
+        raise TypeError("programming error")
+
+    FakePipeline.hook = broken
+    with pytest.raises(TypeError, match="programming error"):
+        run(tmp_path, [1, 2])
+    assert [call["line_num"] for call in FakePipeline.calls] == [1]
+
+
+@pytest.mark.parametrize(
+    ("error", "described"),
+    [(TypeError("programming error"), "TypeError: programming error"), (KeyboardInterrupt(), "KeyboardInterrupt")],
+)
+def test_a_stopped_batch_still_prints_what_ran(tmp_path, capsys, error, described):
+    FakePipeline.failing = {1}
+
+    def stop_at_three(pipeline, line_num, filter_range):
+        if line_num == 3:
+            raise error
+
+    FakePipeline.hook = stop_at_three
+    with pytest.raises(type(error)):
+        run(tmp_path, [1, 2, 3, 4])
+    captured = capsys.readouterr()
+    assert "Completed 1 of 4 experiments." in captured.out
+    assert "Failed: 1 — DataNotFoundError: recording 1 missing" in captured.err
+    assert f"Stopped at 3 by {described}" in captured.err
+    assert "Not run after the stop: 4" in captured.err
+
+
+@pytest.mark.parametrize(("failing", "fail_fast"), [(set(), False), ({10}, False), ({10}, True)])
+def test_a_cleanup_error_after_an_experiment_lists_the_rest_as_not_run(tmp_path, monkeypatch, capsys, failing, fail_fast):
+    import matplotlib
+
+    matplotlib.use("Agg")
+    import matplotlib.pyplot as plt
+
+    def broken_close(which):
+        raise RuntimeError("figure cleanup failed")
+
+    monkeypatch.setattr(plt, "close", broken_close)
+    FakePipeline.failing = failing
+    with pytest.raises(RuntimeError, match="figure cleanup failed"):
+        run(tmp_path, [10, 20, 30], fail_fast=fail_fast)
+    assert [call["line_num"] for call in FakePipeline.calls] == [10]
+    captured = capsys.readouterr()
+    assert f"Completed {0 if failing else 1} of 3 experiments." in captured.out
+    assert "Stopped at 10 by RuntimeError: figure cleanup failed" in captured.err
+    assert "Not run after the stop: 20 30" in captured.err
+
+
+def test_a_batch_failure_shows_its_cause_even_without_headless(tmp_path, capsys):
+    def wrapped(pipeline, line_num, filter_range):
+        try:
+            raise RuntimeError("memmap missing")
+        except RuntimeError as cause:
+            raise DataNotFoundError("Calcium imaging processing stage failed.") from cause
+
+    FakePipeline.hook = wrapped
+    assert run(tmp_path, [1, 2], headless=False) == 1
+    err = capsys.readouterr().err
+    assert err.count("Cause: memmap missing") == 2
+    assert "Failed: 1 — DataNotFoundError: Calcium imaging processing stage failed. (cause: RuntimeError: memmap missing)" in err
+
+
+def test_an_empty_data_path_is_ignored_in_a_batch_as_for_one_experiment(tmp_path):
+    assert run_pipeline_for_experiments(
+        pipeline_name="ephys",
+        pipeline_cls=FakePipeline,
+        defaults={"channel_name": "CH1", "filter_range": [0.5, 4]},
+        line_nums=[1, 2],
+        project_path=str(tmp_path),
+        data_path="",
+        headless=True,
+        csv_loader=lambda line_num, project_path: {},
+        batch=True,
+    ) == 0
+    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2]
+
+
+def test_invalid_paths_are_reported_once_and_nothing_runs(tmp_path, capsys):
+    missing = tmp_path / "missing"
+    assert run_pipeline_for_experiments(
+        pipeline_name="ephys",
+        pipeline_cls=FakePipeline,
+        defaults={"channel_name": "CH1", "filter_range": [0.5, 4]},
+        line_nums=[1, 2, 3],
+        project_path=str(missing),
+        data_path=None,
+        headless=True,
+        csv_loader=lambda line_num, project_path: {},
+        batch=True,
+    ) == 1
+    assert FakePipeline.calls == []
+    err = capsys.readouterr().err
+    assert err.count("project_path does not exist") == 1
+    assert "No experiments were run (3 requested)." in err
+
+
+def test_merged_logs_keep_the_summary_in_order(tmp_path):
+    """Progress, failures and the summary appear in order when stdout and stderr share a pipe."""
+    import os
+    import subprocess
+    import textwrap
+    from pathlib import Path
+
+    import aceneurotools
+
+    script = textwrap.dedent(
+        f"""
+        from aceneurotools.shared.cli_utils import run_pipeline_for_experiments
+        from aceneurotools.shared.exceptions import DataNotFoundError
+
+        class Pipeline:
+            def run(self, line_num, project_path, data_path=None, headless=False):
+                print(f"working on {{line_num}}")
+                if line_num == 1:
+                    raise DataNotFoundError("recording 1 missing")
+
+        raise SystemExit(run_pipeline_for_experiments(
+            pipeline_name="compute", pipeline_cls=Pipeline, defaults={{}}, line_nums=[1, 2],
+            project_path={str(tmp_path)!r}, data_path=None, headless=True,
+            csv_loader=lambda line_num, project_path: {{}}, batch=True,
+        ))
+        """
+    )
+    source_root = str(Path(aceneurotools.__file__).resolve().parents[1])
+    environment = {**os.environ, "PYTHONPATH": os.pathsep.join([source_root, os.environ.get("PYTHONPATH", "")])}
+    result = subprocess.run(
+        [sys.executable, "-c", script],
+        stdout=subprocess.PIPE,
+        stderr=subprocess.STDOUT,
+        text=True,
+        env=environment,
+        timeout=120,
+    )
+    assert result.returncode == 1
+    lines = [line for line in result.stdout.splitlines() if line.strip()]
+    order = [
+        "[1/2] Experiment 1",
+        "working on 1",
+        "Experiment 1 failed:",
+        "[2/2] Experiment 2",
+        "working on 2",
+        "Completed 1 of 2 experiments.",
+        "  Failed: 1 — DataNotFoundError: recording 1 missing",
+    ]
+    positions = [next((i for i, line in enumerate(lines) if line.startswith(text)), None) for text in order]
+    assert None not in positions, result.stdout
+    assert positions == sorted(positions), result.stdout
+
+
+def test_single_experiment_keeps_previous_failure_behavior(tmp_path, capsys):
+    assert run(tmp_path, [4], batch=False) == 0
+    assert [call["line_num"] for call in FakePipeline.calls] == [4]
+    FakePipeline.failing = {5}
+    assert run(tmp_path, [5], headless=True) == 1
+    with pytest.raises(DataNotFoundError):
+        run(tmp_path, [5], headless=False)
+    with pytest.raises(ConfigurationError):
+        run(tmp_path, [6], saved={6: {"channel_name": " "}})
+    capsys.readouterr()
+
+
+def test_line_nums_with_one_experiment_uses_batch_handling(tmp_path, capsys):
+    FakePipeline.failing = {5}
+    assert run(tmp_path, [5], headless=False, batch=True) == 1, "reported, not re-raised"
+    assert run(tmp_path, [6], saved={6: {"channel_name": " "}}, batch=True) == 1, "invalid settings reported"
+    assert "Completed 0 of 1 experiments." in capsys.readouterr().out
+
+
+def test_single_runs_need_exactly_one_experiment(tmp_path):
+    with pytest.raises(ValueError, match="exactly one"):
+        run(tmp_path, [1, 2], batch=False)
+
+
+def test_invalid_saved_settings_fail_only_that_experiment_in_a_batch(tmp_path, capsys):
+    assert run(tmp_path, [1, 2], saved={1: {"channel_name": " "}}) == 1
+    assert [call["line_num"] for call in FakePipeline.calls] == [2]
+    capsys.readouterr()
+
+
+MODULES = ["calcium_imaging", "ephys", "multimodal"]
+
+
+@pytest.mark.parametrize("module", MODULES)
+def test_real_entry_points_pass_the_selection_and_mode(module, monkeypatch, tmp_path):
+    target = importlib.import_module(f"aceneurotools.pipelines.{module}")
+    seen = []
+    monkeypatch.setattr(target, "run_pipeline_for_experiments", lambda **kwargs: seen.append(kwargs) or 0)
+    target.main(["--line-nums", "3", "4", "--project-path", str(tmp_path), "--headless", "--fail-fast"])
+    target.main(["--line-nums", "5", "--project-path", str(tmp_path)])
+    target.main(["--line-num", "6", "--project-path", str(tmp_path)])
+    assert [(kwargs["line_nums"], kwargs["batch"], kwargs["fail_fast"]) for kwargs in seen] == [
+        ([3, 4], True, True),
+        ([5], True, False),
+        ([6], False, False),
+    ]
+    assert seen[0]["headless"] is True and seen[1]["headless"] is False
+    pipeline_class = {
+        "calcium_imaging": "CalciumImagingPipeline",
+        "ephys": "EphysPipeline",
+        "multimodal": "MultimodalPipeline",
+    }[module]
+    from aceneurotools.shared.config_utils import load_analysis_params
+    from aceneurotools.shared.pipeline_defaults import pipeline_defaults
+
+    for kwargs in seen:
+        assert kwargs["pipeline_name"] == module
+        assert kwargs["pipeline_cls"] is getattr(target, pipeline_class)
+        assert kwargs["defaults"] == pipeline_defaults(module)
+        assert kwargs["csv_loader"] is load_analysis_params
+        assert kwargs["project_path"] == str(tmp_path) and kwargs["data_path"] is None
+
+
+@pytest.mark.parametrize("module", MODULES)
+def test_real_entry_points_exit_with_the_batch_code(module, monkeypatch, tmp_path):
+    target = importlib.import_module(f"aceneurotools.pipelines.{module}")
+    monkeypatch.setattr(target, "run_pipeline_for_experiments", lambda **kwargs: 1)
+    with pytest.raises(SystemExit) as raised:
+        target.main(["--line-nums", "1", "2", "--project-path", str(tmp_path)])
+    assert raised.value.code == 1
+
+
+@pytest.mark.parametrize("module", MODULES)
+def test_running_the_module_calls_main(module, monkeypatch, tmp_path):
+    importlib.import_module(f"aceneurotools.pipelines.{module}")  # Import heavy dependencies first.
+    seen = []
+    monkeypatch.setattr(cli_utils, "run_pipeline_for_experiments", lambda **kwargs: seen.append(kwargs) or 0)
+    monkeypatch.setattr(sys, "argv", [module, "--line-nums", "8", "9", "--project-path", str(tmp_path)])
+    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
+        runpy.run_module(f"aceneurotools.pipelines.{module}", run_name="__main__")
+    assert seen and seen[0]["line_nums"] == [8, 9] and seen[0]["batch"] is True
```
