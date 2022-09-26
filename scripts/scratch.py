# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

"""

import os
os.chdir('..')
# import glob

# import miniscope_EEG
# import EEG
import miniscope

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

# %% Import experiment and electrophysiological data
# obj = miniscope_EEG.miniscopeEEG(2, filename='experiments.csv', filenameMiniscope='test_recordings/example_miniscope_recording/settings_and_notes.dat')
# obj = EEG.NeuralynxEEG(11)
# obj.importEphysData()

obj = miniscope.UCLAMiniscope(lineNum=16, jobID=jobID)

# %% Crop and re-save the videos
# for vidnum in range(92): # The number in range() should be the total number of .avi movies in the recording
#     obj.importCaMovies(['../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/' + str(vidnum) + '.avi'])
#     obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False)

# %% Import videos
#obj.importCaMovies(['../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0_cropped.avi'])#, '../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/1_cropped.avi', '../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/2_cropped.avi'])
# obj.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/90.avi'])
# obj.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/memmap__d1_390_d2_388_d3_1_order_C_frames_1000_.mmap'])

# %% Run motion correction and CNMF-E and save the estimates object
#obj.processCaMovies(parallel=False, n_processes=8)

# %% Plot spectrogram
# obj.computeSpectrogram(plotSpectrogram=True, plotEvents=False)
#print('obj.movieFilePaths = ' + str(obj.movieFilePaths))

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
