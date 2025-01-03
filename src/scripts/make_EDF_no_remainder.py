#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug  8 12:55:47 2023

@author: ethanwhitt
"""

import mne
import numpy as np
import ephys

obj = ephys.NeuralynxEphys(37)
obj.importEphysData()

ch_names = list(obj.ephys.keys())

#For LightGBM-1EEG model
#ch_names = ch_names[0:2]

#for LightGBM-2EEG model
ch_names = [ch_names[0],ch_names[3], ch_names[1]]

sfreq = float(obj.samplingRate[ch_names[0]])
info = mne.create_info(ch_names, sfreq, ch_types='misc', verbose=None)

chunk_length = 10  # Length of each chunk in seconds
num_samples_per_chunk = int(sfreq * chunk_length)

num_full_chunks = len(obj.ephys[ch_names[0]]) // num_samples_per_chunk
total_samples = num_full_chunks * num_samples_per_chunk

data = np.empty((0, total_samples))
for i in ch_names:
    chunk_data = obj.ephys[i][:total_samples].reshape(1, -1)
    data = np.concatenate((data, chunk_data), axis=0)

raw = mne.io.RawArray(data, info)

fname = '37_without_remainder.edf'
mne.export.export_raw(fname, raw, overwrite=True)