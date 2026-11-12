---
status: proposed
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

Add three helpers to `shared/cli_utils.py` and use them in all three commands:

- `add_experiment_arguments(parser)`: a required, mutually exclusive
  `--line-num N` / `--line-nums N [N ...]` pair, plus `--fail-fast`.
- `selected_line_nums(args)`: the requested experiments in order, repeats
  removed.
- `run_pipeline_for_experiments(...)`: runs the pipeline and returns the exit code.

The ephys and multimodal commands move into `main(argv=None)` functions, as
calcium imaging already has, so tests can call them directly.

Failure handling:

| Case | Behavior |
| --- | --- |
| `--line-num N` (one experiment) | Unchanged: invalid settings raise; a run error prints, then exits 1 when headless or is re-raised. |
| `--line-nums` | Each experiment gets a new pipeline instance and its own saved settings. A settings or run error (`AceNeuroError`, `FileNotFoundError`, `ValueError`) is printed and the next experiment runs. Other exceptions, including `KeyboardInterrupt`, stop the command as before. |
| `--line-nums --fail-fast` | Stops at the first failure and lists experiments not run. |
| Exit code with `--line-nums` | 1 when any experiment failed or was not run, headless or not, so schedulers and scripts can detect partial failure. |

A summary (`Completed X of N experiments`, then each failure) is printed at the
end. Open matplotlib figures are closed between experiments.

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

## Implementation reviewed in this proposal

Add batch experiment selection and failure summaries. Always shut down the CaImAn worker pool on success and failure, isolate mutable defaults and avoid retaining failed pipeline objects through exceptions. Pipeline numerical calculations are unchanged.

## Risks

Experiments share one process and module-level state. Cleanup now also runs on failure. Review exit codes, fail-fast behavior, exception boundaries and repeated experiment handling; separate processes remain the isolation alternative.

## Tests

Focused regression tests: `tests/test_calcium_imaging_processor_cleanup.py`, `tests/test_cli_line_nums.py`.

## Verification

