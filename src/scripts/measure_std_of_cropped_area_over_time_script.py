# -*- coding: utf-8 -*-
"""
Created on Mon May 20 15:47:45 2024

This script summarizes a movie by taking the 

@author: ericm
"""

import sys
from pathlib import Path

# Add the project root to sys.path for imports to work
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from classes import miniscope
import numpy as np
import matplotlib.pyplot as plt

import sys

#%% Configurable Parameters
FIRST_N_VIDEOS = 1 # typically 5 or more.  My computer is lightweight 

#%%

jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

square = True
lineNum = [97]#,36,37,38,39,40,41,42,43,44,45,46,47,48,64,83,85,86,87,88,90,92,93,94,96,97,99,101,103,104,105,107,108,112]
squareSize = 120 # size of edge of cropped area, in pixels
cropStd = []
ax = []

for i, k in enumerate(lineNum):
    obj = miniscope.UCLAMiniscope(lineNum=k, jobID=jobID)
    obj.findMovieFilePaths()
    obj.movieFilePaths = obj.movieFilePaths[:FIRST_N_VIDEOS] # looks at the first n videos.  Each video is 1000 frames 
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
    
    # %%
    
    # Create the figure and axis for the plot
    fig, ax = plt.subplots()
    img = ax.imshow(cropStd[i], cmap='jet')  # Plot the heatmap
    
    # Add a color bar to indicate the color scale
    colorbar = plt.colorbar(img, ax=ax)
    colorbar.set_label('Median Standard Deviation Over All Frames', fontsize=10)  # Customize the label
    
    # Add title and labels
    ax.set_title(f"Crop Std for Line {k}")
    ax.set_xlabel("X (pixels)")
    ax.set_ylabel("Y (pixels)")
    
    # Show the plot
    plt.show()
    # ax.append(plt.axes(projection = '3d'))
    # x, y = np.meshgrid(np.arange(cropSize[0]), np.arange(cropSize[1]))
    # ax[i].plot_surface(x, y, cropStd[i], cmap='jet')