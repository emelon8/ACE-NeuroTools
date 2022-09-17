# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 16:40:07 2022

@author: Eric

Create projections of an entire miniscope recording.
"""
import matplotlib.pyplot as plt
import miniscope
import numpy as np

obj = miniscope.UCLAMiniscope(lineNum=16)

obj.importCaMovies()

print('obj.movieFilePaths = ' + str(obj.movieFilePaths))

obj.computeProjections()

maxpro = np.array(obj.projections['Max'])
minpro = np.array(obj.projections['Min'])
meanpro = np.array(obj.projections['Mean'])
medpro = np.array(obj.projections['Med'])
stdpro = np.array(obj.projections['Std'])
rangepro = np.array(obj.projections['Range'])

np.save('max.npy', maxpro)
np.save('min.npy', minpro)
np.save('mean.npy', meanpro)
np.save('med.npy', medpro)
np.save('std.npy', stdpro)
np.save('range.npy', rangepro)

# plt.imshow(obj.projections['Max'])
