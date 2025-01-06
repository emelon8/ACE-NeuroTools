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

square=True
lineNum = 92

obj = miniscope.UCLAMiniscope(lineNum=lineNum, filename='C:/Users/ericm/Desktop/experiments.csv', analysisFilename='C:/Users/ericm/Desktop/analysis_parameters.csv', jobID=jobID)

# %% Crop and re-save all of the calcium imaging movies in the recording
numMovies = int(np.ceil(len(obj.timeStamps)/1000)) # The total number of calcium movie files
meanFluorescence = np.array([])

for i in range(numMovies):
    obj.importCaMovies(os.path.join(obj.experiment['calcium imaging directory'], 'Miniscope', str(i) + '.avi'))
    obj.preprocessCaMovies(saveMovie=False, crop=True, cropGUI=False, square=square)
    obj.computeProjections(time=True)
    meanFluorescence = np.concatenate((meanFluorescence, obj.projections['time']))

np.savez_compressed(obj.experiment['calcium imaging directory'] + '/Miniscope/meanFluorescence_' + str(lineNum) + '.npz', meanFluorescence=meanFluorescence)