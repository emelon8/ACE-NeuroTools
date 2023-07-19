# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

Run calcium imaging analysis on a select range of miniscope recordings.
"""

import os
# import glob
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

#%% Crop and re-save the videos
# obj.preprocessCaMovies(saveMovie=False, crop=True, cropGUI=True)

# for k in movieList:
#     obj.importCaMovies(k)
#     obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False)

#%% Run motion correction and CNMF-E and save the estimates object
obj.processCaMovies(parallel=False, n_processes=8)

print('obj.movieFilePaths = ' + str(obj.movieFilePaths))

#%% Delete memmapped files
# # Get a list of all the file paths that ends with .txt from in specified directory
# if type(obj.movieFilePaths) is str:
#     fileList = glob.glob(os.path.split(obj.movieFilePaths)[0] + '/*.mmap')
# else:
#     fileList = glob.glob(os.path.split(obj.movieFilePaths[0])[0] + '/*.mmap')
# # Iterate over the list of filepaths & remove each file.
# for filePath in fileList:
#     try:
#         os.remove(filePath)
#     except:
#         print("Error while deleting file : ", filePath)
