#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import csv
import json
import caiman as cm
import numpy as np
import matplotlib.pyplot as plt
from neo.io import NeuralynxIO
from src2 import misc_functions
from src2.path_finder import PathFinder
import os
from src2.data_manager import DataManager
from src2.block_processor import BlockProcessor
from src2.channel import Channel

class MiniscopeDataManager(DataManager):
    """Manages raw Miniscope data import and storage. Processes data via Processor."""
    
    def __init__(self, line_num, auto_import_data=True):
        super().__init__(line_num)
        self.metadata, self.time_stamps, self.frame_numbers = None, None, None

        if (auto_import_data):
            self.metadata.update(self.import_miniscope_metadata()) # add miniscope metadata to overall metadata
            self.time_stamps, self.frame_numbers = self.import_timestamps()  # import timestamps and frame numbers
            self.movie = self.import_movies()  # import calcium imaging data
            



    def import_miniscope_metadata(self):
        # Assume self.metadata_path contains the path to your JSON file
        metadata_path = self._find_metadata_path()
        print(f"Reading metadata from {metadata_path}...")
        metadata = {}
        try:
            with open(metadata_path, 'r') as file:
                data = json.load(file)
        except (IOError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Error reading or parsing metadata file '{metadata_path}': {e}")

        # add ephys metadata to metadata dictionary, and convert frameRate to float
        for key, value in data.items(): 
            if key == 'frameRate':
                try:
                    metadata[key] = float(value)
                except ValueError:
                    # Attempt to remove 'FPS' and convert again
                    try:
                        cleaned_value = value.replace('FPS', '').strip()
                        metadata[key] = float(cleaned_value)
                    except ValueError:
                        raise ValueError(f"Unable to convert frameRate value '{value}' to float.")
            else:
                metadata[key] = value

        return metadata


    def import_timestamps(self):
         #print('Reading miniscope software timestamps from ' + os.path.abspath(timeStampsFilename) + '...')
        file_path = self._find_timestamps_path()
        time_stamps = []
        frame_numbers = []
        with open(file_path, newline='') as t:
            next(t)
            reader = csv.reader(t)
            for row in reader:
                frame_numbers.append(int(row[0]))
                time_stamps.append(float(row[1]))
        time_stamps = np.divide(np.asarray(time_stamps), 1000)  # convert from ms to s
        return time_stamps, frame_numbers


    def import_movies(self, filenames=None, fileExtensions='.avi'):
        """Import calcium imaging data. Not necessary if using processCaMovies().
        FILENAMES can be a single movie file or a list of movie files (in the order that you want them). If FILENAMES doesn't point to a file (either absolute or relative path from the PWD), it will append the path to the calcium imaging directory to the front of the filename."""
        if filenames == None:
            filenames = self._find_movie_file_paths()
        if type(filenames) is list:
            movie = cm.load_movie_chain(filenames)
        else:
            movie = cm.load(filenames)

        return movie


    def save_movie():
        pass

    def convert_movie_type():
        pass












    def _find_metadata_path(self):        
        path_finder = PathFinder()
        events_path = path_finder.find( 
                        directory=self.metadata['calcium imaging directory'],
                        suffix=".json",
                        prefix="metaData"
            )
        return events_path
    
    def _find_timestamps_path(self):
        path_finder = PathFinder()
        timestamps_path = path_finder.find( 
                        directory=self.metadata['calcium imaging directory'],
                        suffix=".csv",
                        prefix="timeStamps"
            )
        return timestamps_path

    def _find_movie_file_paths(self):
        path_finder = PathFinder()
        movie_file_paths = path_finder.find(
            directory=self.metadata['calcium imaging directory'],
            suffix=".avi",
            prefix=''
        )
        return movie_file_paths


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
        
        
        
        