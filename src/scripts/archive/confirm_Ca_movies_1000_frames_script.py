# -*- coding: utf-8 -*-
"""
Created on Mon May 22 17:32:15 2023

@author: Eric

The purpose of this script is to look at the number of frames in each movie file of a given experiment.
I used it to confirm that each of the video files, including those written to during dropped frames, have exactly 1000 frames.
"""

import miniscope
import numpy as np

numFramesPerFile = 1000

obj = miniscope.UCLAMiniscope(64)

obj.findMovieFilePaths()

h = []

for k in obj.movieFilePaths:
    obj.importCaMovies(k)
    h.append(len(obj.movie))

print(len(h))
print(np.where(np.array(h)!=numFramesPerFile)[0])