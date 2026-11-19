# Multimodal Pipeline

The multimodal pipeline combines ephys and calcium imaging analysis for synchronized electrophysiology and miniscope recordings. It handles timestamp alignment between Neuralynx and Miniscope systems, and performs phase-based calcium event analysis.

## Quick Start

### Prerequisites

1. Ensure your project directory has:
   - `experiments.csv` with both ephys and miniscope paths
   - `analysis_parameters.csv` with parameters for both modalities

### Command Line

```bash
# Run with explicit project path
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run with explicit project and data paths
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data --headless

# Run several experiments one after another (see "Run several experiments" in Getting started)
python -m aceneurotools.pipelines.multimodal --line-nums 97 98 --project-path /my/project --data-path /my/raw_data --headless
```

### Python API

```python
from aceneurotools.pipelines.multimodal import MultimodalPipeline

api = MultimodalPipeline()
api.run(
    line_num=97, 
    project_path="/my/project",
    data_path="/my/raw_data",
    headless=True
)
```

## Pipeline Steps

1. **Ephys Processing**: Loads the requested channel and applies requested processing.
2. **Miniscope Processing**: Runs the full miniscope pipeline (preprocessing, CNMF-E, postprocessing)
3. **Timestamp Synchronization**: Aligns Neuralynx and Miniscope timestamps using TTL events
4. **TTL Event Detection**: Identifies and optionally cleans TTL synchronization events
5. **Phase-Based Event Analysis**: Computes requested calcium event phases relative to available oscillation phases.
6. **Phase Histograms**: Generates circular histograms of calcium event phase distributions

## Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `delete_TTLs` | Remove problematic TTL events | `True` |
| `fix_TTL_gaps` | Correct gaps in TTL timing | `True` |
| `only_experiment_events` | Restrict to experimental time window | `False` |
| `all_TTL_events` | Use all detected TTL events | `True` |
| `ca_events` | Analyze calcium events | `True` |
| `time_range` | Time window to analyze (seconds) | `None` |

The combined pipeline accepts a selected subset of ephys and calcium options;
check its [run signature](../api/pipelines.md) before forwarding settings.
The table above gives shared command-line defaults, which the GUI also inherits.
Direct Python defaults differ: `fix_TTL_gaps=False`, `only_experiment_events=True`,
`ca_events=False`, and `save_estimates=True`. The shared command defaults instead
set `save_estimates=False`; enable estimates saving explicitly for later review.
Filtering is off unless `filter_type` is supplied, and event-phase analysis is
conditional on the requested events/phases. The steps below describe capabilities,
not a promise that every output is computed for every run.

## Export a calcium + ephys movie

After a multimodal run, `create_ca_ephys_movie` (in
`aceneurotools.multimodal.calcium_ephys_visualizer`) draws calcium frames with the
ephys trace, and optionally mean fluorescence and an infusion marker, on top.
Choose one movie with `movie_num` or a period with `time_range` (seconds, as a
list or tuple). Continuing the Python example above, where `api.run(...)` has
finished:

```python
from aceneurotools.multimodal.calcium_ephys_visualizer import create_ca_ephys_movie

dm = api.calcium_imaging_pipeline.calcium_imaging_data_manager
# Use the name of an ephys channel loaded by the run, as in channel_name.
channel = api.ephys_pipeline.ephys_data_manager.get_channel("YourChannel")
path = create_ca_ephys_movie(dm, api.ephys_idx_all_TTL_events, channel,
                             movie_num=3, save_movie=True, headless=True)
```

- Movies are found by their exact name (`3.avi`) in the calcium imaging directory
  or its subfolders (except `saved_movies`), never by prefix. In both modes, a
  missing movie raises `FileNotFoundError`, and a name found in two folders (for
  example a behavior camera's movie) raises `ValueError`; set
  `calcium imaging directory` to the miniscope folder. Previously a missing movie
  only printed a message.
- `save_movie=True` writes `saved_movies/miniscope_ephys_movie3.mp4` (or
  `miniscope_ephys_<start>-<end>s.mp4` for a time range, with the times written
  exactly), or to `output_path` if given, and returns the path. Saving the same
  selection again replaces the earlier file. This replaces the single
  `miniscope_ephys_animation.mp4` earlier versions overwrote.
- The movie plays, on screen and in the saved MP4, at one frame every
  `playback_interval` milliseconds (default 33, about 30 frames per second).
  Raise it to slow the movie down or lower it to speed it up; set it to
  `1000 / frameRate` for real time.
- Saving MP4 files needs ffmpeg. If matplotlib cannot find it, a `RuntimeError`
  is raised before the movie is loaded; other save errors are raised, and the
  figure is closed.
- `headless=True` never opens windows and needs `save_movie=True`. It crops only
  with supplied or saved coordinates (`crop=True` without either is an error), does
  not play the movie, and raises errors that the interactive mode prints (missing
  metadata, nothing to overlay, no movie or time range given). Without it, the
  movie plays in a window as before.
- If no event label starts with "start", the infusion marker is skipped with a
  warning.

## Data Requirements

The `experiments.csv` must contain both:
- `calcium imaging directory`: Path to miniscope recordings
- `ephys directory`: Path to Neuralynx recordings

Both directories should contain data from the same synchronized recording session.


## TTL synchronization and gap detection

TTL pulses are synchronization markers used to map movie frames to electrical
recording times. Verify that the recordings belong to the same session, their
frame rate is correct, and the pulse mapping matches the acquisition. The reader
may instead use the shared ONIX hardware clock. Inspect aligned frame times and
`low_confidence_periods` before accepting results. Gap-repair settings change
alignment behavior and require acquisition-specific review; they do not prove
that missing synchronization data has been recovered correctly.

For GUI runs, review both input lists and the enabled alignment/event options.
Results stay in separate `.ace-runs` folders. See [the workbench guide](../gui.md).
