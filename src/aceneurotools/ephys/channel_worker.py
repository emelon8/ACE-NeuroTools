from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.spectrogram import Spectrogram
from aceneurotools.ephys.visualizer import Visualizer
from aceneurotools.shared.multitaper_spectrogram_python import multitaper_spectrogram
import numpy as np
import matplotlib.pyplot as plt
from typing import Optional, List, Union, Tuple, Any

class ChannelWorker:
    """Worker class for processing and visualizing a single ephys channel.
    
    Provides methods for plotting raw/filtered signals, computing spectrograms,
    and visualizing phase distributions.
    
    Attributes:
        channel: The Channel object to process.
        visualizer: Visualizer instance for plotting.
        spectrogram: Computed Spectrogram object (set after computation).
    """

    channel: Channel
    visualizer: Visualizer
    spectrogram: Optional[Spectrogram]
    
    def __init__(self, channel: Channel):
        """Initialize a ChannelWorker with a Channel object.
        
        Args:
            channel: Channel object containing signal data to process.
        """
        self.channel = channel
        self.visualizer = Visualizer()
        self.spectrogram = None

    def plot_channel(self, use_filtered: bool = False) -> None:
        """Plot the channel's time-domain signal.
        
        Args:
            use_filtered: If True, plot the filtered signal; otherwise plot raw.
        """
        self.visualizer.plot_channel(self.channel, use_filtered)


    def plot_spectrogram(
        self, 
        window_length: float = 30, 
        window_step: float = 3,
        freq_limits: List[float] = [0, 50], 
        time_bandwidth: float = 2, 
        plot_events: bool = False, 
        use_filtered: bool = False
    ) -> Optional[Spectrogram]:
        """Compute and plot the spectrogram for this channel.
        
        Args:
            window_length: Length of each window in seconds.
            window_step: Step size between windows in seconds.
            freq_limits: [min_freq, max_freq] range to display.
            time_bandwidth: Time-bandwidth product for multitaper method.
            plot_events: If True, overlay event markers on the spectrogram.
            use_filtered: If True, use the filtered signal.
            
        Returns:
            Spectrogram object with computed PSD data.
        """
        spectrogram: Spectrogram = self.compute_spectrogram(self.channel, window_length, window_step, freq_limits, time_bandwidth, use_filtered)

        events = None if not plot_events else self.channel.events
        self.visualizer.plot_spectrogram(spectrogram, events = events)
        return self.spectrogram
    

    def compute_spectrogram(
        self, 
        channel: Channel, 
        window_length: float = 30, 
        window_step: float = 3,
        freq_limits: List[float] = [0, 50], 
        time_bandwidth: float = 2, 
        use_filtered: bool = False
    ) -> Spectrogram:
        """Compute the multitaper spectrogram for a channel.
        
        Args:
            channel: Channel object with signal data.
            window_length: Length of each window in seconds.
            window_step: Step size between windows in seconds.
            freq_limits: [min_freq, max_freq] range to compute.
            time_bandwidth: Time-bandwidth product for multitaper method.
            use_filtered: If True, use the filtered signal.
            
        Returns:
            Spectrogram object with PSD data in decibels.
        """
        signal = channel.signal_filtered if use_filtered and channel.signal_filtered is not None else channel.signal
        fs = channel.sampling_rate

        # Spectrogram parameters
        num_tapers = int(time_bandwidth * 2 - 1)
        window_params = [window_length, window_step]  # [window length (s), step size (s)]

        result = multitaper_spectrogram(
            signal, fs, freq_limits, time_bandwidth, num_tapers, window_params, plot_on=False
        )
        psd, stimes, sfreqs = result[:3]

        
        # Convert to decibel scale (dB re 1 µV²/Hz)
        psd_db = 10 * np.log10(psd)

        # Create Spectrogram object and save it to self.spectrogram
        self.spectrogram = Spectrogram(psd_db, stimes, sfreqs)
        return self.spectrogram

    def plot_phases(self) -> None:
        """Plot a histogram of instantaneous phase values for the channel.
        
        Displays diagnostic information about the phase data and creates
        a histogram showing the distribution of phases from -π to +π.
        """
        if self.channel.phases is None:
            print("No phases computed for this channel. Skipping plot.")
            return

        # Step 1: Verify data and sampling rate
        print("Sampling rate:", self.channel.sampling_rate)
        print("Length of phases:", len(self.channel.phases))
        print("Min and Max phase:", np.min(self.channel.phases), np.max(self.channel.phases))
        print("Any NaN values?", np.any(np.isnan(self.channel.phases)))
        print("Any infinite values?", np.any(np.isinf(self.channel.phases)))
    
        # Step 2: Plot a histogram of phase values
        plt.figure(figsize=(10, 6), facecolor='white')  # Create a figure with white background
        plt.hist(self.channel.phases, bins=50, color='blue', alpha=0.7, label=f'Phase Distribution of {self.channel.name}')
        plt.title(f"Histogram of Phase Values for {self.channel.name}")
        plt.xlabel("Phase (radians)")
        plt.ylabel("Frequency")
        plt.xlim(-np.pi, np.pi)  # Phase range: -π to +π
        plt.grid(True, alpha=0.3)  # Light grid for readability
        plt.legend(loc='upper right')  # Explicit legend location
        plt.show()
