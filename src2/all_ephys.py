#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import json
import numpy as np
from scipy.signal import hilbert
from scipy.signal.windows import hann
import matplotlib.pyplot as plt
from src.multitaper_spectrogram_python import multitaper_spectrogram
from neo.io import NeuralynxIO
from src import misc_functions
import math
import time
import csv
from datetime import datetime
from src.classes import experiment
from src2.paths import ANALYSIS_PARAMS, EXPERIMENTS
import pickle
import pandas as pd
import ast
from pathlib import Path
from pathlib import Path
from typing import Union, List, Tuple, Optional
from src2.path_finder import PathFinder
import os


import json
import ast
from datetime import datetime

class DataManager:
    def __init__(self, line_num, auto_import_metadata=True, auto_import_analysis_params=True):
        self.line_num = line_num
        self.metadata = None
        self.analysis_params = None

        if auto_import_metadata:
            self.import_metadata()

        if auto_import_analysis_params:
            self.import_analysis_parameters()

    def import_metadata(self):
        metadata_unconverted = self._csv_row_to_dict(EXPERIMENTS, self.line_num)
        metadata_converted = self._convert_data_types(metadata_unconverted)
        self.metadata = metadata_converted

    def import_analysis_parameters(self):
        # print(f"Looking for analysis params at: {Path(ANALYSIS_PARAMS).resolve()}")
        # print(f"File exists: {Path(ANALYSIS_PARAMS).exists()}")
        analysis_params_unconverted = self._csv_row_to_dict(ANALYSIS_PARAMS, self.line_num)
        analysis_params_converted = self._convert_data_types(analysis_params_unconverted)
        self.analysis_params = analysis_params_converted

    def save_obj(self, filename=None, *, include_job_id=False, include_subject_id=False, include_timestamp=False):
        if filename is None:
            components = []
            if include_subject_id:
                components.append(str(self.experiment['id']))
            components.append(self.__class__.__name__)
            if include_timestamp:
                components.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
            filename = "_".join(components) + ".pickle"

        with open(filename, 'wb') as file:
            pickle.dump(self, file)

    def _csv_row_to_dict(self, csv_file, line_num):
        try:
            df = pd.read_csv(csv_file)
            line_num_str = str(line_num)
            row = df.loc[df['line number'] == line_num_str]
            if row.empty:
                raise ValueError(f"Line number {line_num} (as string: '{line_num_str}') not found")
            return row.squeeze().to_dict()
        except FileNotFoundError:
            print(f"File {csv_file} not found")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None


    def _convert_data_types(self, params_dict):
        non_numeric_keys = ['id', 'calcium imaging directory', 'ephys directory',
                           'method_deconvolution', 'method_init', 'border_nan', 'LFP and EEG CSCs']
        converted_params = {}
        
        for key, value in params_dict.items():
            if key in non_numeric_keys:
                converted_params[key] = value
                continue
            
            converted_value = self._convert_value(value, key)
            converted_params[key] = converted_value

        return converted_params

 
    def _convert_value(self, raw_value, key):
        """
        Converts a raw string value to its appropriate data type.
        """
        # NEW: Handle None
        if raw_value is None:
            return None

        # Check if the value is already a float
        if isinstance(raw_value, float):
            if pd.isna(raw_value): 
                return None
            else:
                return raw_value

        # Date conversion
        if key == 'date (YYMMDD)':
            return self._convert_date(raw_value)

        # Ensure raw_value is a string for further processing
        if not isinstance(raw_value, str):
            return raw_value

        # NEW: Preprocess tuple-like strings for JSON
        processed_value = raw_value.strip().replace(" ", "")
        if processed_value.startswith("(") and processed_value.endswith(")"):
            processed_value = f'[{processed_value[1:-1]}]'

        # Attempt JSON parsing
        try:
            return json.loads(processed_value)
        except (json.JSONDecodeError, AttributeError) as e:
            pass

        # Attempt Python literal evaluation
        try:
            return ast.literal_eval(processed_value)
        except (ValueError, SyntaxError) as e:
            pass

        # Check for boolean strings
        lower_val = raw_value.lower()
        if lower_val == 'true':
            return True
        elif lower_val == 'false':
            return False

        # Check for None/empty
        elif lower_val == 'none' or raw_value.strip() == '':
            return None

        # Attempt float conversion
        try:
            return float(raw_value)
        except ValueError as e:
            return raw_value
        

    def _convert_date(self, date_str):
        """
        Converts a date string in the format YYMMDD to a datetime object.
        
        Args:
            date_str: The date string or float to be converted.
        
        Returns:
            datetime: The converted datetime object, or the original value if conversion fails.
        """
        try:
            if isinstance(date_str, float):
                date_str = str(int(date_str))
            return datetime.strptime(date_str, '%y%m%d')
        except ValueError as e:
            return date_str
        
    
    
    
    
    
    
    
    


