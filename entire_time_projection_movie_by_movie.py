# -*- coding: utf-8 -*-
"""
Created on Fri Jul 21 10:21:03 2023

@author: Eric
The purpose of this script is to load all of the miniscope movies in a
recording, one by one. For each movie, it then takes the average over time (the
average brightness of the pixels in each frame) and concatenate those into a
single vector that covers the entire recording. Then it saves the vector in a
.npy file. Assumes the movie has been cropped already.
"""

import miniscope
import numpy as np

lineNum = 108

obj = miniscope.UCLAMiniscope(lineNum=lineNum)

meanFluorescence = np.array([])

obj.findMovieFilePaths(fileExtensions='_croppedSquare.avi')

h = []

for k in obj.movieFilePaths:
    obj.importCaMovies(k)
    obj.computeProjections(time=True)
    meanFluorescence = np.concatenate((meanFluorescence, obj.projections['time']))

np.savez_compressed(obj.experiment['calcium imaging directory'] + '/Miniscope/meanFluorescence_' + str(lineNum) + '.npz', meanFluorescence=meanFluorescence)