# Multimodal Module Documentation

This directory contains the logic for synchronizing and analyzing the relationship between Calcium Imaging (Miniscope) and Electrophysiology (Ephys) data.

## Core Components

### `MultimodalAPI` (`multimodal_api.py`)
The high-level interface for running joint analyses.

## Configuration

This API uses a combined YAML configuration that includes Ephys, Miniscope, and Multimodal-specific parameters.

**Template:** [`multimodal_config.yaml`](multimodal_config.yaml)

### Key Parameters

| Section | Parameter | Description |
|---------|-----------|-------------|
| `experiment` | `line_num`, `filenames` | Experiment identifier and video files |
| `ephys` | `channel_name`, `filter_type`, `filter_range` | EEG/LFP settings |
| `miniscope_*` | (preprocessing, processing, postprocessing) | Calcium imaging settings |
| `multimodal` | `delete_TTLs` | Remove TTL artifacts from ephys |
| `multimodal` | `fix_TTL_gaps` | Interpolate missing TTL pulses |
| `multimodal` | `only_experiment_events` | Use only events during experiment |
| `multimodal` | `all_TTL_events` | Include all TTL events |
| `multimodal` | `ca_events` | Use calcium events for phase analysis |
| `multimodal` | `time_range` | Optional `[start, end]` in seconds |

See the template file for the complete parameter list.

### Usage

```bash
# Option 1: Config file (Recommended)
python src2/multimodal/multimodal_api.py --config src2/multimodal/multimodal_config.yaml

# Option 2: Headless mode (for Slurm/remote)
python src2/multimodal/multimodal_api.py --config multimodal_config.yaml --headless

# Option 3: Parameters in code (legacy)
api = MultimodalAPI()
api.run(line_num=96, channel_name="PFCLFPvsCBEEG", ...)
```

*   **Workflow:**
    1.  Runs `EphysAPI` to clean and filter electrophysiology data.
    2.  Runs `MiniscopeAPI` to preprocess and extract calcium traces.
    3.  Synchronizes the two data streams using TTL pulses.
    4.  Performs cross-modal analysis (e.g., phase locking, cross-correlation).

## Visualization & Analysis

### `calcium_ephys_visualizer.py`
Tools for creating visual comparisons between the two modalities.
*   **Key Function:** `create_ca_ephys_movie`
    *   Generates a side-by-side movie of the Miniscope video and the scrolling Ephys trace.

### `phase_utils.py`
Utilities for analyzing the phase relationship between LFP oscillations and Calcium events.
*   **Key Functions:**
    *   `ephys_phase_ca_events`: Computes the phase of the Ephys signal at the time of Calcium spikes.
    *   `miniscope_phase_ca_events`: Computes the phase of the Miniscope global signal at the time of individual neuron spikes.
    *   `phase_ca_events_histogram`: Plots histograms of phase distributions to test for phase-locking.

## Core Utilities

### Synchronization Logic (`miniscope_ephys_alignment_utils.py`)

The core challenge is aligning two different timebases. We rely on **TTL pulses** sent from the Miniscope acquisition system to the Neuralynx Ephys system.

#### `sync_neuralynx_miniscope_timestamps`
*   **Input:** An Ephys `Channel` object and a `MiniscopeDataManager`.
*   **Mechanism:**
    1.  Extracts timestamps of "TTL Input" events from `channel.events`.
    2.  Verifies that these TTLs alternate (High/Low) and follow the expected frame rate.
    3.  **Gap Correction:** If `fix_TTL_gaps=True`, it detects missing pulses (dropped frames) by checking for time gaps larger than a threshold (default ~65ms) and interpolates the missing timestamps.
*   **Output:** `tCaIm` (Corrected array of timestamps where each index corresponds to a Miniscope frame).

#### `find_ephys_idx_of_TTL_events`
*   **Purpose:** Maps the continuous Ephys time vector to the discrete Miniscope frames.
*   **Algorithm:** Nearest-neighbor search. For each Miniscope timestamp in `tCaIm`, it finds the index of the closest time point in `channel.time_vector`.
*   **Result:** `ephys_idx_all_TTL_events` (Array of indices).
    *   `channel.signal[ephys_idx_all_TTL_events[i]]` gives the voltage at the moment Frame `i` was captured.

## Analysis Workflow Summary

1.  **Run Ephys API:** To clean and filter LFP data.
2.  **Run Miniscope API:** To extract Calcium traces (`C`).
3.  **Sync:** Use `sync_neuralynx_miniscope_timestamps` to align the time axes.
4.  **Joint Analysis:**
    *   **Phase Locking:** Compute the phase of the LFP signal at the exact indices of Calcium events (`find_ca_events`).
    *   **Cross-Correlation:** Correlate `miniscope_data.C` with the Hilbert envelope of `channel.signal_filtered`.

## Outputs

*   **Phase-Locking Histograms:** Calculated EEG phase at the exact timestamps of Calcium events.
    *   **Interpretation:** Examine the resulting histograms to determine if neuronal activity is modulated by specific LFP oscillations (e.g., locking to the trough of Theta).
*   **Aligned Data:** Time-aligned data structures, allowing for correlation analysis between calcium amplitude and EEG power.

