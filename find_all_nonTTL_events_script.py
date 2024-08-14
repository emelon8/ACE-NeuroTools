# -*- coding: utf-8 -*-
"""
Created on Fri May 24 16:01:29 2024

@author: ericm
"""

import miniscope_ephys
import numpy as np

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

lineNum = [35,36,37,38,39,40,41,42,43,44,45,46,47,48,64,83,85,86,87,88,90,92,93,94,96,97,99,101,103,104,105,107,108,112]
events = [0] * (max(lineNum) + 1)
startArray = [0] * (max(lineNum) + 1)
numStarts = [0] * (max(lineNum) + 1)
firstStart = [0] * (max(lineNum) + 1)
firstStartLabel = [0] * (max(lineNum) + 1)

for k in lineNum:
    obj = miniscope_ephys.miniscopeEphys(lineNum=k, jobID=jobID)
    
    obj.importNeuralynxEvents()
    
    obj.syncNeuralynxMiniscopeTimestamps()
    
    events[k] = obj.NeuralynxEvents
    
    startArray[k] = np.char.find(events[k]['labels'], 'start')
    numStarts[k] = len(events[k]['labels']) + startArray[k]
    
    firstStart[k] = np.where(startArray[k] == 0)[0]
    
    if len(firstStart[k]) > 0:
        firstStartLabel[k] = events[k]['labels'][firstStart[k][0]]