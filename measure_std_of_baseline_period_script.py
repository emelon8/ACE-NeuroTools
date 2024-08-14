# -*- coding: utf-8 -*-
"""
Created on Fri May 24 15:05:36 2024

@author: ericm
"""

import miniscope_ephys
import numpy as np
import matplotlib.pyplot as plt

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

lineNum = [35]#,36,37,38,39,40,41,42,43,44,45,46,47,48,64,83,85,86,87,88,90,92,93,94,96,97,99,101,103,104,105,107,108,112]
stdProjections = []
ax = []

for i, k in enumerate(lineNum):
    obj = miniscope_ephys.miniscopeEphys(lineNum=k, jobID=jobID)
    
    obj.importNeuralynxEvents()
    
    obj.findCaMovieNums(timeRange=[])
    
    obj.importCaMovies(filenames=obj.movieFilePaths)
    obj.computeProjections()
    stdProjections.append(obj.projections['std'])
    ax.append(plt.axes())
    ax[i].imshow(stdProjections[i], cmap='jet')