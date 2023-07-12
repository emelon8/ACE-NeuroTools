# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

This script is used to process an entire miniscope recording. High RAM demands.
"""

# import glob
import miniscope

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

obj = miniscope.UCLAMiniscope(lineNum=21, jobID=jobID)

# %% Crop and re-save the videos
# for vidnum in range(92): # The number in range() should be the total number of .avi movies in the recording
#     obj.importCaMovies(['../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/' + str(vidnum) + '.avi'])
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
