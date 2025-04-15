from src2.ephys.channel import Channel
from src2.ephys.spectrogram import Spectrogram
from src2.ephys.visualizer import Visualizer
from src2.shared.multitaper_spectrogram_python import multitaper_spectrogram
import numpy as np
import matplotlib.pyplot as plt

class ChannelWorker:
    def __init__ (self, channel: Channel):
        self.channel = channel
        self.visualizer = Visualizer()
        self.spectrogram = None

    def plot_channel(self, use_filtered=False):
        self.visualizer.plot_channel(self.channel, use_filtered)


    def plot_spectrogram(self, window_length=30, window_step=3,
                           freq_limits=[0, 50], time_bandwidth=2, plot_events=False, use_filtered=False):
        
        spectrogram: Spectrogram = self.compute_spectrogram(self.channel, window_length, window_step, freq_limits, time_bandwidth, use_filtered)

        events = None if not plot_events else self.channel.events
        self.visualizer.plot_spectrogram(spectrogram, events = events)
        return self.spectrogram
    

    def compute_spectrogram(self, channel:Channel, window_length=30, window_step=3,
                           freq_limits=[0, 50], time_bandwidth=2, use_filtered=False):
        
        signal = channel.signal_filtered if use_filtered else channel.signal
        fs = int(channel.sampling_rate)

        # Spectrogram parameters
        num_tapers = time_bandwidth * 2 - 1  
        window_params = [window_length, window_step]  # [window length (s), step size (s)]

        psd_matrix, time_points, freq_points = multitaper_spectrogram( # psd_matrix = power_spectral_density_matrix
            signal, fs, freq_limits, time_bandwidth, num_tapers, window_params
        )
        
        # Convert to decibel scale (dB re 1 µV²/Hz)
        psd_matrix_db = 10 * np.log10(psd_matrix)

        # Create Spectrogram object and save it to self.spectrogram
        self.spectrogram = Spectrogram(psd_matrix_db, time_points, freq_points)
        return self.spectrogram

