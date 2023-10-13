# -*- coding: utf-8 -*-
"""
Created on Mon Mar 13 10:46:31 2023

@author: Eric

The purpose of this script is to plot the difference between the Neuralynx TTL
event timestamps created when calcium movie frames are captured and the
timestamps recorded by the UCLA Miniscope software, for the purpose of finding
the indices of dropped frames.
"""

import miniscope_ephys
import numpy as np
import matplotlib.pyplot as plt
# %matplotlib qt

#%% Import experiment and electrophysiological data
lendiff = []
alternating = []
driftFit = []

for k in [96]:#48,64]: #35,36,37,38,39,40,41,42,43,44,45,46,47,
    obj = miniscope_ephys.miniscopeEphys(k)
    obj.importEphysData(channels=['PFCEEGvsCBEEG'])
    obj.importNeuralynxEvents(analogSignalImported=True)
    # obj.importCaMovies()
    alternating.append(obj.syncNeuralynxMiniscopeTimestamps(channel='PFCEEGvsCBEEG', deleteTTLs=False))
    
    lendiff.append(len(obj.tCaIm) - len(obj.timeStamps))
    
    TTL_timeStamp_diff=obj.timeStamps-obj.tCaIm[:len(obj.timeStamps)]
    zeroed_tS=TTL_timeStamp_diff-TTL_timeStamp_diff[0]
    plt.figure()
    plt.plot(zeroed_tS*1000)
    plt.xlabel('frame number')
    plt.ylabel('Miniscope software timestamps - TTL event times (ms)')
    
    plt.figure()
    plt.plot(np.diff(obj.timeStamps)*1000)
    plt.xlabel('diff frame number')
    plt.ylabel('Miniscope software timestamp diffs (ms)')
    
    plt.figure()
    plt.plot(np.diff(obj.tCaIm)*1000)
    plt.xlabel('diff frame number')
    plt.ylabel('TTL event time diff (ms)')
    
    # find the slope of the trials with no jumps
    # driftFitRaw = np.polynomial.Polynomial.fit(np.arange(len(zeroed_tS)), zeroed_tS, 1)
    # driftFit.append(driftFitRaw.convert())