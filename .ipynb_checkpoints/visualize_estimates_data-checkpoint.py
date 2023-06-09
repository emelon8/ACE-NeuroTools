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

obj = miniscope.UCLAMiniscope(lineNum=41)

# %% Import videos
obj.importCaMovies('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/dexmedetomidine/R221020A/2022_12_07/15_08_13/Miniscope/103.avi')

# %% Load the estimates object
cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/dexmedetomidine/R221020A/2022_12_07/15_08_13/cnm_41.103.estimates.hdf5')

obj.estimates = cnmObj.estimates

# obj._componentGUI()