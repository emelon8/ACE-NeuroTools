# Ephys Module Documentation

This directory handles the import and processing of Electrophysiology (EEG/LFP) data, primarily from Neuralynx systems.

## Core Components

### `EphysAPI` (`ephys_api.py`)
The main entry point for processing electrophysiology data.
*   **Usage:**
    ```python
    api = EphysAPI()
    api.run(line_num=..., channel_name=..., remove_artifacts=..., ...)
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