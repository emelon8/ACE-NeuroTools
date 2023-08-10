# -*- coding: utf-8 -*-
"""
Created on Tue Aug  8 13:38:27 2023

@author: Eric

This script imports the estimates object for each of the calcium imaging
movies, finds the ephys indices that correspond to each event in estimates.C,
concatenates the ephys indices from the same neurons or adds a new row for new
neurons, finds the phases of the events RELATIVE TO THE AVERAGE MINISCOPE
FLUORESCENCE OVER TIME, and saves it as a single obj.CaEventsPhases dictionary.
"""

import miniscope_ephys
import misc_functions
import numpy as np
from natsort import natsorted, ns

channel = 'PFCLFPvsCBEEG'


#%% R221020A's experiments
# Sleep experiment
# lineNum = 37
# firstVideo = 174
# neuronMatrix = [[0,1,2,3],[0,1,2,4],[3],[0,5,3],[4,3],[3],[0,2],[2,3,6],[7],[0,1,8]]

# Low-dose dex experiment
lineNum = 41
firstVideo = 103
neuronMatrix = [[0,1,2,3,4],[0,1,3,5],[6,0,1,3,2],[7,0,8,9,2,10,3],[11,7,1,2,3,6],[12,0,8,4,9,3],[11,6,0,4,13,14,15,3],[6,8,4,14,3,16,17,10],[11,0,8,18,14,2,3,19,20],[21,6,22,0,8,1,14,23,3],[24,25,0,1,14,3,6],[6,26,0,1,14,3],[24,11,6,20,8,0,2,1,14,3],[8,14,3,2,17],[7,20,0,18,26,2],[21,6,0,27,1,14,28],[21,1,29,30,31,0,7]]

# Propofol experiment
# lineNum = 44
# firstVideo = 77
# neuronMatrix = [[0,1],[1,2,3],[1,4],[1,2],[1,2,3],[1,2],[5,6,1],[1,2],[7,1,2,3],[0,1,3],[1,2],[1,2,3],[0,1,3],[1],[1],[1],[1,3],[1],[0,1],[8,1,3],[7,1,3],[1],[0,1],[1,3],[1,3],[0,1],[0,1],[1],[1],[1],[7,1,9],[1],[0,1],[0,1,10],[1],[0,1,3],[1,3]]


#%% R2201020B's experiments
# Sleep experiment
# lineNum = 38
# firstVideo = 133
# neuronMatrix = [[0,1,2,3,4],[5,6,0,3,7,8],[9],[8,'bad','bad'],[8,4],[8,10],[11]]

# Low-dose dex experiment
# lineNum = 40
# firstVideo = 94
# neuronMatrix = [[0,1,2],[0,3,1,4,2,'bad',5],[0,3,6,2,7,8],[9,0,5,3,1,2],[10,5,3,11,2,12],[9,5,3,11,8,6,7,2],[9,0,11,2],[9,5,1,11,13,7,2],[10,0,5,2],[5,14,0,11,2],[9,0,2],[15,9,16,10,0,5,11,17,6,2],[9,0,5,11,7,2,12,18],[9,10,0,11,6,2],[15,0,2],[11,19,6,2],[10,5,3,11,6,2],[0,5,20,3,17,2],['bad',9,5,11,6],[5],[10,0,2],[9,5,10,0,11,6,4],[9,10,'bad',2],[9,10,0,2,11],[9,11,6,2],[3,11,2,16],[10,0,2],[11,2],[9,10,5,11,2,7],['bad',17,0,11],[2,19],[3,11,2],[9,0,3,11,6,2,19]]

# Propofol experiment
# lineNum = 43
# firstVideo = 65
# neuronMatrix = [['bad','bad','bad','bad',0,1,2],[0,1],['bad',0,1],['bad','bad',0,3,1],['bad',1,4],['bad',0,1],[0,1],['bad','bad','bad',0,1],['bad'],['bad','bad','bad','bad',1,5],[0,1],[0,1],['bad',0],['bad','bad',0],['bad',1],['bad','bad','bad',0,1],[0,3],[0],['bad']*10,['bad']*105,['bad']*18,['bad','bad','bad','bad','bad','bad',1,'bad'],[0,1],[0,1],[0,5],[],['bad','bad','bad','bad','bad','bad',3],['bad','bad','bad','bad','bad','bad','bad',6,0,7],['bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad','bad',3,'bad'],['bad',1],['bad']*57 + [8,'bad','bad','bad','bad','bad','bad',7,'bad']]


#%% Find the n (in neurons) for each experiment
flatNeuronMatrix = []
for b in neuronMatrix:
    for p in b:
        if p != 'bad':
            flatNeuronMatrix.append(p)
n = max(flatNeuronMatrix) + 1


#%% Load the data and create the histograms
obj = miniscope_ephys.miniscopeEphys(lineNum=lineNum)

obj.importEphysData(channels=channel)
obj.importNeuralynxEvents(analogSignalImported=True)
obj.syncNeuralynxMiniscopeTimestamps(channel=channel)

# Import all of the estimates objects and find the indices of each calcium event
estimatesObjectsPaths = misc_functions._findFilePaths(obj.experiment['calcium imaging directory'], fileExtensions='.hdf5')
estimatesObjectsPaths = natsorted(estimatesObjectsPaths, alg=ns.IGNORECASE) # needed if the modified times of the files aren't in order
CaEventsIdx = {}
for i, k in enumerate(estimatesObjectsPaths):
    obj.importComponents(k)
    obj.findCalciumEvents()
    for j in list(obj.CaEventsIdx.keys()):
        if len(obj.CaEventsIdx[j]) > 0:
            obj.CaEventsIdx[j] += (firstVideo+i)*1000
            if neuronMatrix[i][j] in list(CaEventsIdx.keys()):
                CaEventsIdx[neuronMatrix[i][j]] = np.concatenate((CaEventsIdx[neuronMatrix[i][j]], obj.CaEventsIdx[j]))
            elif neuronMatrix[i][j] == 'bad':
                pass
            else:
                CaEventsIdx[neuronMatrix[i][j]] = obj.CaEventsIdx[j]
        else:
            print('Renamed neuron ' + str(neuronMatrix[i][j]) + ' does not have any calcium events in ' + estimatesObjectsPaths[i])

# Find the ephys indices that correspond to the calcium events
obj.CaEventsIdx = CaEventsIdx.copy()

meanFluorescence = np.load('../../experimental_results/miniscope_ephys_correlation_project/npzFiles/meanFluorescence_' + str(lineNum) + '.npz')

fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=obj.experiment['frameRate'])
obj.miniscopePhaseCaEvents(data=fdataM)

# Plot histograms of the mean probability density of all of the neurons
obj.phaseCaEventsHistogram(plotHistogram=True, combined=True, density=True, meanDensity=True)

# Plot histograms of the event count of all of the neurons
# obj.phaseCaEventsHistogram(plotHistogram=True, combined=True, density=False)

# Plot histograms of all of the neurons
# obj.phaseCaEventsHistogram(plotHistogram=True, combined=False, density=False)

# Other plots
# obj.phaseCaEventsHistogram(plotHistogram=True, combined=True, density=True, meanDensity=False)