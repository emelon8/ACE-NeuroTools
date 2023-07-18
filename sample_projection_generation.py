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

obj = miniscope.UCLAMiniscope(lineNum=54)

#%% Import movies
moviePath = 'D:/Dropbox (Partners HealthCare)/experimental_data/miniscope_data/sleep/R221107B/2023_02_28/14_38_18/Miniscope'
movieFilenameAfterNum = '.avi' # '_cropped.avi'
movieNums = np.arange(5)
movieList = []
for k in movieNums:
    movieList.append(os.path.join(moviePath, str(k) + movieFilenameAfterNum))

obj.importCaMovies(movieList) # This doesn't play well with online-only Dropbox files, so make sure they are available offline before running this code.

print('obj.movieFilePaths = ' + str(obj.movieFilePaths))


#%% Create projections
obj.computeProjections()

fMax = plt.figure();plt.imshow(obj.projections['Max'], cmap='gray')
fMin = plt.figure();plt.imshow(obj.projections['Min'], cmap='gray')
fMean = plt.figure();plt.imshow(obj.projections['Mean'], cmap='gray')
fMed = plt.figure();plt.imshow(obj.projections['Med'], cmap='gray')
fStd = plt.figure();plt.imshow(obj.projections['Std'], cmap='gray')
fRange = plt.figure();plt.imshow(obj.projections['Range'], cmap='gray')

#%% Save figures
fMax.savefig(moviePath + '/max_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
fMin.savefig(moviePath + '/min_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
fMean.savefig(moviePath + '/mean_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
fMed.savefig(moviePath + '/med_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
fStd.savefig(moviePath + '/std_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')
fRange.savefig(moviePath + '/range_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.png', bbox_inches='tight')

plt.close('all')

#%% Save arrays of the projections
# maxpro = np.array(obj.projections['Max'])
# minpro = np.array(obj.projections['Min'])
# meanpro = np.array(obj.projections['Mean'])
# medpro = np.array(obj.projections['Med'])
# stdpro = np.array(obj.projections['Std'])
# rangepro = np.array(obj.projections['Range'])

# np.save(moviePath + '/max_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', maxpro)
# np.save(moviePath + '/min_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', minpro)
# np.save(moviePath + '/mean_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', meanpro)
# np.save(moviePath + '/med_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', medpro)
# np.save(moviePath + '/std_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', stdpro)
# np.save(moviePath + '/range_' + str(obj.lineNum) + '_' + str(movieNums[0]) + '-' + str(movieNums[-1]) + '.npy', rangepro)