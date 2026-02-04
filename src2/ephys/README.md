# Ephys Module Documentation

This directory handles the import and processing of Electrophysiology (EEG/LFP) data, primarily from Neuralynx systems.

## Core Components

### `EphysPipeline` (`ephys_pipeline.py`)
The main entry point for processing electrophysiology data.

## Configuration

This API supports YAML configuration files for reproducible experiments.

**Template:** [`ephys_config.yaml`](ephys_config.yaml)

### Parameters

| Section | Parameter | Type | Description |
|---------|-----------|------|-------------|
| `experiment` | `line_num` | int | Row number in `experiments.csv` |
| `ephys` | `channel_name` | string | Neuralynx CSC channel name (e.g., "PFCLFPvsCBEEG") |
| `ephys` | `remove_artifacts` | bool | Enable artifact removal via thresholding |
| `ephys` | `filter_type` | string/null | Filter type: "butter", "fir", or null |
| `ephys` | `filter_range` | [float, float] | Frequency band [low, high] in Hz |
| `ephys.visualization` | `plot_channel` | bool | Plot raw/filtered signal trace |
| `ephys.visualization` | `plot_spectrogram` | bool | Plot multitaper spectrogram |
| `ephys.visualization` | `plot_phases` | bool | Plot phase histogram |
| - | `logging_level` | string | DEBUG, INFO, WARNING, ERROR, CRITICAL |

### Usage

```bash
# Option 1: Config file (Recommended)
python src2/ephys/ephys_pipeline.py --config src2/ephys/ephys_config.yaml

# Option 2: Headless mode (for Slurm/remote)
python src2/ephys/ephys_pipeline.py --config ephys_config.yaml --headless

# Option 3: Parameters in code (legacy)
api = EphysPipeline()
api.run(line_num=101, channel_name="PFCLFPvsCBEEG", ...)
```

*   **Key Responsibilities:**
    *   Interacts with `ExperimentDataManager` to locate the data.
    *   Verifies data integrity (via `file_downloader`).
    *   Orchestrates `EphysDataManager` to import blocks and process channels.
    *   Handles high-level filtering and phase computation requests.
    *   Uses `ChannelWorker` to generate plots and spectrograms.

### `EphysDataManager` (`ephys_data_manager.py`)
Manages the `Neo` library interface and `Channel` storage.
*   **Import Logic:**
    *   Uses `neo.io.NeuralynxIO` to read the raw directory.
    *   Locates the `Events.nev` file to establish the recording context.
*   **Processing:**
    *   `process_ephys_block_to_channels`: Converts the complex `Neo` Block structure into a flat dictionary of `Channel` objects stored in `self.channels`.
*   **Filtering:**
    *   `filter_ephys()` uses `scipy.signal.filtfilt` (zero-phase filtering).
    *   Supports `butter` (Butterworth) and `fir` (Finite Impulse Response) filter types.



### `BlockProcessor` (`block_processor.py`)
Handles the low-level processing of Neo `Block` objects into clean `Channel` objects.
*   **Key Responsibilities:**
    *   `process_raw_ephys`: Iterates through requested channels and extracts them from the Neo structure.
    *   `_scan_segments`: Stitches together non-continuous recording segments (e.g., from paused recordings) into a continuous signal, handling interpolation for gaps.
    *   `remove_artifacts`: Optional artifact removal using thresholding and Hann window smoothing.

### `Channel` (`channel.py`)
A lightweight data class representing a single electrode or signal source.
*   **Attributes:**
    *   `name` (str): Identifier (e.g., "PFCLFPvsCBEEG").
    *   `signal` (np.array): Raw voltage trace.
    *   `sampling_rate` (float): Samples per second (Hz).
    *   `time_vector` (np.array): Time points corresponding to each sample in `signal`.
    *   `events` (dict): Neuralynx events (TTL pulses) associated with this recording block.
    *   `signal_filtered` (np.array): Populated by `EphysDataManager.filter_ephys`.
    *   `phases` (np.array): Instantaneous phase (radians) computed via Hilbert transform.

## Helpers & Visualization



### `Spectrogram` (`spectrogram.py`)
A simple data container for spectrogram results.
*   **Attributes:**
    *   `psd_matrix_db` (np.array): Power Spectral Density matrix in decibels.
    *   `time_points` (np.array): Array of time points.
    *   `freq_points` (np.array): Array of frequency points.



### `ChannelWorker` (`channel_worker.py`)
A helper class that wraps a `Channel` object to perform specific operations, keeping the data class clean.
*   **Capabilities:**
    *   `compute_spectrogram`: Generates a multitaper spectrogram using `multitaper_spectrogram_python`.
    *   `plot_spectrogram`: Visualizes the spectral power over time.
    *   `plot_phases`: Plots the histogram of phase angles.

### `Visualizer` (`visualizer.py`)
Handles the Matplotlib backend logic for plotting signals and spectrograms.
*   **Key Methods:**
    *   `plot_channel`: Standard voltage-vs-time plot.
    *   `plot_spectrogram_helper`: Renders the spectrogram heatmap with a colormap and axis labels.

## Usage Note

When extending this module, always retrieve data via the manager:

```python
dm = EphysDataManager(directory)
# Access a specific channel by name
my_channel = dm.channels['PFCLFPvsCBEEG']
# Plot raw signal
plt.plot(my_channel.time_vector, my_channel.signal)
```