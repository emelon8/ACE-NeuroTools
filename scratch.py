# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric
"""

# import miniscope_EEG
# import EEG
import miniscope
import os
os.chdir('/PHShome/em609/data_analysis_code/experiment_analysis') # uncomment for running on ERISTwo

# %% Import experiment and electrophysiological data
# obj = miniscope_EEG.miniscopeEEG(2, filename='experiments.csv', filenameMiniscope='test_recordings/example_miniscope_recording/settings_and_notes.dat')
# obj = EEG.NeuralynxEEG(11)
# obj.importEphysData()

obj = miniscope.miniscope(lineNum=16)

for vidnum in range(91):
    # obj.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/memmap__d1_390_d2_388_d3_1_order_C_frames_1000_.mmap'])
    obj.importCaMovies(['../../experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/' + str(vidnum) + '.avi'])
    # obj.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/90.avi'])

    # %% Analyze calcium movie
    obj.preprocessCaMovies(saveMovie=True, crop=True, cropGUI=False)
    # obj.processCaMovies(parallel=False, n_processes=12, motionCorrect=False, saveMotionCorrect=True, runCNMFE=True, editComponents=False)#saveCNMFEFilename='_estimates')


# # These lines are only useful for the practice dataset since the modified times are when they were downloaded.
# obj.findMovieFilePaths()
# import numpy as np
# cutFile = []
# for file in obj.movieFilePaths:
#     cutFile.append(int(file[114:-4]))
# sortIdx = np.argsort(np.array(cutFile))
# obj.movieFilePaths = list(np.array(obj.movieFilePaths)[sortIdx])

# obj.processCaMovies(visualizeMotionCorrection=True, inspectCorrPNR=True)

# %% Plot spectrogram
# obj.computeSpectrogram(plotSpectrogram=True, plotEvents=False)