The exact implementation patch below is the full change against base `78acb6b` (main after PRs #152 and #153), excluding this ADR. The proposal remains `status: proposed`; publication as a draft PR is not maintainer approval.

Focused tests are rerun during PR preparation, with exact results recorded in the PR description. Earlier full-suite attempts were interrupted because this environment denied localhost socket creation; the same restriction reproduced on unchanged main. No green full-suite result is claimed. Full tests, changed-line coverage, strict documentation build and representative recording checks remain prerequisites for merge.

## Diff

```diff
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 0b97636..2f317e2 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -11,6 +11,8 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 
 - Remove the duplicate dark-mode switch from the bottom of the GUI navigation;
   the top-bar toggle remains (reported by @Aathok-Git).
+- Stop CaImAn's worker pool when a calcium run fails, so later runs in the same
+  Python session no longer fail with "A cluster is already running".
 - Align bundled CSV example rows with their headers and allow local recording
   checks when optional Box columns are absent.
 - Report a missing explicit CLI configuration as an error without launching setup.
@@ -39,6 +41,9 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
   patch layout and display limits shown by `plot_params` without opening windows,
   for example in a notebook. Analysis results are unchanged. With `plot_params`
   on, unusable `rf`/`stride` settings now stop the run with a clear error.
+- `--line-nums` (and `--fail-fast`) for the calcium imaging, ephys and multimodal
+  commands: run several experiments in one command, continue past failures, and
+  exit 1 if any failed.
 - Installed `ace-gui` workbench with per-launch API authentication and shared
   CLI/GUI defaults. CSVs remain the settings source of truth.
 - GUI feature registry and run plans: new workbench screens register their own
diff --git a/README.md b/README.md
index c4252c8..f670e87 100644
--- a/README.md
+++ b/README.md
@@ -72,6 +72,8 @@ For command-line analysis, replace the paths and ID with your own:
 python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data --headless
 python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /path/to/project --data-path /path/to/raw_data --headless
 python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project --data-path /path/to/raw_data --headless
+# Several experiments in one command; failures are reported and the rest still run:
+python -m aceneurotools.pipelines.ephys --line-nums 96 97 101 --project-path /path/to/project --data-path /path/to/raw_data --headless
 ```
 
 The ID matches the `line number` column; it is not a spreadsheet row position.
diff --git a/docs/api/shared.md b/docs/api/shared.md
index bc435bd..1746ca7 100644
--- a/docs/api/shared.md
+++ b/docs/api/shared.md
@@ -10,6 +10,17 @@ This section details the shared data structures and configuration utilities of t
 
 ::: aceneurotools.shared.config_utils.parse_analysis_params
 
+## Command-line helpers
+Shared by the per-experiment commands (`--line-num`, `--line-nums`, `--fail-fast`).
+
+::: aceneurotools.shared.cli_utils.add_experiment_arguments
+
+::: aceneurotools.shared.cli_utils.parse_experiment_args
+
+::: aceneurotools.shared.cli_utils.selected_line_nums
+
+::: aceneurotools.shared.cli_utils.run_pipeline_for_experiments
+
 ## Path Resolution
 ::: aceneurotools.shared.paths
 
diff --git a/docs/getting_started.md b/docs/getting_started.md
index 957e907..3efa16a 100644
--- a/docs/getting_started.md
+++ b/docs/getting_started.md
@@ -79,6 +79,30 @@ These examples need actual electrical channels and, for combined recordings,
 verified synchronization information. See the [ephys](guides/ephys.md) and
 [alignment](guides/multimodal.md) guides before running them.
 
+### Run several experiments
+
+Each of these commands also accepts `--line-nums` with several IDs. They run one
+after another in the same process, each with its own saved settings:
+
+```sh
+python -m aceneurotools.pipelines.calcium_imaging --line-nums 96 97 101 --project-path /path/to/project --data-path /path/to/raw_data --headless
+```
+
+- Use either `--line-num` or `--line-nums`, not both. Repeated IDs run once.
+- A failed experiment is reported and the next one runs. Add `--fail-fast` to stop
+  at the first failure instead (`--fail-fast` is only accepted with `--line-nums`).
+- At the end the command prints `Completed X of N experiments.`, then each failure
+  as `Failed: <ID> — <error type>: <message>`, and any IDs not run after
+  `--fail-fast`.
+- The exit code is `1` if any experiment failed or was not run, and `0` otherwise,
+  so scripts and job schedulers can detect partial failures. With `--line-num` the
+  exit code is unchanged.
+- Errors other than settings or recording problems (for example a programming error
+  or Ctrl+C) stop the whole command.
+
+To keep each experiment fully separate, for example on a cluster, run one
+`--line-num` command per experiment instead.
+
 ## 3. Passing parameters into the pipelines
 
 | Entry point | Effective settings |
diff --git a/docs/guides/calcium_imaging.md b/docs/guides/calcium_imaging.md
index 306e7e7..a1015d4 100644
--- a/docs/guides/calcium_imaging.md
+++ b/docs/guides/calcium_imaging.md
@@ -15,6 +15,9 @@ optional for modality commands but is needed to store overrides.
 python -m aceneurotools.pipelines.calcium_imaging --line-num 96 --project-path /my/project --data-path /my/raw_data --headless
 ```
 
+To run several experiments in one command, use `--line-nums`; see
+[Run several experiments](../getting_started.md#run-several-experiments).
+
 Replace the paths and experiment ID. The command enables extraction and saves
 estimates by default, selects `0.avi`, and does not enable motion correction by
 default. Set `filenames=[]` in saved settings to process all supported movies.
diff --git a/docs/guides/ephys.md b/docs/guides/ephys.md
index aa20279..aed868f 100644
--- a/docs/guides/ephys.md
+++ b/docs/guides/ephys.md
@@ -15,6 +15,9 @@ not exist in your recording.
 python -m aceneurotools.pipelines.ephys --line-num 96 --project-path /my/project --data-path /my/raw_data --headless
 ```
 
+To run several experiments in one command, use `--line-nums`; see
+[Run several experiments](../getting_started.md#run-several-experiments).
+
 `analysis_parameters.csv` is optional for this command; absent settings use
 command defaults. Filtering and phase calculation are off by default. The command
 normally requests channel/spectrogram plots, but headless mode suppresses them.
diff --git a/docs/guides/multimodal.md b/docs/guides/multimodal.md
index 31d4bbf..9883082 100644
--- a/docs/guides/multimodal.md
+++ b/docs/guides/multimodal.md
@@ -21,6 +21,9 @@ python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/pr
 
 # Run in headless mode
 python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data --headless
+
+# Run several experiments one after another (see "Run several experiments" in Getting started)
+python -m aceneurotools.pipelines.multimodal --line-nums 97 98 --project-path /my/project --data-path /my/raw_data --headless
 ```
 
 ### Python API
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
index 4c38152..1b3d57b 100644
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
@@ -149,3 +155,109 @@ def apply_headless_policy(*, pipeline_name: str, run_params: dict[str, Any]) ->
         run_params["plot_params"] = False
 
     return run_params
+
+
+def add_experiment_arguments(parser: argparse.ArgumentParser) -> None:
+    """Add ``--line-num`` / ``--line-nums`` (one is required) and ``--fail-fast``."""
+    group = parser.add_mutually_exclusive_group(required=True)
+    group.add_argument('--line-num', type=int,
+                       help="Experiment line number from experiments.csv")
+    group.add_argument('--line-nums', type=int, nargs='+', metavar='N',
+                       help="Several experiment line numbers, run one after another with each experiment's saved settings")
+    parser.add_argument('--fail-fast', action='store_true',
+                        help="With --line-nums, stop at the first experiment that fails")
+
+
+def parse_experiment_args(parser: argparse.ArgumentParser, argv: list[str] | None = None) -> argparse.Namespace:
+    """Parse arguments added by :func:`add_experiment_arguments` and check how they combine."""
+    args = parser.parse_args(argv)
+    if args.fail_fast and args.line_nums is None:
+        parser.error("--fail-fast applies only with --line-nums")
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
+    with one experiment: each experiment gets a new pipeline instance, a fresh
+    copy of the defaults and its own saved settings. A failed experiment is
+    reported and the next one runs (unless ``fail_fast``); the exit code is 1
+    when any experiment failed or was not run. Only the error text of a failure
+    is kept, so a failed experiment's data can be freed before the next one.
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
+    completed: list[int] = []
+    failed: list[tuple[int, str]] = []
+    for index, line_num in enumerate(line_nums, start=1):
+        print(f"\n[{index}/{len(line_nums)}] Experiment {line_num}", flush=True)
+        try:
+            pipeline_cls().run(**prepare(line_num))
+        except RUN_ERRORS as exc:
+            print(f"Experiment {line_num} failed:", file=sys.stderr)
+            print_cli_error(exc, include_cause=headless)
+            failed.append((line_num, f"{type(exc).__name__}: {exc}"))
+            if fail_fast:
+                break
+        else:
+            completed.append(line_num)
+        finally:
+            # Release figures between experiments; each run can create many.
+            if "matplotlib.pyplot" in sys.modules:
+                sys.modules["matplotlib.pyplot"].close("all")
+
+    not_run = line_nums[len(completed) + len(failed):]
+    print(f"\nCompleted {len(completed)} of {len(line_nums)} experiments.")
+    for line_num, summary in failed:
+        print(f"  Failed: {line_num} — {summary}", file=sys.stderr)
+    if not_run:
+        print(f"  Not run after --fail-fast: {' '.join(map(str, not_run))}", file=sys.stderr)
+    return 1 if failed or not_run else 0
diff --git a/tests/test_calcium_imaging_processor_cleanup.py b/tests/test_calcium_imaging_processor_cleanup.py
new file mode 100644
index 0000000..5340440
--- /dev/null
+++ b/tests/test_calcium_imaging_processor_cleanup.py
@@ -0,0 +1,110 @@
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
diff --git a/tests/test_cli_line_nums.py b/tests/test_cli_line_nums.py
new file mode 100644
index 0000000..279a82b
--- /dev/null
+++ b/tests/test_cli_line_nums.py
@@ -0,0 +1,247 @@
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
