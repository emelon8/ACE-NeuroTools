"""The installed frontend settings and run interfaces have a shared contract."""

import importlib
import inspect

import pytest

from aceneurotools.shared.pipeline_defaults import pipeline_defaults, pipeline_keys


@pytest.mark.parametrize("kind", ["miniscope", "ephys", "multimodal"])
def test_shared_options_match_public_pipeline_run(kind):
    module = importlib.import_module("aceneurotools.pipelines." + kind)
    pipeline = getattr(
        module, {"miniscope": "MiniscopePipeline", "ephys": "EphysPipeline", "multimodal": "MultimodalPipeline"}[kind]
    )
    public = set(inspect.signature(pipeline.run).parameters) - {
        "self",
        "line_num",
        "project_path",
        "data_path",
        "headless",
    }
    assert pipeline_keys(kind) == public
    assert set(pipeline_defaults(kind)) <= public


def test_each_frontend_gets_independent_nested_defaults():
    first = pipeline_defaults("miniscope")
    second = pipeline_defaults("miniscope")
    first["filenames"].append("another.avi")
    assert first["filenames"] != second["filenames"]
    assert second == pipeline_defaults("miniscope")
