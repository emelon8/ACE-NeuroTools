"""ACE-Neuro pipeline orchestrators.

Public API
----------
EphysPipeline      — CLI wrapper: load → filter → phase → visualize one ephys channel.
CalciumImagingPipeline  — CLI wrapper: load → preprocess → CNMF-E → postprocess.
MultimodalPipeline — CLI wrapper: TTL sync + alignment between ephys and miniscope.
StatsPipeline      — CLI wrapper: coherence / scatter statistical analyses.
ComputePipeline    — Memory-safe mean-fluorescence extraction from raw video files.

The calcium imaging and multimodal pipelines require CaImAn. For lightweight
stage configurations and results, import aceneurotools.calcium_imaging.
For programmatic analysis, the sub-package APIs are also available directly
(aceneurotools.ephys, aceneurotools.calcium_imaging, aceneurotools.multimodal).
"""

from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline
from aceneurotools.pipelines.compute import ComputePipeline
from aceneurotools.pipelines.ephys import EphysPipeline
from aceneurotools.pipelines.multimodal import MultimodalPipeline
from aceneurotools.pipelines.stats import StatsPipeline

MiniscopePipeline = CalciumImagingPipeline

__all__ = [
    "MiniscopePipeline",
    "EphysPipeline",
    "CalciumImagingPipeline",
    "MultimodalPipeline",
    "StatsPipeline",
    "ComputePipeline",
]
