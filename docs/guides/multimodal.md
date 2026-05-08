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
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project

# Run with explicit project and data paths
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --data-path /my/raw_data

# Run in headless mode
python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /my/project --headless
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

1. **Ephys Processing**: Runs the full ephys pipeline (channel loading, filtering, phase analysis)
2. **Miniscope Processing**: Runs the full miniscope pipeline (preprocessing, CNMF-E, postprocessing)
3. **Timestamp Synchronization**: Aligns Neuralynx and Miniscope timestamps using TTL events
4. **TTL Event Detection**: Identifies and optionally cleans TTL synchronization events
5. **Phase-Based Event Analysis**: Computes calcium event phases relative to ephys oscillations
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

All ephys and miniscope parameters from their respective pipelines also apply here.

## Data Requirements

The `experiments.csv` must contain both:
- `calcium imaging directory`: Path to miniscope recordings
- `ephys directory`: Path to Neuralynx recordings

Both directories should contain data from the same synchronized recording session.
