# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 16:40:07 2022

@author: Eric

Create projections of an entire miniscope recording.
"""

# import matplotlib.pyplot as plt
import miniscope
import numpy as np

lineNum = [35, 37, 38]

for k in lineNum:
    obj = miniscope.UCLAMiniscope(lineNum=k)
    
    obj.importCaMovies()
    
    print('obj.movieFilePaths = ' + str(obj.movieFilePaths))
    
    obj.computeProjections()
    
    maxpro = np.array(obj.projections['Max'])
    minpro = np.array(obj.projections['Min'])
    meanpro = np.array(obj.projections['Mean'])
    medpro = np.array(obj.projections['Med'])
    stdpro = np.array(obj.projections['Std'])
    rangepro = np.array(obj.projections['Range'])
    
    np.save('max_' + str(k) + '.npy', maxpro)
    np.save('min_' + str(k) + '.npy', minpro)
    np.save('mean_' + str(k) + '.npy', meanpro)
    np.save('med_' + str(k) + '.npy', medpro)
    np.save('std_' + str(k) + '.npy', stdpro)
    np.save('range_' + str(k) + '.npy', rangepro)
    
#     plt.imshow(obj.projections['Max'])