class Channel:
    def __init__(self, name, signal, sampling_rate, time_vector):
        self.name = name
        self.signal = signal
        self.sampling_rate = sampling_rate
        self.time_vector = time_vector
        self.signal_filtered = None
        
        
        
        
        
        
        
        
        
        


class EphysDataManager(DataManager):
    """Manages raw ephys data import and storage. Processes data via Processor."""
    

    def __init__(self, line_num, auto_import_ephys_block=True):
        super().__init__(line_num)
        self.channels = {}  # Processed channels
        self.ephys_block = None  # Raw data storage

        if (auto_import_ephys_block):
            self.import_ephys_block()
        

    def import_ephys_block(self):
        """Load raw Neuralynx data without processing."""
        print('Importing raw ephys data...')
        ephys_file_path = self._find_ephys_file_path()[0] # get most recently edited Events.nev file
        ephys_dir_path = os.path.dirname(ephys_file_path) # get its parent directory
        file_reader = NeuralynxIO(dirname=ephys_dir_path)
        self.ephys_block = file_reader.read_block(signal_group_mode='split-all')


    def process_ephys_block_to_channels(self, channels='all'):
        """Process raw ephys data into channels."""
        processor = BlockProcessor(self)
        self.channels = processor.process_raw_ephys(channels)


    

    def filter_ephys(self, channel_name, n=2, cut=[0.5, 4], ftype='butter', btype='bandpass'):
        """Filter the ephys data."""
        print('Filtering ' + channel_name + ' with a(n) ' + ftype + ' filter ...')
        try:
            channel = self.data_manager.channels[channel_name]
        except KeyError:
            raise ValueError("Channel not found in data_manager. Please import the data first.")
            
        filtered_data = self._filter_data(
            channel.signal,
            n=n,
            cut=cut,
            ftype=ftype,
            btype=btype,
            fs=channel.sampling_rate
        )
        
        
        channel.signal = filtered_data

        return filtered_data
        



    def _find_ephys_file_path(self):        
        path_finder = PathFinder()
        events_path = path_finder.find( 
                        directory=self.metadata['ephys directory'],
                        suffix=".nev",
                        prefix="Events"
            )
        return events_path

    def _filter_data(self, data, n, cut, ftype, btype, fs, bodePlot=False):
        from scipy.signal import butter, freqz, filtfilt, firwin, bode
        import logging

        # Set up logging
        logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s') # turn to DEBUG for more info
        
        # Log input variables
        logging.debug(f"Input variables:")
        logging.debug(f"- data: {data}")
        logging.debug(f"- n: {n}")
        logging.debug(f"- cut: {cut}")
        logging.debug(f"- ftype: {ftype}")
        logging.debug(f"- btype: {btype}")
        logging.debug(f"- fs: {fs}")
        logging.debug(f"- bodePlot: {bodePlot}")

        """ Use ftype to indicate FIR or Butterworth filter.
        
        For the FIR filter indicate a LowPass, HighPass, or BandPass with btype = lowpass, highpass, or bandpass, respectively. 
        n is the length of the filter (number of coefficients, i.e. the filter order + 1). numtaps must be odd if a passband includes the Nyquist frequency.
        A good value for n is 10000.
        Channel should be set to desired .ncs file
        
        The Butterworth filters have a more linear phase response in the pass-band than other types and is able to provide better group delay performance, and also a lower level of overshoot.
        Indicate the filter type by setting btype = 'low', 'high', or 'band'.
        The default for n is n = 2
        For a bandpass filter indicate the lowstop and the highstop by using an array. example: wn= ([10, 30])"""

        if ftype.lower() == 'fir':
            h = firwin(n, cut, pass_zero=btype, fs=fs)  # Build the FIR filter
            filteredData = filtfilt(h, 1, data)  # Zero-phase filter the data
            if bodePlot:
                w, a = freqz(h, worN=10000,fs=2000)
                plt.figure()
                plt.semilogx(w, abs(a))
                
                w, mag, phase = bode((h,1),w=2*np.pi*w)
                plt.figure()
                plt.semilogx(w,mag)
                plt.figure()
                plt.semilogx(w,phase)

        if ftype.lower() == 'butterworth' or ftype.lower() == 'butter':
            print(f"fs: {type(fs)}")
            b, a = butter(n, cut, btype=btype, fs=fs)
            filteredData = filtfilt(b, a, data)
            
            if bodePlot:
                w, h = freqz(b, a, worN=10000,fs=2000)
                plt.figure()
                plt.semilogx(w, abs(h))
                
                w, mag, phase = bode((b,a),w=2*np.pi*w)
                plt.figure()
                plt.semilogx(w,mag)
                plt.figure()
                plt.semilogx(w,phase)

        return filteredData
        
        
        
        
        
        

