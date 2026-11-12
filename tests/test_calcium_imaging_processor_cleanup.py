"""The CaImAn worker pool is stopped whether calcium processing succeeds or fails."""

from types import SimpleNamespace

import numpy as np
import pytest

from aceneurotools.calcium_imaging import calcium_imaging_processor as module
from aceneurotools.calcium_imaging.calcium_imaging_processor import CalciumImagingProcessor
from aceneurotools.shared.exceptions import ProcessingError


@pytest.fixture
def processor(monkeypatch):
    stops = []
    processor = object.__new__(CalciumImagingProcessor)
    processor.data_manager = SimpleNamespace(
        opts_caiman=None, CNMFE_obj=None, estimates_filepath=None, motion_corrected_movie_filepath=None, fr=20.0
    )
    monkeypatch.setattr(module.cm.cluster, "setup_cluster", lambda **kwargs: ("cluster", "worker-pool", 2))
    monkeypatch.setattr(module.cm, "stop_server", lambda dview=None: stops.append(dview))
    monkeypatch.setattr(processor, "motion_correction_manager", lambda dm, *args: dm)
    monkeypatch.setattr(processor, "cnmfe_parameter_handler", lambda dm, plot_params=False: (dm, np.zeros((3, 4, 4))))
    monkeypatch.setattr(module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(processor, "_save_processed_data", lambda dm, *args: dm)
    return processor, stops


def test_successful_run_stops_the_worker_pool_once(processor):
    processor, stops = processor
    processor.process_calcium_movie(parallel=True, run_CNMFE=False)
    assert stops == ["worker-pool"]
    assert processor.result.estimates_filepath is None


@pytest.mark.parametrize("stage", ["motion_correction_manager", "cnmfe_parameter_handler", "_save_processed_data"])
def test_failed_run_still_stops_the_worker_pool(processor, monkeypatch, stage):
    processor, stops = processor

    def fail(*args, **kwargs):
        raise ProcessingError(f"{stage} failed")

    monkeypatch.setattr(processor, stage, fail)
    with pytest.raises(ProcessingError, match=f"{stage} failed"):
        processor.process_calcium_movie(parallel=True, run_CNMFE=False)
    assert stops == ["worker-pool"]
    assert not hasattr(processor, "result"), "no result is reported for a failed run"


def test_cnmfe_failure_still_stops_the_worker_pool(processor, monkeypatch):
    processor, stops = processor

    def fit(images):
        raise MemoryError("not enough memory")

    monkeypatch.setattr(module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: SimpleNamespace(fit=fit))
    with pytest.raises(ProcessingError, match="CNMFE failed: not enough memory"):
        processor.process_calcium_movie(parallel=True, run_CNMFE=True)
    assert stops == ["worker-pool"]


def test_serial_runs_make_the_same_stop_call_as_before(processor):
    processor, stops = processor
    processor.process_calcium_movie(parallel=False, run_CNMFE=False)
    assert stops == [None]


def test_a_failing_stop_is_only_a_warning(processor, monkeypatch, capsys):
    processor, _ = processor

    def stop(dview=None):
        raise OSError("already stopped")

    monkeypatch.setattr(module.cm, "stop_server", stop)
    processor.process_calcium_movie(parallel=True, run_CNMFE=False)
    assert "Warning: could not stop CaImAn processing server: already stopped" in capsys.readouterr().out


class FittedCNMF:
    """Records the quality-score calls the processor makes after a successful fit."""

    def __init__(self, fail_scoring=False):
        self.calls = []
        self.fail_scoring = fail_scoring
        self.params = SimpleNamespace(set=lambda group, values: self.calls.append(("set", group, values)))
        self.estimates = SimpleNamespace(evaluate_components=self.evaluate)

    def fit(self, images):
        self.calls.append(("fit", images.shape))

    def evaluate(self, images, params, dview=None):
        if self.fail_scoring:
            raise RuntimeError("scores unavailable")
        self.calls.append(("evaluate", images.shape, params is self.params, dview))


@pytest.mark.parametrize("fail_scoring", [False, True])
def test_quality_scores_are_computed_inside_the_cleanup_block(processor, monkeypatch, capsys, fail_scoring):
    processor, stops = processor
    fitted = FittedCNMF(fail_scoring)
    monkeypatch.setattr(module.cm.source_extraction.cnmf, "CNMF", lambda **kwargs: fitted)
    processor.process_calcium_movie(parallel=True, run_CNMFE=True, save_estimates=True)

    expected = [("fit", (3, 4, 4)), ("set", "quality", {"min_SNR": 3, "rval_thr": 0.85, "use_cnn": False})]
    if fail_scoring:
        assert fitted.calls == expected
        assert "Warning: component quality scores could not be computed: scores unavailable" in capsys.readouterr().out
    else:
        assert fitted.calls == expected + [("evaluate", (3, 4, 4), True, "worker-pool")]
    assert stops == ["worker-pool"]


def test_successful_run_saves_results_before_stopping_the_worker_pool(processor, monkeypatch):
    processor, stops = processor
    events = []
    monkeypatch.setattr(module.cm, "stop_server", lambda dview=None: events.append(("stop", dview)))
    monkeypatch.setattr(processor, "_save_processed_data", lambda dm, *args: events.append(("save",)) or dm)
    processor.process_calcium_movie(parallel=True, run_CNMFE=False)
    assert events == [("save",), ("stop", "worker-pool")]
