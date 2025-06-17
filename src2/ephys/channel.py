#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import numpy as np

class Channel:
    def __init__(self, name: str, signal: np.array, sampling_rate: float, time_vector: np.array, events):
        self.name = name # for example, "PFCLFPvsCBEEG"
        self.signal = signal # [0.4, 0.5, 0.6, 0.5, 0.4, 0.5]
        self.sampling_rate = sampling_rate
        self.time_vector = time_vector
        self.events = events
        self.signal_filtered = None
        self.phases = None