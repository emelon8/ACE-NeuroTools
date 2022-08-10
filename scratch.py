# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric
"""

# import miniscope_EEG
# import EEG
import miniscope

# %% Import experiment and electrophysiological data
# program = miniscope_EEG.miniscopeEEG(2, filename='experiments.csv', filenameMiniscope='test_recordings/example_miniscope_recording/settings_and_notes.dat')
# program = EEG.NeuralynxEEG(11)
# program.importEphysData()

program = miniscope.miniscope(lineNum=16)
# program.importCaMovies('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0_4_cropped.avi')
program.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/50_50_cropped.avi'])#,'D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/1.avi'])
# program.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/memmap__d1_390_d2_388_d3_1_order_C_frames_1000_.mmap'])
# program.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/50_cropped_mc.avi'])
# program.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/90.avi'])
# program.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_26/14_34_38/Miniscope/0_0_cropped.avi'])

# %% Analyze calcium movie
# program.preprocessCaMovies(saveMovie=True, crop=True)
program.processCaMovies(parallel=False, motionCorrect=False, saveMotionCorrect=True, runCNMFE=True, editComponents=False)#saveCNMFEFilename='50_estimates')


# # These lines are only useful for the practice dataset since the modified times are when they were downloaded.
# program.findMovieFilePaths()
# import numpy as np
# cutFile = []
# for file in program.movieFilePaths:
#     cutFile.append(int(file[114:-4]))
# sortIdx = np.argsort(np.array(cutFile))
# program.movieFilePaths = list(np.array(program.movieFilePaths)[sortIdx])

# program.processCaMovies(visualizeMotionCorrection=True, inspectCorrPNR=True)

# %% Plot spectrogram
# program.computeSpectrogram(plotSpectrogram=True, plotEvents=False)