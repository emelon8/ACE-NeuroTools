"""ACE-Neuro pipeline orchestrators.

Public API
----------
EphysPipeline      — CLI wrapper: load → filter → phase → visualize one ephys channel.
MiniscopePipeline  — CLI wrapper: load → preprocess → CNMF-E → postprocess.
MultimodalPipeline — CLI wrapper: TTL sync + alignment between ephys and miniscope.
StatsPipeline      — CLI wrapper: coherence / scatter statistical analyses.
ComputePipeline    — Memory-safe mean-fluorescence extraction from raw video files.

Note: caiman is imported inside MiniscopePipeline.run(), not at module level.
PySimpleGUI is imported lazily inside gui_utils functions.  These pipelines are
intended as CLI entry points; for programmatic use prefer the sub-package APIs
directly (aceneurotools.ephys, aceneurotools.miniscope, aceneurotools.multimodal).
"""

from aceneurotools.pipelines.compute import ComputePipeline
from aceneurotools.pipelines.ephys import EphysPipeline
from aceneurotools.pipelines.miniscope import MiniscopePipeline
from aceneurotools.pipelines.multimodal import MultimodalPipeline
from aceneurotools.pipelines.stats import StatsPipeline

__all__ = [
    "EphysPipeline",
    "MiniscopePipeline",
    "MultimodalPipeline",
    "StatsPipeline",
    "ComputePipeline",
]
