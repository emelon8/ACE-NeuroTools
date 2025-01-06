# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

Examines the spatial and temporal components of a calcium imaging movie.
"""

import miniscope
import caiman as cm

# obj = miniscope.UCLAMiniscope(lineNum=20)

# # %% Import videos
# obj.importCaMovies('D:/Dropbox (Partners HealthCare)/experimental_data/miniscope_data/test/R220607/2022_07_26/14_57_17/Miniscope/0.avi')

# # %% Load the estimates object
# cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF('D:/Dropbox (Partners HealthCare)/experimental_data/miniscope_data/test/R220607/2022_07_26/14_57_17/estimates.hdf5')

# obj.estimates = cnmObj.estimates

# obj._componentGUI()

obj = miniscope.UCLAMiniscope(lineNum=85)

#%% Import videos
obj.importCaMovies(obj.experiment['calcium imaging directory'] + '/Miniscope/103.avi')

#%% Load the estimates object
cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF(obj.experiment['calcium imaging directory'] + '/estimates.hdf5')

obj.estimates = cnmObj.estimates

obj._componentGUI()