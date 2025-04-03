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
    

    def plot_spectrogram(psd_matrix_db, time_points, freq_points, plot_events=False):
        
        fig, ax = plt.subplots()
        mesh = ax.pcolormesh(time_points / 60, freq_points, psd_matrix_db,
                            shading='gouraud', cmap='inferno')
        plt.colorbar(mesh, ax=ax, label='Power (dB)')
        ax.set_xlabel('Time (min)')
        ax.set_ylabel('Frequency (Hz)')
        
        # if plot_events and hasattr(self.data_manager, 'events'):
        #     self._mark_events_on_spectrogram(ax)
            
        plt.show()
        return fig, ax
    
    def plot_spectrogram(self, spectrogram, plot_events=False):
        """Plot the spectrogram."""
        self.plot_spectrogram(spectrogram.psd_matrix_db, spectrogram.time_points, spectrogram.freq_points, plot_events=plot_events)
    