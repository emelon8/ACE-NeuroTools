#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import numpy as np

class Channel:
    """Represents a single electrophysiology recording channel.
    
    Stores signal data, timing information, and associated events for one
    channel of an ephys recording.
    
    Attributes:
        name: Channel identifier (e.g., "PFCLFPvsCBEEG").
        signal: Raw signal data as numpy array.
        sampling_rate: Sampling frequency in Hz.
        time_vector: Timestamps corresponding to each sample.
        events: Dict containing event labels and timestamps.
        signal_filtered: Filtered signal data (set after filtering).
        phases: Instantaneous phase values (set after phase computation).
    """
    
    def __init__(self, name: str, signal: np.array, sampling_rate: float, time_vector: np.array, events):
        """Initialize a Channel with signal data and metadata.
        
        Args:
            name: Channel identifier string.
            signal: 1D numpy array of signal values.
            sampling_rate: Sampling frequency in Hz.
            time_vector: 1D numpy array of timestamps (same length as signal).
            events: Dict with 'labels' and 'timestamps' arrays for event markers.
        """
        self.name = name # for example, "PFCLFPvsCBEEG"
        self.signal = signal # [0.4, 0.5, 0.6, 0.5, 0.4, 0.5]
        self.sampling_rate = sampling_rate
        self.time_vector = time_vector
        self.events = events
        self.signal_filtered = None
        self.phases = None