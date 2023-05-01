# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

"""

# import os
# import glob

import miniscope_ephys
# import ephys
# import miniscope
import numpy as np

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1] + '_'

# %% Import experiment and electrophysiological data
obj = miniscope_ephys.miniscopeEphys(53)
# obj = ephys.NeuralynxEphys(48)
obj.importEphysData(channels=['PFCEEGvsCBEEG'])
# obj.filterEphys(channel='PFCLFPvsCBEEG')#, ftype='FIR')
obj.importNeuralynxEvents(analogSignalImported=True)

# x=np.concatenate((obj.NeuralynxEvents['timestamps'][2:37122],obj.NeuralynxEvents['timestamps'][37123:58556],obj.NeuralynxEvents['timestamps'][58557:120449],obj.NeuralynxEvents['timestamps'][120450:239543],obj.NeuralynxEvents['timestamps'][239544:-5],obj.NeuralynxEvents['timestamps'][-4:-1]))

# obj = miniscope.UCLAMiniscope(lineNum=48, jobID=jobID)

# %% Crop and re-save the movies
# for movnum in range(5): # The number in range() should be the total number of .avi movies in the recording
#     obj.importCaMovies([obj.experiment['calcium imaging directory'] + '/Miniscope/' + str(movnum) + '.avi'])
#     obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False)

# %% Import movies
#obj.importCaMovies(['../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0_cropped.avi'])#, '../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/1_cropped.avi', '../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/2_cropped.avi'])
# obj.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/90.avi'])
# obj.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/memmap__d1_390_d2_388_d3_1_order_C_frames_1000_.mmap'])

# # Import movies in a range
# movrange = []
# for movnum in range(5): # The number in range() should be the total number of .avi movies in the recording
#     movrange.append(obj.experiment['calcium imaging directory'] + '/Miniscope/' + str(movnum) + '.avi')
# obj.importCaMovies(movrange)

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