class BlockProcessor:
    """Processes an Ephys Block into channels."""
    
    def __init__(self, data_manager: EphysDataManager):
        self.data_manager = data_manager
        
    def process_raw_ephys(self, channels='all', remove_artifacts=False):
        """Convert raw ephys data into processed Channel objects."""
        if not self.data_manager.ephys_block:
            raise ValueError("Load raw data first using EphysDataManager.import_ephys_data()")
        
        print('Processing raw ephys data into channels...')
        if channels == 'all':
            channels = self.data_manager.metadata['LFP and EEG CSCs'].split(';')
        
        channels_dict = {}

        for channel_name in channels:

            new_channel = self._process_single_channel(channel_name)

            if remove_artifacts:
                self.remove_artifacts(new_channel)

            channels_dict[channel_name] = new_channel

        return channels_dict
            

            
            
            
    

    def _remove_artifacts(self, channel: Channel, volt_threshold=1500, time_threshold=60, hannNum=75):
        """Remove artifacts from the specified channel."""
        print('Removing artifacts from ' + channel.name + '...')
        dt = channel.time_vector[1] - channel.time_vector[0]
        mean = np.mean(channel.signal)
        channel.signal = channel.signal - mean
        
        mask = np.abs(channel.signal) > volt_threshold
        mask = self._fill_gaps(mask, dt, time_threshold)
        han_window = self._create_hann_window(hannNum)
        
        self._apply_hann_window(channel, mask, han_window, dt)
        
            
            
            
    def _process_single_channel(self, channel_name):
        """Process a single channel from raw data."""
        # Get the first and last segments
        first_segment = self.data_manager.ephys_block.segments[0].analogsignals
        last_segment = self.data_manager.ephys_block.segments[-1].analogsignals

        # Find the channel in the first segment by name
        try:
            # Get the channel and its index in the first segment
            channel_index, channel = next(
                (i, c) for i, c in enumerate(first_segment) 
                if c.name == channel_name
            )
        except StopIteration:
            raise ValueError(f"Channel '{channel_name}' not found in the first segment.")

        # Find the corresponding channel in the last segment by name
        try:
            last_channel = next(c for c in last_segment if c.name == channel_name)
        except StopIteration:
            raise ValueError(f"Channel '{channel_name}' not found in the last segment.")

        # Extract timing details
        sampling_rate = channel.sampling_rate.magnitude.item()
        dt = 1 / sampling_rate
        t_start = channel.t_start.magnitude
        t_stop = last_channel.t_stop.magnitude  # Use last_segment's channel

        # Generate time vector
        if (t_stop - t_start) % dt <= dt / 2:
            t_stop -= 0.51 * dt
        time_vector = np.arange(t_start, t_stop, dt)

        # Build signal array using the index from the first segment
        signal = self._make_ephys_array(channel_index, channel_name, time_vector)

        # Return processed channel
        return Channel(channel_name, signal, sampling_rate, time_vector)
        
    def _make_ephys_array(self, channel_index, channel_name, time_vector):
        """Construct continuous signal from raw segments."""
        n_points = len(time_vector)
        signal = np.full(n_points, np.nan)
        
        for seg in self.data_manager.ephys_block.segments:
            sig = seg.analogsignals[channel_index]
            signal_data = sig.magnitude.squeeze()  # NEW: Flatten to 1D
            
            # Calculate start/end indices
            start_idx = np.argmin(np.abs(time_vector - sig.t_start.magnitude))
            end_idx = start_idx + signal_data.size  # Use flattened data size
            
            # Avoid overfilling
            end_idx = min(end_idx, n_points)  # NEW: Prevent index overflow
            
            if start_idx > 0 and np.isnan(signal[start_idx - 1]):
                self._interpolate_missing_data(channel_name, signal, start_idx, time_vector, sig.t_start.magnitude)
            
            # Assign flattened data
            signal[start_idx:end_idx] = signal_data[:end_idx-start_idx]  # MODIFIED
        
        return signal
        
    def _interpolate_missing_data(self, channel_name, signal, start_idx, time_vector, t_start):
        """Fill gaps between segments with interpolation."""
        interp_start = np.where(np.isnan(signal))[0][0]
        interp_length = start_idx - interp_start
        x = np.linspace(signal[interp_start - 1], signal[interp_start], interp_length + 2)
        signal[interp_start:start_idx] = x[1:-1]
        

            
    def _fill_gaps(self, mask, dt, threshold):
        """Fill gaps in the mask where the time between threshold crossings is below the threshold."""
        diff = np.diff(mask.astype(int))
        starts = np.where(diff == -1)[0]
        
        for start in starts:
            end = np.where(diff[start:] == 1)[0]
            if end and (end[0] * dt) < threshold:
                mask[start:start + end[0] + 1] = True
        return mask
        
    def _create_hann_window(self, size):
        """Create a Hann window for smoothing."""
        window = hann(size)
        return np.abs(window - 1)
        
    def _apply_hann_window(self, channel, mask, window, dt):
        """Apply the Hann window to the masked regions."""
        half_len = len(window) // 2
        indices = np.where(mask)[0]
        
        for idx in indices:
            start = max(0, idx - half_len)
            end = min(len(channel.signal), idx + half_len + 1)
            segment = channel.signal[start:end]
            channel.signal[start:end] = segment * window[:len(segment)]

            
            
    def visualize_channel(self, channel):
        """Visualize the processed channel."""
        plt.figure()
        plt.plot(channel.time_vector, channel.signal)
        plt.title(channel.name)
        plt.xlabel('Time (s)')
        plt.ylabel('Voltage (µV)')
        plt.show()
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
    

