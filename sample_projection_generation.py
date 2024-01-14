# -*- coding: utf-8 -*-
"""
Created on Fri Sep 16 16:40:07 2022

@author: Eric

Create projections of an entire miniscope recording.
"""
import os

import matplotlib.pyplot as plt
import miniscope
import numpy as np

obj = miniscope.UCLAMiniscope(lineNum=88)

#%% Import movies
moviePath = obj.experiment['calcium imaging directory'] + '/Miniscope'
movieFilenameAfterNum = '.avi' # '_cropped.avi'
movieNums = np.arange(5)
movieList = []
for k in movieNums:
    movieList.append(os.path.join(moviePath, str(k) + movieFilenameAfterNum))

obj.importCaMovies(movieList) # This doesn't play well with online-only Dropbox files, so make sure they are available offline before running this code.

print('obj.movieFilePaths = ' + str(obj.movieFilePaths))


#%% Create projections
obj.computeProjections()

fMax = plt.figure();plt.imshow(obj.projections['max'], cmap='gray')
fMin = plt.figure();plt.imshow(obj.projections['min'], cmap='gray')
fMean = plt.figure();plt.imshow(obj.projections['mean'], cmap='gray')
fMed = plt.figure();plt.imshow(obj.projections['median'], cmap='gray')
fStd = plt.figure();plt.imshow(obj.projections['std'], cmap='gray')
fRange = plt.figure();plt.imshow(obj.projections['range'], cmap='gray')

#%% Save figures
# fMax.savefig(moviePath + '/max_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
# fMin.savefig(moviePath + '/min_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
# fMean.savefig(moviePath + '/mean_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
# fMed.savefig(moviePath + '/median_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
# fStd.savefig(moviePath + '/std_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
# fRange.savefig(moviePath + '/range_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')

# plt.close('all')

#%% Save arrays of the projections
# maxpro = np.array(obj.projections['max'])
# minpro = np.array(obj.projections['min'])
# meanpro = np.array(obj.projections['mean'])
# medianpro = np.array(obj.projections['median'])
# stdpro = np.array(obj.projections['std'])
# rangepro = np.array(obj.projections['range'])

# np.save(moviePath + '/max_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', maxpro)
# np.save(moviePath + '/min_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', minpro)
# np.save(moviePath + '/mean_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', meanpro)
# np.save(moviePath + '/median_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', medianpro)
# np.save(moviePath + '/std_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', stdpro)
# np.save(moviePath + '/range_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', rangepro)