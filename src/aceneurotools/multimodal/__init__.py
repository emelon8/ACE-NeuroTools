"""ACE-NeuroTools multimodal alignment subpackage.

Cross-modal work only: aligning miniscope calcium imaging to the ephys clock
and relating calcium events to ephys/miniscope signal phases.

Modules
-------
alignment                — TTL sync, calcium-frame ↔ ephys-index mapping.
phase_utils              — Phase extraction at calcium events + histograms.
calcium_ephys_visualizer — Side-by-side calcium movie / ephys trace animation
                           (resource-heavy; import directly when needed).

Configuration classes (LabConfig, StatsConfig) live in ``aceneurotools.config``;
the statistical engines and toolbox live in ``aceneurotools.stats``.
"""

from aceneurotools.multimodal.alignment import (
    find_ca_movie_filenums,
    find_ca_movie_frame_num_of_ephys_idx,
    find_ephys_idx_of_TTL_events,
    sync_neuralynx_miniscope_timestamps,
)

__all__ = [
    "sync_neuralynx_miniscope_timestamps",
    "find_ephys_idx_of_TTL_events",
    "find_ca_movie_frame_num_of_ephys_idx",
    "find_ca_movie_filenums",
]
