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
program.importCaMovies('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0_4_cropped.avi')

# %% Analyze calcium movie
# program.preprocessCaMovies(crop=True)
program.processCaMovies(inspectMotionCorrection=True, runCNMFE=False)


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