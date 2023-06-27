# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 19:54:58 2020

@author: eric

This file contains classes that are used to analyze simultaneous calcium
imaging and ephys, including from the UCLA Miniscope V4 and Neuralynx DAQ.
Methods to syncronize the timing of events and analyze relationships between
the different types of data are included.
"""

# import csv
import ephys
import miniscope
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['svg.fonttype'] = 'none'
import misc_functions
import experiment
import sys
import csv
from math import sqrt
from six.moves import zip
import scipy.signal
import scipy.interpolate
from rdp import rdp
import time
import pandas as pd

class miniscopeEphys(ephys.NeuralynxEphys, miniscope.UCLAMiniscope):
    """This is the class definition for handling miniscopes and simultaneous ephys data."""
#%% Methods for importing experiment info, metadata, and analysis parameters
    def __init__(self, lineNum=None, filename='experiments.csv', filenameMiniscope='metaData.json', analysisFilename='analysis_parameters.csv', jobID=''):
        super().__init__(lineNum=lineNum, filename=filename, filenameMiniscope=filenameMiniscope, analysisFilename=analysisFilename, jobID=jobID) #FIXME Does this init statment need to be here? Will it inherit from ephys or miniscope if it's not?


#%% Methods for extracting timing of calcium image acquisition, deleting timestamps of dropped frames, and matching timestamps with ephys timestamps
    def syncNeuralynxMiniscopeTimestamps(self, channel='PFCLFPvsCBEEG', deleteTTLs=True):
        """Create time vector for calcium movies from TTL events in Neuralynx."""
        print('Syncing calcium movie times...')
        
        # create the self.tCaIm, which is the array of labels and timestamps for the Neuralynx events that occur for each calcium image frame acquisition
        frameAcqIdx = (self.NeuralynxEvents['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).') | (self.NeuralynxEvents['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0001).')
        self.tCaIm = self.NeuralynxEvents['timestamps'][frameAcqIdx]
        
        # Check for gaps in the TTL event timestamps and insert a timestamp guess if needed
        self.lowConfidencePeriods = np.array([])
        self._correcttCaIm(self.NeuralynxEvents['labels'][frameAcqIdx])
        
        # delete the TTL events that correspond to dropped frames in the saved calcium movie, specified in analysis_parameters.csv. This currently assumes that any gaps in the TTL events have been corrected already.
        #TODO Add a method that plots the 3 figures of the timestamps for help in deciding which events to drop, then writes to analysis_parameters.csv and self._analysisParamsDict['indices of TTL events to delete'].
        if deleteTTLs:
            self.tCaIm = np.delete(self.tCaIm, self._analysisParamsDict['indices of TTL events to delete'])


    def _correcttCaIm(self, eventLabels, threshold=0.04):
        """This method first confirms that the TTL events alternate and then checks for missing TTL events. If there are any, the method guesses their timing and inserts them into the calcium imaging time vector.
        EVENTLABELS is the array of imported Neuralynx event labels.
        THRESHOLD is the time threshold, in seconds, for detecting gaps in the TTL events."""
        print('Checking that TTL events alternate...')
        # Print a message if the TTL event labels do not alternate between HIGH and LOW
        alternating = []
        for q in range(0,len(eventLabels)-2):
            alternating.append(np.char.equal(eventLabels[q+2], eventLabels[q]))
        alternating.append(np.char.not_equal(eventLabels[-1], eventLabels[-2]))
        if sum(alternating) != (len(eventLabels) - 1):
            print('TTL does not alternate!')
            sys.exit() # Exit program execution if this condition is reached.
        
        print('Fixing any gaps in the TTL events...')
        dtCaIm = np.diff(self.tCaIm)
        idxTTLGap = np.where(dtCaIm > threshold)[0] # indices of gaps in the TTL events
        flippedIdxTTLGap = np.flip(idxTTLGap) # Reverse the order of idxTTLGap so that inserting TTLs in the loop doesn't affect the indices of the next iteration of the loop.
        gapLength = [] # number dropped frames per index
        for k, gapIdx in enumerate(flippedIdxTTLGap):
            gapLength.append(round(dtCaIm[gapIdx]/(1/self.experiment['frameRate']))) # Guesses how many timesteps occur in the gap. E.g., a 30 Hz video with a gap of 67 ms will have 2 timesteps in the gap.
            print(str(gapLength[k]-1) + ' TTL event(s) is/are missing between index numbers ' + str(gapIdx) + ' and ' + str(gapIdx + 1) + '.')
            estimatedEventTimes = np.linspace(self.tCaIm[gapIdx], self.tCaIm[gapIdx+1], gapLength[k]+1) # Estimates the timing of the TTLs, beginning at the one before the gap and ending at the one after the gap.
            self.tCaIm = np.insert(self.tCaIm, gapIdx, estimatedEventTimes[:-1])
            self.lowConfidencePeriods = np.append(self.lowConfidencePeriods, [[gapIdx, gapIdx+gapLength[k]-1]], axis=0)


    def correctTimeStamps_OLD(self,channel='PFCLFPvsCBEEG', plot=False):
        print('Correcting time stamps...')
        start_time = time.time()
        
        '''
        TODO
            run on that data
            it finds steps
            period of uncertainty
            Party
        '''

        # A whole bunch of fail safes
        try:
            x = len(self.tCaIm)
        except AttributeError:
            try:
                self.tCaIm = []
                file = misc_functions._findFilePaths(directory=self.experiment['calcium imaging directory'],fileStartsWith='syncCaMovieTimes')[0]
                with open(file, newline='') as f:
                    reader = csv.reader(f)
                    self.pOUC = list(reader[1])
                    next(f)
                    for row in reader:
                        self.tCaIm.append(float(row[1]))
                self.tCaIm = np.asarray(self.tCaIm)
                x = len(self.tCaIm)
            except AttributeError:
                self.importEvents(channel=channel)
                x = len(self.tCaIm)
        
        # Starts comparing TTL timestamps to miniscope timestamps and finds points of instability
        
        if len(self.timeStamps) == len(self.tCaIm):
            return
        else:
            numDroppedFrames = len(self.tCaIm)-len(self.timeStamps)
            dropFramesIndices = self._turningPoints(self.timeStamps,numDroppedFrames,plot)
            sectionMeans = []
            for k,val in enumerate(dropFramesIndices):
                if k == 0:
                    mean = np.mean(self.clockDiffStart[:int(val)]) 
                    sectionMeans.append(mean)
                elif val == dropFramesIndices[-1]:
                    mean = np.mean(self.clockDiffStart[int(val):])
                    sectionMeans.append(mean)
                    break
                else:
                    mean = np.mean(self.clockDiffStart[int(val):int(dropFramesIndices[k+1])])
                    sectionMeans.append(mean)
            diffTimes = abs(np.diff(sectionMeans))
            tPF = 1 / self.experiment['frameRate']
            nDFPI = [] # number of dropped frames per index
            for val in diffTimes:
                nDFPI.append(round(val/tPF))
            if sum(nDFPI) != numDroppedFrames:
                raise ValueError('Wrong number of frames to be deleted found')
            else:
                self.tCaIm = list(self.tCaIm)
                PoUC = [] # Period of Uncertainty
                for k, index in enumerate(dropFramesIndices[:-1]):
                    string = ''
                    start = None
                    end = None
                    if nDFPI[k] != 0:
                        if nDFPI[k] == 1:
                            self.tCaIm.pop(int(index))  
                            #self.tCaIm.pop(int(index+1))
                            start = self.tCaIm[int(index)]
                            end = self.tCaIm[int(index + 1)]
                        else:
                            x = list(range(nDFPI[k]))
                            for l in x:
                                self.tCaIm.pop(int(index + l))
                                if (l == 0):
                                    start = self.tCaIm[int(index+l)]
                                    # print(start)
                                elif (l == (nDFPI[k]-1)):
                                     end = self.tCaIm[int(index+l)]
                                     #print(end)# decide how long the end time should be?
                        string = str(f"{start:08}") + '-' + str(f"{end:08}")
                        PoUC.append(string)
                self.pOUC = np.sort(np.concatenate((self.pOUC,PoUC)))
                if len(self.tCaIm) != len(self.timeStamps):
                    raise ValueError('Number deleted frames is incorrect')
                print(self.pOUC)
        print("--- %s seconds ---" % (time.time() - start_time))


    def _turningPoints_OLD(self,timeStamps,numDroppedFrames,plot=False):
        """Step detection algorithm borrowed from https://stackoverflow.com/questions/48000663/step-detection-in-one-dimensional-data."""
        self.clockTime = self.tCaIm - self.tCaIm[0] # FIXME make not self throughout function
        self.clockDiffStart = self.timeStamps - self.clockTime[:len(timeStamps)] 
        self.clockDiffEnd = self.timeStamps[len(timeStamps)-numDroppedFrames:] - self.clockTime[len(timeStamps):] # FIXME consider if you need to add number of dropped frames so this is right
        # Check the beginning
        startInd = self._stepID(self.clockDiffStart,plot)
        # Check the end
        endInd = self._stepID(self.clockDiffEnd,plot) + len(timeStamps)
        self.inds = np.concatenate((startInd,endInd))
        return(self.inds)


    def _angle_OLD(self,directions):
        """Return the angle between vectors."""
        vec2 = directions[1:]
        vec1 = directions[:-1]
    
        norm1 = np.sqrt((vec1 ** 2).sum(axis=1))
        norm2 = np.sqrt((vec2 ** 2).sum(axis=1))
        cos = (vec1 * vec2).sum(axis=1) / (norm1 * norm2)   
        return np.arccos(cos)


    def _stepID_OLD(self,clockDiff,plot):
        """"""
        d = clockDiff
        dary = np.array([*map(float, d)])
        dary -= np.average(dary)
        step = np.hstack((np.ones(len(dary)), -1*np.ones(len(dary))))
        dary_step = np.convolve(dary, step, mode='valid')
        
        # Using RDP algorithm borrowed from https://www.gakhov.com/articles/find-turning-points-for-a-trajectory-in-python.html
        var = np.empty(len(dary_step)*2)
        for k,val in enumerate(dary_step):
            var[2*k] = k
            var[2*k+1] = val
        
        trajectory = np.asarray(var).reshape(len(dary_step),2)
        epsilon = 31 # FIXME This number is arbitrary .1 * len(clockDiff)- this works for smaller cases 
        simplified_trajectory = rdp(trajectory, epsilon=epsilon)
        sx, sy = simplified_trajectory.T
        
        # Define a minimum angle to treat change in direction as significant (valuable turning point).
        min_angle = 0
    
        # Compute the direction vectors on the simplified_trajectory.
        directions = np.diff(simplified_trajectory, axis=0)
        theta = self._angle(directions)
        
        # Select the index of the points with the greatest theta. Large theta is associated with greatest change in direction.
        idx = np.where(theta > min_angle)[0] + 1
    
        epsilon = epsilon*5 #makes graph aspect look right
        
        # Visualize valuable turning points on the simplified trjectory.
        if plot:
            plt.plot(sx, sy/(epsilon), 'gx-', label='simplified trajectory')
            plt.plot(sx[idx], sy[idx]/(epsilon), 'ro', markersize = 7, label='turning points')
            plt.legend(loc='best')
            plt.plot(dary)
            plt.plot(dary_step/(epsilon))
            plt.show()
        return(sx[idx])


    def findEphysIdxOfTTLEvents(self, channel='PFCLFPvsCBEEG', allTTLEvents=True, CaEvents=True):
        """Finds the index of a calcium event in the Neuralynx timespace. If the miniscope class method to find the timing of calcium events has not been run yet, it runs that first.
        CHANNEL is the ephys channel with which to compare the timing of the ephys samples to the calcium event timing."""
        # Match up all calcium movie timestamps with their corresponding ephys timestamps.
        if allTTLEvents:
            try:
                tCaImLength = len(self.tCaIm)
            except AttributeError:
                self.syncNeuralynxMiniscopeTimestamps(channel=channel)
            finally:
                print('Finding the indices of ephys timestamps that are closest to all calcium movie frame acquisition TTL events...')
                self.ephysIdxAllTTLEvents = np.empty(len(self.tCaIm),dtype=int)
                # Choose a number of indices after the lastIndex before which you are confident that the next index will be.
                # I am choosing the number of ephys indices during the time it takes for two calcium imaging frames.
                endPoint = round(int(self.samplingRate[channel]) * 2 / int(self.experiment['frameRate']))
                lastIndex = 0
                
                for k, CaImTTLEvent in enumerate(self.tCaIm):
                    if k == 0:
                        self.ephysIdxAllTTLEvents[k] = np.abs(self.tEphys[channel][lastIndex:] - CaImTTLEvent).argmin() + lastIndex
                    elif len(self.tEphys[channel][lastIndex:]) - endPoint < 0:
                        self.ephysIdxAllTTLEvents[k] = np.abs(self.tEphys[channel][lastIndex:] - CaImTTLEvent).argmin() + lastIndex
                    else:
                        self.ephysIdxAllTTLEvents[k] = np.abs(self.tEphys[channel][lastIndex:(lastIndex + endPoint)] - CaImTTLEvent).argmin() + lastIndex
                    lastIndex = self.ephysIdxAllTTLEvents[k]
                
        # Look for the indices of the ephys timestamps that are closest to the calcium event (Neuralynx) timestamps.
        if CaEvents:
            try:
                CaEventsIdxLength = len(self.CaEventsIdx)
            except AttributeError:
                self.findCalciumEvents()
            finally:
                print('Finding the indices of ephys timestamps that are closest to the calcium event (Neuralynx) timestamps...')
                self.ephysIdxCaEvents = {}
                for k in list(self.CaEventsIdx.keys()):
                    self.ephysIdxCaEvents[k] = []
                    lastIndex = 0
                    for j in range(len(self.CaEventsIdx[k])):
                        self.ephysIdxCaEvents[k].append(np.abs(self.tEphys[channel][lastIndex:] - self.tCaIm[self.CaEventsIdx[k][j]]).argmin() + lastIndex)
                        # Check to see if the gap between the calcium event time and the corresponding ephys timestamp is reasonable (within 1 frame's timestep).
                        if np.abs(self.tEphys[channel][self.ephysIdxCaEvents[k][j]]-self.tCaIm[self.CaEventsIdx[k][j]]) > (1/self.experiment['frameRate']):
                            print('There are no ephys timestamps closer to the calcium event timestamp than the duration of a calcium movie frame!')
                        lastIndex = self.ephysIdxCaEvents[k][j]
                    self.ephysIdxCaEvents[k] = np.array(self.ephysIdxCaEvents[k])


