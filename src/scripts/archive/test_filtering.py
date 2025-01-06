# -*- coding: utf-8 -*-
"""
Created on Thu Jun  1 09:18:41 2023

@author: Eric

The purpose of this script is to test the filtering and instantaneous phase
methods in ephys.py.
"""

import ephys
from misc_functions import filterData
import matplotlib.pyplot as plt
import numpy as np

lineNum = 41
channel = 'PFCLFPvsCBEEG'

obj = ephys.NeuralynxEphys(lineNum=lineNum)

#%% Butterworth filter
obj.importEphysData(channel)

data = obj.ephys[channel].copy()

plt.figure()
plt.plot(obj.tEphys[channel],obj.ephys[channel],color='blue')

obj.filterEphys(channel=channel, n=3, ftype='butterworth')
butterdata = obj.ephys[channel].copy()

plt.plot(obj.tEphys[channel],butterdata,color='red')
plt.title('Butterworth filter (red) vs. original signal (blue)')

obj.computePhase(channel=channel)

plt.figure()
plt.plot(obj.tEphys[channel],butterdata,color='red')
plt.plot(obj.tEphys[channel],obj.instantaneousPhaseEphys[channel]*200/np.pi,color='green')
plt.title('Butterworth filter (red) vs. phase (green)')

#%% FIR filter
plt.figure()
plt.plot(obj.tEphys[channel],data,color='blue')

obj.ephys[channel] = data.copy()

obj.filterEphys(channel=channel)
firdata = obj.ephys[channel].copy()

plt.plot(obj.tEphys[channel],firdata,color='red')
plt.title('FIR filter (red) vs. original signal (blue)')

obj.computePhase(channel=channel)

plt.figure()
plt.plot(obj.tEphys[channel],firdata,color='red')
plt.plot(obj.tEphys[channel],obj.instantaneousPhaseEphys[channel]*200/np.pi,color='green')
plt.title('FIR filter (red) vs. phase (green)')

#%% Make Bode plots of the filters
filterData(data,3,[0.5,4],'Butterworth','bandpass',2000,bodePlot=True)
filterData(data,10000,[0.5,4],'fir','bandpass',2000,bodePlot=True)

#%% Compare the standard deviations of the difference between the filtered signals and the original signal (not sure if this is a good measure of the filter or not!)
print('Standard deviation of the difference between Butterworth and original signal: ' + str(np.std(data-butterdata)))
print('Standard deviation of the difference between FIR and original signal: ' + str(np.std(data-firdata)))