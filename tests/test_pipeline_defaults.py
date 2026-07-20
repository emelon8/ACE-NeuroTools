"""Guards against pipeline default-parameter drift.

The multitaper ``time_bandwidth`` default previously disagreed between the
Multimodal pipeline signature (23) and everywhere else (2). This test pins the
defaults together so they cannot silently diverge again.
"""

from __future__ import annotations

import inspect

import pytest


def test_time_bandwidth_default_consistent_across_pipelines():
    pytest.importorskip("caiman")
    from aceneurotools.pipelines.miniscope import MiniscopePipeline
    from aceneurotools.pipelines.multimodal import MultimodalPipeline

    mm = inspect.signature(MultimodalPipeline.run).parameters["time_bandwidth"].default
    ms = inspect.signature(MiniscopePipeline.run).parameters["time_bandwidth"].default
    assert mm == ms == 2
