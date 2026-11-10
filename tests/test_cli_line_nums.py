"""Per-experiment CLIs accept one or several experiments with explicit failure handling."""

import argparse
import gc
import importlib
import runpy
import sys
import weakref

import pytest

from aceneurotools.shared import cli_utils
from aceneurotools.shared.cli_utils import (
    add_experiment_arguments,
    parse_experiment_args,
    run_pipeline_for_experiments,
    selected_line_nums,
)
from aceneurotools.shared.exceptions import ConfigurationError, DataNotFoundError


class FakePipeline:
    """Accepts the keys the ephys headless policy sets, like the real EphysPipeline.run."""

    calls: list = []
    instances: list = []
    failing: set = set()
    hook = None

    def run(
        self,
        line_num,
        project_path,
        data_path=None,
        channel_name="CH1",
        plot_channel=True,
        plot_spectrogram=True,
        plot_phases=True,
        filter_range=None,
        headless=False,
    ):
        FakePipeline.instances.append(self)
        FakePipeline.calls.append(
            {
                "line_num": line_num,
                "channel_name": channel_name,
                "plots": (plot_channel, plot_spectrogram, plot_phases),
                "filter_range": list(filter_range),
            }
        )
        if FakePipeline.hook:
            FakePipeline.hook(self, line_num, filter_range)
        if line_num in FakePipeline.failing:
            raise DataNotFoundError(f"recording {line_num} missing")


@pytest.fixture(autouse=True)
def reset_fake():
    FakePipeline.calls, FakePipeline.instances, FakePipeline.failing, FakePipeline.hook = [], [], set(), None


def parser():
    result = argparse.ArgumentParser()
    add_experiment_arguments(result)
    return result


def run(tmp_path, line_nums, *, headless=True, fail_fast=False, saved=None, batch=None):
    saved = saved or {}
    return run_pipeline_for_experiments(
        pipeline_name="ephys",
        pipeline_cls=FakePipeline,
        defaults={"channel_name": "CH1", "plot_channel": True, "filter_range": [0.5, 4]},
        line_nums=line_nums,
        project_path=str(tmp_path),
        data_path=None,
        headless=headless,
        csv_loader=lambda line_num, project_path: saved.get(line_num, {}),
        batch=len(line_nums) > 1 if batch is None else batch,
        fail_fast=fail_fast,
    )


def test_line_num_and_line_nums_are_exclusive_and_one_is_required(capsys):
    assert selected_line_nums(parse_experiment_args(parser(), ["--line-num", "7"])) == [7]
    assert selected_line_nums(parse_experiment_args(parser(), ["--line-nums", "9", "7", "9"])) == [9, 7]
    for argv in ([], ["--line-num", "1", "--line-nums", "2"]):
        with pytest.raises(SystemExit):
            parse_experiment_args(parser(), argv)
    capsys.readouterr()


def test_fail_fast_is_rejected_without_line_nums(capsys):
    with pytest.raises(SystemExit) as raised:
        parse_experiment_args(parser(), ["--line-num", "1", "--fail-fast"])
    assert raised.value.code == 2
    assert "--fail-fast applies only with --line-nums" in capsys.readouterr().err
    assert parse_experiment_args(parser(), ["--line-nums", "1", "--fail-fast"]).fail_fast is True


def test_each_experiment_uses_its_own_saved_settings_and_new_instance(tmp_path):
    assert run(tmp_path, [1, 2], saved={2: {"channel_name": "CH2"}}) == 0
    assert [(call["line_num"], call["channel_name"]) for call in FakePipeline.calls] == [(1, "CH1"), (2, "CH2")]
    # The headless policy turns every ephys plot off, for every experiment.
    assert all(call["plots"] == (False, False, False) for call in FakePipeline.calls)
    first, second = FakePipeline.instances
    assert first is not second


def test_defaults_are_copied_for_each_experiment(tmp_path):
    def mutate(pipeline, line_num, filter_range):
        filter_range.append(99)

    FakePipeline.hook = mutate
    assert run(tmp_path, [1, 2, 3]) == 0
    assert [call["filter_range"] for call in FakePipeline.calls] == [[0.5, 4]] * 3


def test_failed_experiment_is_reported_and_the_next_one_runs(tmp_path, capsys):
    FakePipeline.failing = {2}
    assert run(tmp_path, [1, 2, 3], headless=False) == 1
    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2, 3]
    captured = capsys.readouterr()
    assert "Completed 2 of 3 experiments." in captured.out
    assert "Failed: 2 — DataNotFoundError: recording 2 missing" in captured.err


def test_a_failed_experiment_is_released_before_the_next_one(tmp_path):
    """Only the error text is kept, so the failed pipeline (and its data) can be freed."""
    FakePipeline.failing = {1}
    released, first = [], {}

    def check(pipeline, line_num, filter_range):
        if line_num == 1:
            first["ref"] = weakref.ref(pipeline)
        else:
            FakePipeline.instances.clear()  # Drop the test's own reference to experiment 1.
            gc.collect()
            released.append(first["ref"]() is None)

    FakePipeline.hook = check
    assert run(tmp_path, [1, 2]) == 1
    assert released == [True]


