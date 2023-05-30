# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

Examines the spatial and temporal components of a calcium imaging movie.
"""

import os
os.chdir('..')

import miniscope
import caiman as cm

obj = miniscope.UCLAMiniscope(lineNum=16)

# %% Import videos
obj.importCaMovies('cluster_testing/multiple_movies/same_analysis_twice/Yr_d1_390_d2_388_d3_1_order_C_frames_3000_.mmap')

# %% Load the estimates object
cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF('cluster_testing/multiple_movies/same_analysis_twice/%J_estimates.hdf5')

obj.estimates = cnmObj.estimates

obj._componentGUI()