class Analysis:
    """Class for analyzing ephys data."""
    
    def __init__(self, data_manager):
        self.data_manager = data_manager
        
    def compute_spectrogram(self, channel_name='PFCLFPvsCBEEG', window_length=30, window_step=3,
                           freq_limits=[0, 50], time_bandwidth=2):
        """Compute and plot the multitaper spectrogram."""
        
        print('Computing spectrogram...')
        channel = self.data_manager.channels[channel_name]
        fs = int(channel.sampling_rate)
        
        # Spectrogram parameters
        num_tapers = time_bandwidth * 2 - 1  
        window_params = [window_length, window_step]  # [window length (s), step size (s)]
        
        # Compute multitaper spectrogram
        # Returns:
        # - power_spectrum: Raw power spectral density values (µV²/Hz)
        # - time_points: Time bin centers (seconds)
        # - freq_points: Frequency bin centers (Hz)
        power_spectrum, time_points, freq_points = multitaper_spectrogram(
            channel.signal, fs, freq_limits, time_bandwidth, num_tapers, window_params
        )
        
        # Convert to decibel scale (dB re 1 µV²/Hz)
        power_db = 10 * np.log10(power_spectrum)
        
        return power_db, time_points, freq_points

    
    
    
    

class Visualizer:
    """Class for visualizing ephys data."""
    
    def plot_spectrogram(self, time_points, freq_points, power_db, plot_events=False):
        """Plot a precomputed spectrogram.
        
        Args:
            time_points: 1D array of time bin centers (seconds)
            freq_points: 1D array of frequency bin centers (Hz) 
            power_db: 2D array of power values in decibels
            plot_events: Boolean for whether to mark events
        """
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
    
    
    
    

class NeuralynxEphys:
    """Main workflow class."""
    
    def run_analysis(self, channel_name='PFCLFPvsCBEEG', window_length=30, window_step=3,
                    freq_limits=[0, 50], time_bandwidth=2, plot_spectrogram=True, plot_events=False):
        """Run spectral analysis pipeline.
        
        Returns:
            power_db: 2D array of power values in decibels (dB re 1 µV²/Hz)
            time_points: 1D array of time bin centers (seconds)
            freq_points: 1D array of frequency bin centers (Hz)
            phase: 1D array of instantaneous phase values (radians)
        """
        # Compute spectrogram
        power_db, time_points, freq_points = self.analysis.compute_spectrogram(
            channel_name,
            window_length,
            window_step,
            freq_limits,
            time_bandwidth,
            plot_spectrogram,
            plot_events
        )
        
        # Compute Hilbert transform phase
        phase = self.analysis.compute_phase(channel_name)
        
        return power_db, time_points, freq_points, phase
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    