def test_figures_are_closed_between_experiments(tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    open_at_start = []

    def draw(pipeline, line_num, filter_range):
        open_at_start.append(len(plt.get_fignums()))
        plt.figure()

    FakePipeline.hook = draw
    FakePipeline.failing = {2}
    assert run(tmp_path, [1, 2, 3]) == 1
    assert open_at_start == [0, 0, 0] and plt.get_fignums() == []


def test_fail_fast_stops_and_lists_experiments_not_run(tmp_path, capsys):
    FakePipeline.failing = {2}
    assert run(tmp_path, [1, 2, 3], fail_fast=True) == 1
    assert [call["line_num"] for call in FakePipeline.calls] == [1, 2]
    assert "Not run after --fail-fast: 3" in capsys.readouterr().err


def test_errors_outside_run_failures_stop_the_batch(tmp_path):
    def broken(pipeline, line_num, filter_range):
        raise TypeError("programming error")

    FakePipeline.hook = broken
    with pytest.raises(TypeError, match="programming error"):
        run(tmp_path, [1, 2])
    assert [call["line_num"] for call in FakePipeline.calls] == [1]


def test_single_experiment_keeps_previous_failure_behavior(tmp_path, capsys):
    assert run(tmp_path, [4], batch=False) == 0
    assert [call["line_num"] for call in FakePipeline.calls] == [4]
    FakePipeline.failing = {5}
    assert run(tmp_path, [5], headless=True) == 1
    with pytest.raises(DataNotFoundError):
        run(tmp_path, [5], headless=False)
    with pytest.raises(ConfigurationError):
        run(tmp_path, [6], saved={6: {"channel_name": " "}})
    capsys.readouterr()


def test_line_nums_with_one_experiment_uses_batch_handling(tmp_path, capsys):
    FakePipeline.failing = {5}
    assert run(tmp_path, [5], headless=False, batch=True) == 1, "reported, not re-raised"
    assert run(tmp_path, [6], saved={6: {"channel_name": " "}}, batch=True) == 1, "invalid settings reported"
    assert "Completed 0 of 1 experiments." in capsys.readouterr().out


def test_single_runs_need_exactly_one_experiment(tmp_path):
    with pytest.raises(ValueError, match="exactly one"):
        run(tmp_path, [1, 2], batch=False)


def test_invalid_saved_settings_fail_only_that_experiment_in_a_batch(tmp_path, capsys):
    assert run(tmp_path, [1, 2], saved={1: {"channel_name": " "}}) == 1
    assert [call["line_num"] for call in FakePipeline.calls] == [2]
    capsys.readouterr()


MODULES = ["calcium_imaging", "ephys", "multimodal"]


@pytest.mark.parametrize("module", MODULES)
def test_real_entry_points_pass_the_selection_and_mode(module, monkeypatch, tmp_path):
    target = importlib.import_module(f"aceneurotools.pipelines.{module}")
    seen = []
    monkeypatch.setattr(target, "run_pipeline_for_experiments", lambda **kwargs: seen.append(kwargs) or 0)
    target.main(["--line-nums", "3", "4", "--project-path", str(tmp_path), "--headless", "--fail-fast"])
    target.main(["--line-nums", "5", "--project-path", str(tmp_path)])
    target.main(["--line-num", "6", "--project-path", str(tmp_path)])
    assert [(kwargs["line_nums"], kwargs["batch"], kwargs["fail_fast"]) for kwargs in seen] == [
        ([3, 4], True, True),
        ([5], True, False),
        ([6], False, False),
    ]
    assert seen[0]["headless"] is True and seen[1]["headless"] is False


@pytest.mark.parametrize("module", MODULES)
def test_real_entry_points_exit_with_the_batch_code(module, monkeypatch, tmp_path):
    target = importlib.import_module(f"aceneurotools.pipelines.{module}")
    monkeypatch.setattr(target, "run_pipeline_for_experiments", lambda **kwargs: 1)
    with pytest.raises(SystemExit) as raised:
        target.main(["--line-nums", "1", "2", "--project-path", str(tmp_path)])
    assert raised.value.code == 1


@pytest.mark.parametrize("module", MODULES)
def test_running_the_module_calls_main(module, monkeypatch, tmp_path):
    importlib.import_module(f"aceneurotools.pipelines.{module}")  # Import heavy dependencies first.
    seen = []
    monkeypatch.setattr(cli_utils, "run_pipeline_for_experiments", lambda **kwargs: seen.append(kwargs) or 0)
    monkeypatch.setattr(sys, "argv", [module, "--line-nums", "8", "9", "--project-path", str(tmp_path)])
    with pytest.warns(RuntimeWarning, match="found in sys.modules"):
        runpy.run_module(f"aceneurotools.pipelines.{module}", run_name="__main__")
    assert seen and seen[0]["line_nums"] == [8, 9] and seen[0]["batch"] is True
