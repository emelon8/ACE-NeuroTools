# -*- coding: utf-8 -*-
"""
Created on Wed Jul 12 16:29:57 2023

@author: Eric
"""

import os
import miniscope
import numpy as np

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

square=False
lineNum = 35

obj = miniscope.UCLAMiniscope(lineNum=lineNum, jobID=jobID)

# %% Crop and re-save all of the calcium imaging movies in the recording
numMovies = int(np.ceil(len(obj.timeStamps)/1000)) # The total number of calcium movie files

for i in range(numMovies):
    obj.importCaMovies(os.path.join(obj.experiment['calcium imaging directory'], 'Miniscope', str(i) + '.avi'))
    obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False, square=square)