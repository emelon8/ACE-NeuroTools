#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import numpy as np
import matplotlib.pyplot as plt
from src.multitaper_spectrogram_python import multitaper_spectrogram
from src2.ephys.channel import  Channel
import logging


class Visualizer:
    """Class for visualizing ephys data."""
    def __init__(self, level='CRITICAL'):
        """Initialize the Visualizer with a logging level.
        
        Args:
            level: Logging level string (e.g., 'DEBUG', 'INFO', 'CRITICAL').
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)


    def plot_channel(self, channel:Channel, use_filtered=False):
        """Visualize the processed channel."""
        self.logger.info(f"Plotting channel...")

        signal = channel.signal_filtered if use_filtered else channel.signal
        self.logger.debug(f"signal to be plotted: {signal}")
        plt.figure()
        plt.plot(channel.time_vector, signal)
        plt.title(channel.name)
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (µV)')
        plt.show()
    

    def plot_spectrogram_helper(self, psd_matrix_db, time_points, freq_points, events):
        """Create a spectrogram plot with optional event markers.
        
        Args:
            psd_matrix_db: 2D array of PSD values in decibels.
            time_points: 1D array of time values in seconds.
            freq_points: 1D array of frequency values in Hz.
            events: Optional event data to overlay on the plot.
            
        Returns:
            Tuple of (figure, axes) matplotlib objects.
        """
        self.logger.info(f"Plotting spectrogram...")
        
        fig, ax = plt.subplots()
        mesh = ax.pcolormesh(time_points / 60, freq_points, psd_matrix_db,
                            shading='gouraud', cmap='inferno')
        plt.colorbar(mesh, ax=ax, label='Power (dB)')
        ax.set_xlabel('Time (min)')
        ax.set_ylabel('Frequency (Hz)')
        
        if events:
            self._mark_events(ax, events)
            
        plt.show()
        return fig, ax
    
    def plot_spectrogram(self, spectrogram, events = None):
        """Plot a Spectrogram object with optional event markers.
        
        Convenience wrapper around plot_spectrogram_helper that accepts
        a Spectrogram object instead of raw arrays.
        
        Args:
            spectrogram: Spectrogram object with PSD data.
            events: Optional event data to overlay on the plot.
        """
        self.plot_spectrogram_helper(spectrogram.psd_matrix_db, spectrogram.time_points, spectrogram.freq_points, events)
    
    def _mark_events(self, axisHandle, events):
        """Add vertical lines and labels for events on a plot.
        
        Draws dashed vertical lines at event timestamps with rotated
        text labels. Currently limited to first 10 events.
        
        Args:
            axisHandle: Matplotlib axes object to draw on.
            events: List of (label, timestamp) tuples.
            
        Note:
            TODO: Should only mark user-made events. Event structure
            may change in future versions.
        """
        self.logger.info(f"Marking events on plot...")
        yLimits = axisHandle.get_ylim()
        xLimits = axisHandle.get_xlim()
        lineLength = np.diff(yLimits)
        lineOffset = yLimits[0] + (lineLength / 2)

        events = events[:10]
        
        for label, timestamp in events:
            # Plot the event line
            axisHandle.axvline(x=timestamp, color='k', linestyle='--', alpha=0.7)
            # Add the label
            axisHandle.text(timestamp, yLimits[1], label, rotation=90, verticalalignment='bottom', fontsize=8)
        
        axisHandle.axis([xLimits[0], xLimits[1], yLimits[0], yLimits[1]])