#%% Methods to extract the instantaneous phase of the ephys signal, determine the phases of the calcium events, and summarize and save the results
    def phaseCaEvents(self, channel='PFCLFPvsCBEEG', neuron='all'):
        """Compare calcium events to the phase extracted from a specified ephys channel.
        CHANNEL is the ephys channel name.
        NEURON is the neuron number (i.e., the integer row number in self.estimates.C, starting with 0) of the neuron you want to compare. If you want to compare all of the neurons in the recording, pass 'all' as the argument."""
        try:
            tCaImLength = len(self.tCaIm)
        except AttributeError:
            self.syncNeuralynxMiniscopeTimestamps(channel=channel)
        finally:
            self.computePhase(channel)
            print('Comparing the calcium events to the corresponding phase of ' + channel + '...')
            self.CaEventsPhases = {}
            if neuron == 'all':
                neurons = list(self.ephysIdxCaEvents.keys())
            elif type(neuron) != list:
                neurons = [neuron]
            for k in neurons:
                self.CaEventsPhases[k] = []
                for j in range(len(self.ephysIdxCaEvents[k])):
                    self.CaEventsPhases[k].append(self.instantaneousPhaseEphys[channel][self.ephysIdxCaEvents[k][j]])
                self.CaEventsPhases[k] = np.array(self.CaEventsPhases[k])


    def phaseCaEventsHistogram(self, channel='PFCLFPvsCBEEG', neuron='all', bins=18, histRange=(-np.pi,np.pi), density=False, meanDensity=True, plotHistogram=False, combined=False):
        """Compute the histogram of calcium events/probability density vs phase.
        CHANNEL is the channel to compare the timing of calcium events to.
        NEURON is a list of the neuron indexes to compare. All neurons can be selected with 'all'.
        BINS is the number of bins to sort the data into.
        HISTRANGE is a tuple of the range that the bins should cover.
        DENSITY determines whether the data will be bins will represent a probability density or a count.
        MEANDENSITY provides the mean of the density histograms of all specified neurons.
        PLOTHISTOGRAM chooses whether or not to plot the computed histogram.
        COMBINED is a boolean that determines whether to combine the data from all of the specified neurons or whether to create histograms for each of the specified neurons."""
        print('Creating a histogram of the phases of ' + channel + ' relative to the calcium events...')
        try:
            lengthCaEventsPhases = len(self.CaEventsPhases)
        except AttributeError:
            self.phaseCaEvents(channel, neuron)
        finally:
            if plotHistogram:
                if combined:
                    CaEventsPhases = np.array([])
                    # Flatten the dictionary of numpy arrays so that all calcium events are contained in the same array
                    if neuron == 'all':
                        if density:
                            if meanDensity:
                                # Mean density histogram across neurons
                                CaEventsPhasesHist = np.empty((0, bins))
                                meanCaEventsVectors = np.empty((0, 2))
                                self.meanCaEventsVectorTheta = []
                                self.meanCaEventsVectorRadius = []
                                for i, k in enumerate(list(self.CaEventsPhases.keys())):
                                    hist, self.binEdges = np.histogram(self.CaEventsPhases[k], bins=bins, range=histRange, density=True)
                                    CaEventsPhasesHist = np.concatenate((CaEventsPhasesHist, hist.reshape((1,-1))), axis=0)
                                    # Find the mean vector for each neuron's calcium events
                                    CaEventsVectors = np.concatenate((np.cos(self.CaEventsPhases[k]).reshape((-1,1)), np.sin(self.CaEventsPhases[k]).reshape((-1,1))), axis=1)
                                    meanCaEventsVectors = np.concatenate((meanCaEventsVectors, np.mean(CaEventsVectors,axis=0).reshape((1,2))), axis=0)
                                    self.meanCaEventsVectorTheta.append(np.arctan2(meanCaEventsVectors[i,1], meanCaEventsVectors[i,0]))
                                    self.meanCaEventsVectorRadius.append(np.sqrt(meanCaEventsVectors[i,0]**2 + meanCaEventsVectors[i,1]**2))
                                self.hist = np.mean(CaEventsPhasesHist, axis=0) # Take the mean across the neurons at each bin.
                                self.histError = np.std(CaEventsPhasesHist, axis=0) / np.sqrt(np.shape(CaEventsPhasesHist)[0]) # Take the standard error of the mean at each bin.
                                h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Mean Event Probability', title='Neuron(s): '+str(neuron))
                                ax.hist(self.binEdges[:-1], self.binEdges, weights=self.hist)
                                binMidpoints = (self.binEdges[1:] + self.binEdges[:-1]) / 2
                                ax.errorbar(binMidpoints, self.hist, yerr=self.histError, fmt='none', capsize=3)
                                # Find the mean vector of all of the neurons
                                meanNeuronVector = np.mean(meanCaEventsVectors, axis=0)
                                self.meanNeuronVectorTheta = np.arctan2(meanNeuronVector[1], meanNeuronVector[0])
                                self.meanNeuronVectorRadius = np.sqrt(meanNeuronVector[0]**2 + meanNeuronVector[1]**2)
                            else:
                                # Barstacked density histogram across neurons
                                CaEventsPhasesHist = list(self.CaEventsPhases.values())
                                h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(neuron))
                                self.hist, self.binEdges, _ = ax.hist(CaEventsPhasesHist, bins=bins, range=histRange, density=True, histtype='barstacked')
                        else:
                            for k in list(self.CaEventsPhases.keys()):
                                CaEventsPhases = np.concatenate((CaEventsPhases, self.CaEventsPhases[k]))
                            h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(neuron))
                            self.hist, self.binEdges, _ = ax.hist(CaEventsPhases, bins=bins, range=histRange)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        if density:
                            CaEventsPhasesHist = {}
                            for k in neuron:
                                CaEventsPhasesHist[k] = self.CaEventsPhases[k]
                            # Barstacked density histogram across neurons
                            CaEventsPhasesHist = list(self.CaEventsPhases.values())
                            h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(neuron))
                            self.hist, self.binEdges, _ = ax.hist(CaEventsPhasesHist, bins=bins, range=histRange, density=True, histtype='barstacked')
                        else:
                            for k in neuron:
                                CaEventsPhases = np.concatenate((CaEventsPhases, self.CaEventsPhases[k]))
                            h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(neuron))
                            self.hist, self.binEdges, _ = ax.hist(CaEventsPhases, bins=bins, range=histRange)
                else:
                    # Plot each of the neurons as separate histograms
                    ax = []
                    self.hist = {}
                    self.binEdges = {}
                    if neuron == 'all':
                        for i, k in enumerate(list(self.CaEventsPhases.keys())):
                            if density:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(k))
                            else:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(k))
                            ax.append(newAx)
                            self.hist[k], self.binEdges[k], _ = ax[i].hist(self.CaEventsPhases[k], bins=bins, range=histRange, density=density)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        for i, k in enumerate(neuron):
                            if density:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(k))
                            else:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(k))
                            ax.append(newAx)
                            self.hist[k], self.binEdges[k], _ = ax[i].hist(self.CaEventsPhases[k], bins=bins, range=histRange, density=density)
            else:
                if combined:
                    CaEventsPhases = np.array([])
                    # Flatten the dictionary of numpy arrays so that all calcium events are contained in the same array
                    if neuron == 'all':
                        for k in list(self.CaEventsPhases.keys()):
                            CaEventsPhases = np.concatenate((CaEventsPhases, self.CaEventsPhases[k]))
                        self.hist, self.binEdges = np.histogram(CaEventsPhases, bins=bins, range=histRange, density=density)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        for k in neuron:
                            CaEventsPhases = np.concatenate((CaEventsPhases, self.CaEventsPhases[k]))
                        self.hist, self.binEdges = np.histogram(CaEventsPhases, bins=bins, range=histRange, density=density)
                else:
                    # Plot each of the neurons as separate histograms
                    self.hist = {}
                    self.binEdges = {}
                    if neuron == 'all':
                        for k in list(self.CaEventsPhases.keys()):
                            self.hist[k], self.binEdges[k] = np.histogram(self.CaEventsPhases[k], bins=bins, range=histRange, density=density)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        for k in neuron:
                            self.hist[k], self.binEdges[k] = np.histogram(self.CaEventsPhases[k], bins=bins, range=histRange, density=density)


    def phaseCaEventsPolarPlot(self, channel='PFCLFPvsCBEEG', neuron='all', bins=18, plotMeanVector=True):
        """"""
        plt.subplot()
        self.hist


    def saveData(self, filename='neuron_phase.csv'):
        """Saves extracted phases of calcium events, along with neuron and rat IDs and other info, to a CSV file for further processing."""
        df = pd.read_csv("miniscope_Ephys_rats.csv", encoding="ISO-8859-1" )  #reading csv file
        for index, row in df.iterrows():   # filtering the rows where job is Govt
        	if self.experiment['id'] in row['Rat ID']:
        		sex = row['Sex']
        else:
            print("No such variable found")
        length = len(self.CaEventsPhases)
        list_data = {"Phase":self.CaEventsPhases, 'NeuronID':self.CaEventsNeurons, 'RatID':[self.experiment['id']] * length, 'Sex': [sex] * length, 'Condition':[self.experiment["systemic drug"]] * length}
        print('Saving calcium event phases and other attributes to ' + filename)
        misc_functions.appendRowCSV(list_data, filename=filename) #FIXME I haven't tested this yet.