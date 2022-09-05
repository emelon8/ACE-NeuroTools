# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

For examining the spatial and temporal components of a calcium imaging movie.
"""

import miniscope
import caiman as cm

obj = miniscope.miniscope(lineNum=16)

# %% Import videos
obj.importCaMovies('cluster_testing/parallel/without_parallel/_d1_390_d2_388_d3_1_order_C_frames_1000_.mmap')

# %% Load the estimates object
cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF('cluster_testing/parallel/without_parallel/estimates.hdf5')

obj.estimates = cnmObj.estimates

obj._componentGUI()