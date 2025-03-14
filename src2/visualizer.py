#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import numpy as np
import matplotlib.pyplot as plt
from src.multitaper_spectrogram_python import multitaper_spectrogram
from src2.channel import  Channel
import logging


class Visualizer:
    """Class for visualizing ephys data."""
    def __init__(self, channel:Channel, level='CRITICAL'):
        self.channel = channel
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(level)


    def plot_channel(self, use_filtered=False):
        """Visualize the processed channel."""
        self.logger.info(f"Plotting channel...")

        signal = self.channel.signal_filtered if use_filtered else self.channel.signal
        self.logger.debug(f"signal to be plotted: {signal}")
        plt.figure()
        plt.plot(self.channel.time_vector, signal)
        plt.title(self.channel.name)
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (µV)')
        plt.show()
    

    def plot_spectrogram(self, window_length=30, window_step=3,
                           freq_limits=[0, 50], time_bandwidth=2, plot_events=False, use_filtered=False):
        
        signal = self.channel.signal_filtered if use_filtered else self.channel.signal
        
        fs = int(self.channel.sampling_rate)

        # Spectrogram parameters
        num_tapers = time_bandwidth * 2 - 1  
        window_params = [window_length, window_step]  # [window length (s), step size (s)]

        power_spectrum, time_points, freq_points = multitaper_spectrogram(
            signal, fs, freq_limits, time_bandwidth, num_tapers, window_params
        )
        
        # Convert to decibel scale (dB re 1 µV²/Hz)
        power_db = 10 * np.log10(power_spectrum)



        # Plot spectrogram
        
        fig, ax = plt.subplots()
        mesh = ax.pcolormesh(time_points / 60, freq_points, power_db,
                            shading='gouraud', cmap='inferno')
        plt.colorbar(mesh, ax=ax, label='Power (dB)')
        ax.set_xlabel('Time (min)')
        ax.set_ylabel('Frequency (Hz)')
        
        if plot_events and hasattr(self.data_manager, 'events'):
            self._mark_events_on_spectrogram(ax)
            
        plt.show()
        return fig, ax
    
    