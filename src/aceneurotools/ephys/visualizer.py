import numpy as np
import matplotlib.pyplot as plt
from aceneurotools.shared.multitaper_spectrogram_python import multitaper_spectrogram
from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.spectrogram import Spectrogram
import logging
from typing import Optional, Union, Tuple, List, Any, Dict


class Visualizer:
    """Class for visualizing ephys data."""
    
    logger: logging.Logger

    def __init__(self, level: Union[str, int] = 'CRITICAL') -> None:
        """Initialize the Visualizer with a logging level.
        
        Args:
            level: Logging level string (e.g., 'DEBUG', 'INFO', 'CRITICAL').
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)


    def plot_channel(self, channel: Channel, use_filtered: bool = False) -> None:
        """Visualize the processed channel."""
        self.logger.info(f"Plotting channel...")

        signal = channel.signal_filtered if use_filtered and channel.signal_filtered is not None else channel.signal
        self.logger.debug(f"signal to be plotted: {signal}")
        plt.figure()
        plt.plot(channel.time_vector, signal)
        plt.title(channel.name)
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (µV)')
        plt.show()
    

    def plot_spectrogram_helper(
        self, 
        psd: np.ndarray, 
        stimes: np.ndarray, 
        sfreqs: np.ndarray, 
        events: Optional[Dict[str, Any]] = None
    ) -> Tuple[plt.Figure, plt.Axes]:
        """Create a spectrogram plot with optional event markers.
        
        Args:
            psd: 2D array of PSD values in decibels.
            stimes: 1D array of time values in seconds.
            sfreqs: 1D array of frequency values in Hz.
            events: Optional event data to overlay on the plot.
            
        Returns:
            Tuple of (figure, axes) matplotlib objects.
        """
        self.logger.info(f"Plotting spectrogram...")
        
        fig, ax = plt.subplots()
        mesh = ax.pcolormesh(stimes / 60, sfreqs, psd,
                            shading='gouraud', cmap='inferno')
        plt.colorbar(mesh, ax=ax, label='Power (dB)')
        ax.set_xlabel('Time (min)')
        ax.set_ylabel('Frequency (Hz)')
        
        if events:
            self._mark_events(ax, events)
            
        plt.show()
        return fig, ax
    
    def plot_spectrogram(self, spectrogram: Spectrogram, events: Optional[Dict[str, Any]] = None) -> None:
        """Plot a Spectrogram object with optional event markers.
        
        Convenience wrapper around plot_spectrogram_helper that accepts
        a Spectrogram object instead of raw arrays.
        
        Args:
            spectrogram: Spectrogram object with PSD data.
            events: Optional event data to overlay on the plot.
        """
        self.plot_spectrogram_helper(spectrogram.psd, spectrogram.stimes, spectrogram.sfreqs, events)
    
    def _mark_events(self, axisHandle: plt.Axes, events: Dict[str, Any]) -> None:
        """Add vertical lines and labels for events on a plot.
        
        Draws dashed vertical lines at event timestamps with rotated
        text labels. Currently limited to first 10 events.
        
        Args:
            axisHandle: Matplotlib axes object to draw on.
            events: Dict with 'labels' and 'timestamps' arrays for event markers.
            
        Note:
            TODO: Should only mark user-made events. Event structure
            may change in future versions.
        """
        self.logger.info(f"Marking events on plot...")
        yLimits = axisHandle.get_ylim()
        xLimits = axisHandle.get_xlim()
        lineLength = np.diff(yLimits)
        lineOffset = yLimits[0] + (lineLength / 2)

        if 'labels' not in events or 'timestamps' not in events:
            return

        labels = events['labels'][:10]
        timestamps = events['timestamps'][:10]
        
        for label, timestamp in zip(labels, timestamps):
            # Plot the event line
            axisHandle.axvline(x=timestamp, color='k', linestyle='--', alpha=0.7)
            # Add the label
            axisHandle.text(timestamp, yLimits[1], label, rotation=90, verticalalignment='bottom', fontsize=8)
        
        axisHandle.axis((xLimits[0], xLimits[1], yLimits[0], yLimits[1]))
