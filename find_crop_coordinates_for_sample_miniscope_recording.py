# -*- coding: utf-8 -*-
"""
Created on Wed Jul 12 16:29:11 2023

@author: Eric
"""

import os
import miniscope
import numpy as np

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

lineNum = 35
movieNums = np.arange(5)

obj = miniscope.UCLAMiniscope(lineNum=lineNum, jobID=jobID)

#%% Import movies
movieFilenameAfterNum = '.avi'
movieList = []
for k in movieNums:
    movieList.append(os.path.join(obj.experiment['calcium imaging directory'], 'Miniscope', str(k) + movieFilenameAfterNum))

obj.importCaMovies(movieList)

#%% Find and save the cropping coordinates for the recording
obj.preprocessCaMovies(saveMovie=False, crop=True, cropGUI=True)