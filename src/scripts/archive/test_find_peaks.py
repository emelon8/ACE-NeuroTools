# -*- coding: utf-8 -*-
"""
Created on Tue Jun  6 10:47:07 2023

@author: Eric
"""

import miniscope
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import numpy as np

obj = miniscope.UCLAminiscope(41)
obj.importComponents('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/dexmedetomidine/R221020A/2022_12_07/15_08_13/cnm_41.103.estimates.hdf5')

peaks = find_peaks(np.diff(obj.estimates.C[0]), height=5, threshold=5)
peaks2 = find_peaks(np.diff(obj.estimates.C[0]), height=0)

plt.figure()
plt.plot(obj.estimates.C[0])

plt.figure()
plt.plot(np.arange(1/30,len(obj.estimates.C[0])/30,1/30),obj.estimates.C[0])
plt.plot(peaks[0]/30,obj.estimates.C[0][peaks[0]],'g*')

plt.figure()
plt.plot(np.arange(1/30,len(obj.estimates.C[0])/30,1/30),obj.estimates.C[0])
plt.plot(peaks2[0]/30,obj.estimates.C[0][peaks2[0]],'g*')