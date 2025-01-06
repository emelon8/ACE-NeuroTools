#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jul 20 13:46:08 2023

@author: lab
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

data = np.empty((0,len(obj.ephys[ch_names[0]])))
for i in ch_names:
    data = np.concatenate((data, obj.ephys[i].reshape((1,-1))), axis=0)

raw = mne.io.RawArray(data, info)

fname = '37.edf'
mne.export.export_raw(fname, raw,overwrite=True)