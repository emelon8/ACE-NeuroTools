# -*- coding: utf-8 -*-
"""
Created on Sat May 27 13:31:43 2023

@author: Eric

The purpose of this script is to check the number of segments in specified
ephys experiments. There will be more than one segment if there were dropped
samples in the recording.
"""

import ephys
import numpy as np

numSegs = []

experimentNum = np.arange(1,82) # [35,36,37,38,39,40,41,42,43,44,45,46,47,48]

for k in experimentNum:
    obj = ephys.NeuralynxEphys(k)
    try:
        obj.importEphysData(channels='PCvsPFCEEG')
        numSegs.append(len(obj._ephysData.segments))
    except AttributeError:
        numSegs.append(np.nan)
        print('There is no ephys data for experiment #' + str(k) + '!')