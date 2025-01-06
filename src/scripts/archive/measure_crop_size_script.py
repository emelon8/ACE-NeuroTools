# -*- coding: utf-8 -*-
"""
Created on Fri May 17 09:25:17 2024

@author: ericm
This script measures the size (in pixels) of the crop coordinates in analysis_parameters.csv.
"""

import miniscope
import numpy as np

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

square = True
lineNum = [35,36,37,38,39,40,41,42,43,44,45,46,47,48,64,83,85,86,87,88,90,92,93,94,96,97,99,101,103,104,105,107,108,112]

crop_coords = np.ones((max(lineNum)+1, 4)) * np.nan

for k in lineNum:
    obj = miniscope.UCLAMiniscope(lineNum=k, jobID=jobID)
    crop_coords[k] = obj._analysisParamsDict['crop_square']

xSize = np.abs(crop_coords[:,2]-crop_coords[:,0])
ySize = np.abs(crop_coords[:,3]-crop_coords[:,1])
totalPix = xSize * ySize