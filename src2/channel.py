#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""

class Channel:
    def __init__(self, name, signal, sampling_rate, time_vector):
        self.name = name
        self.signal = signal
        self.sampling_rate = sampling_rate
        self.time_vector = time_vector
        self.signal_filtered = None
        