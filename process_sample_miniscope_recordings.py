# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

"""

import os
os.chdir('..')
# import glob
import miniscope
import numpy as np

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

obj = miniscope.UCLAMiniscope(lineNum=21, jobID=jobID)

# %% Import movies
moviePath = '../../experimental_data/miniscope_data/test/R220607/2022_08_10/10_55_07/Miniscope/'
movieFilenameAfterNum = '_cropped.avi'
movieNums = np.arange(5)
movieList = []
for k in movieNums:
    movieList.append(os.path.join(moviePath, str(k) + movieFilenameAfterNum))

obj.importCaMovies(movieList)

# %% Crop and re-save the videos
# obj.preprocessCaMovies(saveMovie=False, crop=True, cropGUI=True)

# for k in movieList:
#     obj.importCaMovies(k)
#     obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False)

# %% Run motion correction and CNMF-E and save the estimates object
obj.processCaMovies(parallel=False, n_processes=8)

print('obj.movieFilePaths = ' + str(obj.movieFilePaths))

# %% Delete memmapped files
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
