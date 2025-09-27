#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 01:32:41 2025

@author: lukerichards
"""

from src.classes import experiment
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
import logging

# Configure logging.   Change "CRITIAL" to "INFO" to see most useful things
logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s")

class EphysDataManager:
    
    
    def __init__(self):
        self.ephys_data = None
        self.sampling_rate = {}
        self.t_ephys = {}
        self.ephys = {}
        self.zero_time = {}

    def import_ephys_data(self, channels='all', remove_artifacts=False, 
                          v_threshold=1500, t_threshold=60, plot=False, hann_num=75):


        print('Importing ephys data...')
        start_time = time.time()

        # Find ephys file path
        ephys_file_path = misc_functions._find_file_paths(
            self.experiment['ephys directory'], 
            file_extensions='.nev', 
            file_starts_with='Events', 
            remove_file=True
        )[0]

        # Initialize NeuralynxIO and read block
        nev_file_reader = NeuralynxIO(dirname=ephys_file_path)
        self._ephys_data = nev_file_reader.read_block(signal_group_mode='split-all')

        # Initialize sampling rate and time arrays
        self._initialize_sampling_rate_and_time_arrays()

        # Process channels
        self._process_channels(channels, remove_artifacts, v_threshold, t_threshold, plot, hann_num)

        print('--- %s seconds ---' % (time.time() - start_time))

    def _initialize_sampling_rate_and_time_arrays(self):
        """
        Initialize sampling rate and time arrays.
        """
        self.sampling_rate = {}
        self.t_ophys = {}
        self.ephys = {}
        self.zero_time = {}

    def _process_channels(self, channels, remove_artifacts, v_threshold, t_threshold, plot, hann_num):
        """
        Process channels.

        Args:
            channels (str or list of str): 'all', 'none', or a string or list of strings.
            remove_artifacts (bool): Whether to remove artifacts.
            v_threshold (float): Voltage threshold for artifact removal.
            t_threshold (float): Time threshold for artifact removal.
            plot (bool): Whether to plot.
            hann_num (int): Hann window number.

        Returns:
            None
        """

        if channels == 'all':
            channels = self.experiment['LFP and EEG CSCs'].split(';')

        for k, c in enumerate(self._ephys_data.segments[0].analogsignals):
            if c.name in channels:
                self.sampling_rate[c.name] = c.sampling_rate.magnitude
                dt = 1 / self.sampling_rate[c.name]
                t_start = c.t_start.magnitude
                t_stop = self._ephys_data.segments[-1].analogsignals[k].t_stop.magnitude

                if (t_stop - t_start) % dt <= (dt / 2):
                    t_stop -= 0.51 * dt

                self.t_ophys[c.name] = np.arange(t_start, t_stop, dt)
                self._make_ephys_arrays(k)

                if remove_artifacts:
                    self.artifact_removal(channel=c.name, v_threshold=v_threshold, 
                                          t_threshold=t_threshold, plot=plot, hann_num=hann_num)

    def _make_ephys_arrays(self, k):
        """
        Make ephys arrays.

        Args:
            k (int): Index.

        Returns:
            None
        """
        # TO DO: implement _make_ephys_arrays method
        pass

    def artifact_removal(self, channel, v_threshold, t_threshold, plot, hann_num):
        """
        Remove artifacts.

        Args:
            channel (str): Channel name.
            v_threshold (float): Voltage threshold.
            t_threshold (float): Time threshold.
            plot (bool): Whether to plot.
            hann_num (int): Hann window number.

        Returns:
            None
        """
        # TO DO: implement artifact_removal method
        pass
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    def importEphysData(self,channels='all',removeArtifacts=False, 
                        VThreshold=1500,TThreshold=60,plot=False,hannNum=75):
        
        """Import Neuralynx continuously sampled channel data and associated events.
        CHANNELS can be 'all', 'none' (if you just want to import the events),
        or a string or list of strings."""
        
        
        print('Importing ephys data...')
        start_time = time.time()
        self.ephysFilePath = misc_functions._findFilePaths(self.experiment['ephys directory'], fileExtensions='.nev', fileStartsWith='Events', removeFile=True)[0]
        self._recording = NeuralynxIO(dirname=self.ephysFilePath)
        self._ephysData = self._recording.read_block(signal_group_mode='split-all')
        self.samplingRate = {}
        self.tEphys = {}
        self.ephys = {}
        self.zeroTime = {}
        if channels == 'all':
            channels = self.experiment['LFP and EEG CSCs'].split(';')
        if channels != 'none':
            for k, c in enumerate(self._ephysData.segments[0].analogsignals):
                if c.name in channels:
                    self.samplingRate[c.name] = c.sampling_rate.magnitude
                    print("Printing c.sampling_rate.magnitude", )
                    dt = 1/self.samplingRate[c.name]
                    tStart = c.t_start.magnitude
                    tStop = self._ephysData.segments[-1].analogsignals[k].t_stop.magnitude
                    # Since tStop is actually one timestep beyond the time of the last sample, 
                    # evaluate whether there needs to be another time point at the end
                    # to accommodate the timing of the last segment (and not leave the
                    # last element stranded). The '=' in the '<=' is to account for the
                    # fact that .argmin() in self._makeEphysArrays() looks for the first
                    # occurance of the minimum when there is more than one candidate.
                    if (tStop - tStart) % dt <= (dt / 2):
                        tStop -= 0.51 * dt # subtract just over half of a dt to bump it down a time point
                    self.tEphys[c.name] = np.arange(tStart, tStop, dt)
                    self._makeEphysArrays(k)
                    # For each channel, after making the ephys arrays, find the element
                    # of the time vector closest to self.experiment['zero time (s)']
                    # and subtract the time at that element from the entire time array
                    # zeroIdx = (np.abs(self.tEphys[c.name] - self._analysisParamsDict['zero time (s)'])).argmin()
                    # self.zeroTime[c.name] = self.tEphys[c.name][zeroIdx]
                    # self.tEphys[c.name] -= self.zeroTime[c.name]
                    if removeArtifacts:
                        self.artifactRemoval(channel=c.name,VThreshold=VThreshold,
                                             TThreshold=TThreshold,plot=plot,hannNum=hannNum)
        print('--- %s seconds ---' % (time.time() - start_time))
        
        
        
        
        