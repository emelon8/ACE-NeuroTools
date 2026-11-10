# Multimodal API

Alignment and cross-modal analysis between Miniscope calcium imaging and electrophysiology.

**How to pass arguments:** same pattern as other pipelines — use `MultimodalPipeline.run(...)` with keyword arguments; see [Getting started](../getting_started.md) §3a and [Pipelines](pipelines.md).

## Multimodal pipeline

::: aceneurotools.pipelines.multimodal.MultimodalPipeline

## Alignment utilities

::: aceneurotools.multimodal.miniscope_ephys_alignment_utils.sync_neuralynx_miniscope_timestamps

::: aceneurotools.multimodal.miniscope_ephys_alignment_utils.find_ephys_idx_of_TTL_events

::: aceneurotools.multimodal.miniscope_ephys_alignment_utils.find_ca_movie_frame_num_of_ephys_idx

::: aceneurotools.multimodal.miniscope_ephys_alignment_utils.find_ca_movie_filenums

::: aceneurotools.multimodal.miniscope_ephys_alignment_utils.find_numbered_movies

## Calcium + ephys movie export

::: aceneurotools.multimodal.calcium_ephys_visualizer.create_ca_ephys_movie
