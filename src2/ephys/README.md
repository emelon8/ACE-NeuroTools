# Ephys Module Documentation

This directory handles the import and processing of Electrophysiology (EEG/LFP) data, primarily from Neuralynx systems.

## Core Components

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

### `EphysDataManager` (`ephys_data_manager.py`)
Manages the `Neo` library interface and `Channel` storage.
*   **Import Logic:**
    *   Uses `neo.io.NeuralynxIO` to read the raw directory.
    *   Locates the `Events.nev` file to establish the recording context.
*   **Processing:**
    *   Converts the complex `Neo` Block structure into a flat dictionary of `Channel` objects stored in `self.channels`.
*   **Filtering:**
    *   Method `filter_ephys()` uses `scipy.signal.filtfilt` (zero-phase filtering).
    *   Supports `butter` (Butterworth) and `fir` (Finite Impulse Response) filter types.

## Usage Note

When extending this module, always retrieve data via the manager:

```python
dm = EphysDataManager(directory)
# Access a specific channel by name
my_channel = dm.channels['PFCLFPvsCBEEG']
# Plot raw signal
plt.plot(my_channel.time_vector, my_channel.signal)
```
