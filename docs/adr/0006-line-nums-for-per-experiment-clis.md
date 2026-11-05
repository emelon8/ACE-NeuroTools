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
- Pipeline `run()` methods and numerical results are unchanged.
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

## Verification

Diff not test-verified: no test environment was available. The diff applies to
base commit `9e47959` and every changed Python file passed
`python -m py_compile`. Once the locked environment exists (`environment.yml` /
`conda-lock.yml`, then `pip install -e ".[dev]"`), run:

```sh
python -m pytest tests/test_cli_line_nums.py tests/test_cli_config.py -q
python -m pytest tests/test_gui_parity.py tests/test_pipeline_defaults.py tests/test_gui_shared_defaults.py -q
python -m pytest -q
ruff check src/aceneurotools/shared/cli_utils.py src/aceneurotools/pipelines tests/test_cli_line_nums.py
```

Most of `tests/test_cli_line_nums.py` needs only the shared modules; the
entry-point test is skipped without CaImAn.

## Diff

```diff
diff --git a/src/aceneurotools/pipelines/calcium_imaging.py b/src/aceneurotools/pipelines/calcium_imaging.py
index 7499d68..33e2a76 100644
--- a/src/aceneurotools/pipelines/calcium_imaging.py
+++ b/src/aceneurotools/pipelines/calcium_imaging.py
@@ -17,18 +17,15 @@ from aceneurotools.calcium_imaging.pipeline_results import (
 )
 from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS, accept_legacy_keywords, alias_attribute
 from aceneurotools.shared.cli_utils import (
-    apply_headless_policy,
-    build_run_params,
-    run_allowed_keys,
-    validate_run_params,
+    add_experiment_arguments,
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
 
@@ -386,7 +383,7 @@ class CalciumImagingPipeline:
         )
 
 
-def main():
+def main(argv=None):
     parser = argparse.ArgumentParser(
         description="Run Calcium Imaging Analysis Pipeline",
         formatter_class=argparse.RawDescriptionHelpFormatter,
@@ -397,10 +394,12 @@ Examples:
 
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
@@ -408,32 +407,22 @@ Examples:
     parser.add_argument('--headless', action='store_true',
                         help="Run in headless mode (no GUI)")
 
-    args = parser.parse_args()
-
-    # Default parameters
-    defaults = pipeline_defaults("calcium_imaging")
+    args = parser.parse_args(argv)
 
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
index 12188c0..e0779b0 100644
--- a/src/aceneurotools/pipelines/ephys.py
+++ b/src/aceneurotools/pipelines/ephys.py
@@ -9,16 +9,11 @@ from aceneurotools.ephys.ephys_data_manager import EphysDataManager
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
+    run_pipeline_for_experiments,
+    selected_line_nums,
 )
+from aceneurotools.shared.exceptions import PipelineExecutionError
 from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
 
 
@@ -288,7 +283,7 @@ class EphysPipeline:
 
 
 
-if __name__ == "__main__":
+def main(argv=None):
     parser = argparse.ArgumentParser(
         description="Run Ephys Analysis Pipeline",
         formatter_class=argparse.RawDescriptionHelpFormatter,
@@ -299,10 +294,12 @@ Examples:
 
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
@@ -310,29 +307,23 @@ Examples:
     parser.add_argument('--headless', action='store_true',
                         help="Run in headless mode (no GUI)")
 
-    args = parser.parse_args()
-
-    # Default parameters
-    defaults = pipeline_defaults("ephys")
+    args = parser.parse_args(argv)
 
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
index f247c65..48fafb0 100644
--- a/src/aceneurotools/pipelines/multimodal.py
+++ b/src/aceneurotools/pipelines/multimodal.py
@@ -19,13 +19,12 @@ from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline
 from aceneurotools.pipelines.ephys import EphysPipeline
 from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS, accept_legacy_keywords, alias_attribute
 from aceneurotools.shared.cli_utils import (
-    apply_headless_policy,
-    build_run_params,
-    run_allowed_keys,
-    validate_run_params,
+    add_experiment_arguments,
+    run_pipeline_for_experiments,
+    selected_line_nums,
 )
 from aceneurotools.shared.config_utils import load_analysis_params
-from aceneurotools.shared.exceptions import AceNeuroError, PipelineExecutionError, print_cli_error
+from aceneurotools.shared.exceptions import PipelineExecutionError
 from aceneurotools.shared.pipeline_defaults import pipeline_defaults
 
 
@@ -344,7 +343,7 @@ class MultimodalPipeline:
         self.phase_bin_edges_calcium_imaging = bin_edges2
 
 
-if __name__ == "__main__":
+def main(argv=None):
     parser = argparse.ArgumentParser(
         description="Run Multimodal Analysis Pipeline",
         formatter_class=argparse.RawDescriptionHelpFormatter,
@@ -355,10 +354,12 @@ Examples:
 
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
@@ -366,28 +367,22 @@ Examples:
     parser.add_argument('--headless', action='store_true',
                         help="Run in headless mode (no GUI)")
 
-    args = parser.parse_args()
-
-    # Default parameters
-    defaults = pipeline_defaults("multimodal")
+    args = parser.parse_args(argv)
 
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
index 4c38152..81e89b8 100644
--- a/src/aceneurotools/shared/cli_utils.py
+++ b/src/aceneurotools/shared/cli_utils.py
@@ -2,14 +2,19 @@
 
 from __future__ import annotations
 
+import argparse
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
@@ -149,3 +154,94 @@ def apply_headless_policy(*, pipeline_name: str, run_params: dict[str, Any]) ->
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
+    fail_fast: bool = False,
+) -> int:
+    """Run a per-experiment pipeline CLI and return its exit code.
+
+    One experiment keeps the original single-experiment behavior: invalid
+    settings raise, and a run error exits 1 when headless or is re-raised.
+    Several experiments each get a new pipeline instance and their own saved
+    settings. A failed experiment is reported and the next one runs (unless
+    ``fail_fast``); the exit code is 1 when any experiment failed or was skipped.
+    """
+    def prepare(line_num: int) -> dict[str, Any]:
+        run_params = build_run_params(
+            defaults=defaults,
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
+    if len(line_nums) == 1:
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
+    failed: list[tuple[int, BaseException]] = []
+    for index, line_num in enumerate(line_nums, start=1):
+        print(f"\n[{index}/{len(line_nums)}] Experiment {line_num}", flush=True)
+        try:
+            pipeline_cls().run(**prepare(line_num))
+        except RUN_ERRORS as exc:
+            print(f"Experiment {line_num} failed:", file=sys.stderr)
+            print_cli_error(exc, include_cause=headless)
+            failed.append((line_num, exc))
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
+    for line_num, exc in failed:
+        print(f"  Failed: {line_num} — {exc}", file=sys.stderr)
+    if not_run:
+        print(f"  Not run after --fail-fast: {' '.join(map(str, not_run))}", file=sys.stderr)
+    return 1 if failed or not_run else 0
diff --git a/tests/test_cli_line_nums.py b/tests/test_cli_line_nums.py
new file mode 100644
index 0000000..f09bb0b
--- /dev/null
+++ b/tests/test_cli_line_nums.py
@@ -0,0 +1,106 @@
+"""Per-experiment CLIs accept one or several experiments with explicit failure handling."""
+
+import argparse
+
+import pytest
+
+from aceneurotools.shared.cli_utils import (
+    add_experiment_arguments,
+    run_pipeline_for_experiments,
+    selected_line_nums,
+)
+from aceneurotools.shared.exceptions import DataNotFoundError
+
+
+class FakePipeline:
+    calls: list = []
+    failing: set = set()
+
+    def run(self, line_num, project_path, data_path=None, channel_name="CH1", plot_channel=True, headless=False):
+        FakePipeline.calls.append({"line_num": line_num, "channel_name": channel_name, "plot_channel": plot_channel, "instance": id(self)})
+        if line_num in FakePipeline.failing:
+            raise DataNotFoundError(f"recording {line_num} missing")
+
+
+@pytest.fixture(autouse=True)
+def reset_fake():
+    FakePipeline.calls, FakePipeline.failing = [], set()
+
+
+def parse(argv):
+    parser = argparse.ArgumentParser()
+    add_experiment_arguments(parser)
+    return parser.parse_args(argv)
+
+
+def run(tmp_path, line_nums, *, headless=True, fail_fast=False, saved=None):
+    saved = saved or {}
+    return run_pipeline_for_experiments(
+        pipeline_name="ephys",
+        pipeline_cls=FakePipeline,
+        defaults={"channel_name": "CH1", "plot_channel": True},
+        line_nums=line_nums,
+        project_path=str(tmp_path),
+        data_path=None,
+        headless=headless,
+        csv_loader=lambda line_num, project_path: saved.get(line_num, {}),
+        fail_fast=fail_fast,
+    )
+
+
+def test_line_num_and_line_nums_are_exclusive_and_one_is_required(capsys):
+    assert selected_line_nums(parse(["--line-num", "7"])) == [7]
+    assert selected_line_nums(parse(["--line-nums", "9", "7", "9"])) == [9, 7]
+    for argv in ([], ["--line-num", "1", "--line-nums", "2"]):
+        with pytest.raises(SystemExit):
+            parse(argv)
+    capsys.readouterr()
+
+
+def test_each_experiment_uses_its_own_saved_settings_and_new_instance(tmp_path):
+    assert run(tmp_path, [1, 2], saved={2: {"channel_name": "CH2"}}) == 0
+    assert [(call["line_num"], call["channel_name"]) for call in FakePipeline.calls] == [(1, "CH1"), (2, "CH2")]
+    assert all(call["plot_channel"] is False for call in FakePipeline.calls)  # headless policy per experiment
+    assert len({call["instance"] for call in FakePipeline.calls}) == 2
+
+
+def test_failed_experiment_is_reported_and_the_next_one_runs(tmp_path, capsys):
+    FakePipeline.failing = {2}
+    assert run(tmp_path, [1, 2, 3], headless=False) == 1
+    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2, 3]
+    captured = capsys.readouterr()
+    assert "Completed 2 of 3 experiments." in captured.out
+    assert "Failed: 2" in captured.err
+
+
+def test_fail_fast_stops_and_lists_experiments_not_run(tmp_path, capsys):
+    FakePipeline.failing = {2}
+    assert run(tmp_path, [1, 2, 3], fail_fast=True) == 1
+    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2]
+    assert "Not run after --fail-fast: 3" in capsys.readouterr().err
+
+
+def test_single_experiment_keeps_previous_failure_behavior(tmp_path, capsys):
+    FakePipeline.failing = {5}
+    assert run(tmp_path, [5], headless=True) == 1
+    with pytest.raises(DataNotFoundError):
+        run(tmp_path, [5], headless=False)
+    capsys.readouterr()
+
+
+def test_invalid_saved_settings_fail_only_that_experiment_in_a_batch(tmp_path, capsys):
+    assert run(tmp_path, [1, 2], saved={1: {"channel_name": " "}}) == 1
+    assert [call["line_num"] for call in FakePipeline.calls] == [2]
+    capsys.readouterr()
+
+
+@pytest.mark.parametrize("module", ["calcium_imaging", "ephys", "multimodal"])
+def test_real_entry_points_accept_line_nums(module, monkeypatch, tmp_path):
+    pytest.importorskip("caiman")
+    import importlib
+
+    target = importlib.import_module(f"aceneurotools.pipelines.{module}")
+    seen = {}
+    monkeypatch.setattr(target, "run_pipeline_for_experiments", lambda **kwargs: seen.update(kwargs) or 0)
+    target.main(["--line-nums", "3", "4", "--project-path", str(tmp_path), "--headless", "--fail-fast"])
+    assert seen["line_nums"] == [3, 4] and seen["fail_fast"] is True and seen["headless"] is True
```
