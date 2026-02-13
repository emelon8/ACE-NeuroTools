# Multimodal Pipeline

The multimodal pipeline combines ephys and calcium imaging analysis for synchronized electrophysiology and miniscope recordings. It handles timestamp alignment between Neuralynx and Miniscope systems, and performs phase-based calcium event analysis.

## Quick Start

### Prerequisites

1. Set up your project's `.env` file (see root [README](../../README.md)):
   ```
   PROJECT_REPO=/path/to/your/project
   ```

2. Ensure your project has:
   - `experiments.csv` with both ephys and miniscope paths
   - `analysis_parameters.csv` with parameters for both modalities

### Command Line

```bash
# Run using analysis_parameters.csv from PROJECT_REPO (set in .env)
python -m src2.multimodal.multimodal_pipeline --line-num 97

# Run in headless mode (no GUI) for batch processing
python -m src2.multimodal.multimodal_pipeline --line-num 97 --headless
```

### Python API

```python
from src2.multimodal.multimodal_pipeline import MultimodalPipeline
from src2.shared.config_utils import load_analysis_params

params = load_analysis_params(97)
api = MultimodalPipeline()
api.run(line_num=97, headless=True, **params)
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
