# -*- coding: utf-8 -*-
"""
Created on Tue Jul 25 17:27:39 2023

@author: Eric
"""

from scipy.signal import correlate
import miniscope_ephys
import matplotlib.pyplot as plt
import numpy as np
import misc_functions

obj = miniscope_ephys.miniscopeEphys(37)

obj.importEphysData()
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps()
obj.findEphysIdxOfTTLEvents(CaEvents=False)

meanFluorescence_37 = np.load('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/sleep/R221020A/2022_11_29/14_23_10/Miniscope/meanFluorescence_37.npz')

fdataM = misc_functions.filterData(meanFluorescence_37['meanFluorescence'], n=2, cut=[2,4], ftype='butter', btype='bandpass', fs=obj.experiment['frameRate'])

obj.filterEphys(n=2,cut=[2,4],ftype='butter',inline=False)

xcorr = correlate(fdataM[116300:125900], obj.fdata[0].data[obj.ephysIdxAllTTLEvents][116300:125900])