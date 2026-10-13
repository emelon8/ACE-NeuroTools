"""ACE-Neuro pipeline orchestrators.

Public API
----------
EphysPipeline      — CLI wrapper: load → filter → phase → visualize one ephys channel.
MiniscopePipeline  — CLI wrapper: load → preprocess → CNMF-E → postprocess.
MultimodalPipeline — CLI wrapper: TTL sync + alignment between ephys and miniscope.
StatsPipeline      — CLI wrapper: coherence / scatter statistical analyses.
ComputePipeline    — Memory-safe mean-fluorescence extraction from raw video files.

Pipeline classes are imported on first access, so importing a statistics or
ephys pipeline does not require the optional compiled movie stack.
PySimpleGUI is imported lazily inside gui_utils functions. These pipelines are
intended as CLI entry points; for programmatic use prefer the sub-package APIs
directly (aceneurotools.ephys, aceneurotools.miniscope, aceneurotools.multimodal).
"""

from importlib import import_module

__all__ = [
    "EphysPipeline",
    "MiniscopePipeline",
    "MultimodalPipeline",
    "StatsPipeline",
    "ComputePipeline",
]

_MODULES = {
    "EphysPipeline": "ephys",
    "MiniscopePipeline": "miniscope",
    "MultimodalPipeline": "multimodal",
    "StatsPipeline": "stats",
    "ComputePipeline": "compute",
}


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{_MODULES[name]}"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
