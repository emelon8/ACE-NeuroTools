# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 16:40:07 2022

@author: Eric

Create projections of an entire miniscope recording.
"""
import os
os.chdir('..')

import matplotlib.pyplot as plt
import miniscope

obj = miniscope.UCLAMiniscope(lineNum=16)

obj.importCaMovies('testing/cluster_testing/cropping_samples/cool.avi')

obj.computeProjections()

plt.imshow(obj.projections['Max'])