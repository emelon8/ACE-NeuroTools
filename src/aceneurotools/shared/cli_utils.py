"""Helpers for consistent pipeline CLI parameter handling."""

from __future__ import annotations

import argparse
import copy
import inspect
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any

from aceneurotools.shared.calcium_imaging_names import options_for_keys
from aceneurotools.shared.exceptions import AceNeuroError, ConfigurationError, print_cli_error

#: Errors reported per experiment instead of ending a multi-experiment command.
RUN_ERRORS = (AceNeuroError, FileNotFoundError, ValueError)


def run_allowed_keys(run_callable: Callable[..., Any]) -> set[str]:
    """Return accepted kwargs for a pipeline run() method."""
    return {
        name
        for name, param in inspect.signature(run_callable).parameters.items()
        if name != "self" and param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }


def build_run_params(
    *,
    defaults: dict[str, Any],
    allowed_keys: set[str],
    line_num: int,
    project_path: str,
    data_path: str | None,
    headless: bool,
    csv_loader: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Build run params with canonical precedence: defaults -> CSV -> CLI."""
    params = options_for_keys(defaults, allowed_keys)
    params["line_num"] = line_num

    try:
        csv_params = csv_loader(line_num, project_path=Path(project_path))
    except FileNotFoundError as e:
        warnings.warn(str(e), stacklevel=2)
        csv_params = {}

    for key, value in options_for_keys(csv_params, allowed_keys).items():
        if key in allowed_keys:
            params[key] = value
        else:
            warnings.warn(f"Ignoring unknown analysis_parameters key: {key}", stacklevel=2)

    params["project_path"] = project_path
    if data_path:
        params["data_path"] = data_path
    params["headless"] = bool(headless)
    return params


def validate_common_inputs(*, line_num: Any, project_path: Any, data_path: Any = None) -> None:
    """Validate required common CLI inputs before pipeline execution."""
    if not isinstance(line_num, int) or line_num < 0:
        raise ConfigurationError(
            "line_num must be a non-negative integer.",
            stage="validate_cli_inputs",
            hint="Pass --line-num or --line-nums with valid experiment row numbers.",
        )
    if not isinstance(project_path, (str, Path)) or not str(project_path).strip():
        raise ConfigurationError(
            "project_path must be a non-empty path.",
            stage="validate_cli_inputs",
            hint="Pass --project-path to the directory containing experiments.csv.",
        )
    project = Path(project_path)
    if not project.exists() or not project.is_dir():
        raise ConfigurationError(
            f"project_path does not exist or is not a directory: {project}",
            stage="validate_cli_inputs",
            hint="Check --project-path and ensure it points to your project directory.",
        )
    if data_path is not None:
        if not isinstance(data_path, (str, Path)) or not str(data_path).strip():
            raise ConfigurationError(
                "data_path must be a non-empty path when provided.",
                stage="validate_cli_inputs",
                hint="Either omit --data-path or provide a valid directory path.",
            )
        data = Path(data_path)
        if not data.exists() or not data.is_dir():
            raise ConfigurationError(
                f"data_path does not exist or is not a directory: {data}",
                stage="validate_cli_inputs",
                hint="Fix --data-path to point at your raw data directory.",
            )


def validate_run_params(*, pipeline_name: str, run_params: dict[str, Any]) -> None:
    """Validate critical pipeline-specific run parameters."""
    validate_common_inputs(
        line_num=run_params.get("line_num"),
        project_path=run_params.get("project_path"),
        data_path=run_params.get("data_path"),
    )

    if pipeline_name == "ephys":
        channel_name = run_params.get("channel_name")
        if not isinstance(channel_name, str) or not channel_name.strip():
            raise ConfigurationError(
                "channel_name must be a non-empty string.",
                stage="validate_ephys_params",
                hint="Set channel_name in CSV or defaults to a valid channel.",
            )

    if pipeline_name in {"miniscope", "calcium_imaging", "multimodal"}:
        key = "filenames" if pipeline_name in {"miniscope", "calcium_imaging"} else (
            "calcium_imaging_filenames" if "calcium_imaging_filenames" in run_params else "miniscope_filenames"
        )
        filenames = run_params.get(key)
        if isinstance(filenames, str):
            run_params[key] = [filenames]
            filenames = run_params[key]
        if filenames is None:
            run_params[key] = []
            filenames = []
        if not isinstance(filenames, list):
            raise ConfigurationError(
                f"{key} must be a list of movie filenames.",
                stage="validate_miniscope_params",
                hint="Use a list such as ['0.avi'] for miniscope input movies.",
            )
        if any((not isinstance(name, str)) or (not name.strip()) for name in filenames):
            raise ConfigurationError(
                f"{key} contains invalid filename values.",
                stage="validate_miniscope_params",
                hint="Ensure all movie names are non-empty strings.",
            )


def apply_headless_policy(*, pipeline_name: str, run_params: dict[str, Any]) -> dict[str, Any]:
    """Apply consistent headless policy across CLI entrypoints."""
    if not bool(run_params.get("headless", False)):
        return run_params

    if pipeline_name in {"ephys", "multimodal"}:
        run_params["plot_channel"] = False
        run_params["plot_spectrogram"] = False
        run_params["plot_phases"] = False

    if pipeline_name in {"miniscope", "calcium_imaging", "multimodal"}:
        run_params["inspect_motion_correction"] = False
        run_params["remove_components_with_gui"] = False
        run_params["plot_params"] = False

    return run_params


def add_experiment_arguments(parser: argparse.ArgumentParser) -> None:
    """Add ``--line-num`` / ``--line-nums`` (one is required) and ``--fail-fast``.

    ``--line-nums`` may be repeated; the values are added together.
    """
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--line-num', type=int,
                       help="Experiment line number from experiments.csv")
    group.add_argument('--line-nums', type=int, nargs='+', action='extend', metavar='N',
                       help="Several experiment line numbers, run one after another with each experiment's "
                            "saved settings (repeating the flag adds more)")
    parser.add_argument('--fail-fast', action='store_true',
                        help="With --line-nums, stop at the first experiment that fails")


def parse_experiment_args(parser: argparse.ArgumentParser, argv: list[str] | None = None) -> argparse.Namespace:
    """Parse arguments added by :func:`add_experiment_arguments` and check how they combine."""
    args = parser.parse_args(argv)
    if args.fail_fast and args.line_nums is None:
        parser.error("--fail-fast applies only with --line-nums")
    if args.line_nums is not None and any(line_num < 0 for line_num in args.line_nums):
        parser.error("--line-nums takes non-negative experiment row numbers")
    return args


def selected_line_nums(args: argparse.Namespace) -> list[int]:
    """Return the requested experiments in order, without repeats."""
    if args.line_num is not None:
        return [args.line_num]
    return list(dict.fromkeys(args.line_nums))


def _failure_summary(error: BaseException) -> str:
    text = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    cause = error.__cause__
    if cause is not None:
        text += f" (cause: {type(cause).__name__}: {cause})" if str(cause) else f" (cause: {type(cause).__name__})"
    return text


def _print_batch_summary(
    line_nums: list[int],
    completed: list[int],
    failed: list[tuple[int, str]],
    stopped: tuple[int | None, BaseException] | None = None,
) -> int:
    processed = len(completed) + len(failed) + (1 if stopped else 0)
    not_run = line_nums[processed:]
    print(f"\nCompleted {len(completed)} of {len(line_nums)} experiments.", flush=True)
    for line_num, summary in failed:
        print(f"  Failed: {line_num} — {summary}", file=sys.stderr)
    if stopped:
        line_num, error = stopped
        where = f" at {line_num}" if line_num is not None else ""
        print(f"  Stopped{where} by {_failure_summary(error)}", file=sys.stderr)
    if not_run:
        reason = "the stop" if stopped else "--fail-fast"
        print(f"  Not run after {reason}: {' '.join(map(str, not_run))}", file=sys.stderr)
    sys.stderr.flush()
    return 1 if failed or not_run else 0


def run_pipeline_for_experiments(
    *,
    pipeline_name: str,
    pipeline_cls: type,
    defaults: dict[str, Any],
    line_nums: list[int],
    project_path: str,
    data_path: str | None,
    headless: bool,
    csv_loader: Callable[..., dict[str, Any]],
    batch: bool,
    fail_fast: bool = False,
) -> int:
    """Run a per-experiment pipeline CLI and return its exit code.

    ``batch`` is False for ``--line-num``, which keeps the original
    single-experiment behavior: invalid settings raise, and a run error exits 1
    when headless or is re-raised. ``batch`` is True for ``--line-nums``, even
    with one experiment:

    - The project and data paths are checked once; if they are invalid, nothing runs
      and the exit code is 1.
    - Each experiment gets a new pipeline instance, a fresh copy of the defaults and
      its own saved settings.
    - A failed experiment (an error in ``RUN_ERRORS``) is reported with its cause and
      the next one runs, unless ``fail_fast``. The exit code is 1 when any experiment
      failed or was not run.
    - Any other exception, including ``KeyboardInterrupt``, stops the command: the
      summary so far is printed and the exception is re-raised.

    Only the error text of a failure is kept, so a failed experiment's data can be
    freed before the next one.
    """
    if not batch and len(line_nums) != 1:
        raise ValueError("A single-experiment run needs exactly one line number.")

    def prepare(line_num: int) -> dict[str, Any]:
        run_params = build_run_params(
            defaults=copy.deepcopy(defaults),
            allowed_keys=run_allowed_keys(pipeline_cls.run),
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            headless=headless,
            csv_loader=csv_loader,
        )
        apply_headless_policy(pipeline_name=pipeline_name, run_params=run_params)
        validate_run_params(pipeline_name=pipeline_name, run_params=run_params)
        return run_params

    if not batch:
        run_params = prepare(line_nums[0])
        try:
            pipeline_cls().run(**run_params)
        except RUN_ERRORS as exc:
            print_cli_error(exc, include_cause=headless)
            if headless:
                return 1
            raise
        return 0

    try:
        validate_common_inputs(line_num=0, project_path=project_path, data_path=data_path)
    except ConfigurationError as exc:
        print_cli_error(exc)
        print(f"No experiments were run ({len(line_nums)} requested).", file=sys.stderr)
        return 1

    completed: list[int] = []
    failed: list[tuple[int, str]] = []
    current: int | None = None
    try:
        for index, line_num in enumerate(line_nums, start=1):
            current = line_num
            print(f"\n[{index}/{len(line_nums)}] Experiment {line_num}", flush=True)
            try:
                pipeline_cls().run(**prepare(line_num))
            except RUN_ERRORS as exc:
                sys.stdout.flush()  # Keep merged stdout/stderr logs in order.
                print(f"Experiment {line_num} failed:", file=sys.stderr)
                # A batch never re-raises a run error, so always show its cause here.
                print_cli_error(exc, include_cause=True)
                failed.append((line_num, _failure_summary(exc)))
                if fail_fast:
                    current = None
                    break
            else:
                completed.append(line_num)
            finally:
                # Release figures between experiments; each run can create many.
                if "matplotlib.pyplot" in sys.modules:
                    sys.modules["matplotlib.pyplot"].close("all")
            current = None
    except BaseException as exc:
        _print_batch_summary(line_nums, completed, failed, stopped=(current, exc))
        raise
    return _print_batch_summary(line_nums, completed, failed)
