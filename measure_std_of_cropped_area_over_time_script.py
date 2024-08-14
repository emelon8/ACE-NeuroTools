# -*- coding: utf-8 -*-
"""
Created on Mon May 20 15:47:45 2024

@author: ericm
"""

import miniscope
import numpy as np
import matplotlib.pyplot as plt

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

square = True
lineNum = [35]#,36,37,38,39,40,41,42,43,44,45,46,47,48,64,83,85,86,87,88,90,92,93,94,96,97,99,101,103,104,105,107,108,112]
squareSize = 120 # size of edge of cropped area, in pixels
cropStd = []
ax = []

for i, k in enumerate(lineNum):
    obj = miniscope.UCLAMiniscope(lineNum=k, jobID=jobID)
    obj.findMovieFilePaths()
    obj.movieFilePaths = obj.movieFilePaths[:5]
    obj.importCaMovies(filenames=obj.movieFilePaths)
    obj.computeProjections()
    cropSize = np.array(obj.movie.shape[1:]) - squareSize
    cropStdTemp = np.ones((cropSize)) * np.nan
    for n in range(cropSize[0]):
        for m in range(cropSize[1]):
            cropStdTemp[n,m] = np.median(obj.projections['std'][n:n+squareSize,m:m+squareSize])
        print(n)
    cropStd.append(cropStdTemp)
    ax.append(plt.axes())
    ax[i].imshow(cropStd[i], cmap='jet')
    # ax.append(plt.axes(projection = '3d'))
    # x, y = np.meshgrid(np.arange(cropSize[0]), np.arange(cropSize[1]))
    # ax[i].plot_surface(x, y, cropStd[i], cmap='jet')