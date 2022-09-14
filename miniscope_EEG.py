# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 19:54:58 2020

@author: eric
"""

# import csv
import EEG
import miniscope
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['svg.fonttype'] = 'none'
import misc_Functions
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

class miniscopeEEG(EEG.NeuralynxEEG, miniscope.UCLAMiniscope):
    """This is the class definition for handling miniscopes and simultaneous EEG data."""
    def __init__(self, lineNum=None, filename='experiments.csv', filenameMiniscope='metaData.json', analysisFilename='analysis_parameters.csv', jobID=''):
        super().__init__(lineNum=lineNum, filename=filename, filenameMiniscope=filenameMiniscope, analysisFilename=analysisFilename, jobID=jobID) #FIXME Does this init statment need to be here? Will it inherit from EEG or miniscope if it's not?

    def importEvents(self, channel='CBvsPFCEEG', writeFile=False, ttl=False,plot=False):
        """Translate the events imported from self.experiment['Miniscope settings filename']
        into a common time as the Neuralynx time format and combine the events from the two sources."""
        self.NeuralynxImportEvents()
        self.importEphysData(channels=channel)
        self._syncCaMovieTimes(channel, writeFile, ttl)
        self.correctTimeStamps(channel,plot)


    def _syncCaMovieTimes(self, channel, writeFile=False, ttl=False):
        """Create time vector for calcium movies from TTL events in Neuralynx."""
        print('Syncing Calcium Movie Times...')
        try:
            self.tCaIm = []
            file = misc_Functions._findFilePaths(directory=self.experiment['directory'],fileStartsWith='syncCaMovieTimes')[0]
            with open(file, newline='') as f:
                reader = csv.reader(f)
                self.pOUC = list(reader[1])
                next(f)
                reader = csv.reader(f)
                for row in reader:
                    self.tCaIm.append(float(row[1]))
            self.tCaIm = np.asarray(self.tCaIm)
        except AttributeError:
            frameAcqIdx = (self.NeuralynxEvents['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).') | (self.NeuralynxEvents['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0001).')
            if ttl: 
                self.tCaIm = self.NeuralynxEvents['timestamps'][frameAcqIdx]
                return
            endPoint = round(int(self.samplingRate[channel]) * 2 / int(self.experiment['frameRate'])) 
            self._tIdxCaIm = np.empty(len(self.NeuralynxEvents['timestamps'][frameAcqIdx]),dtype=int)
            lastIndex = 0
            for k, caImEvent in enumerate(self.NeuralynxEvents['timestamps'][frameAcqIdx]):
                self._tIdxCaIm[k] = self._findtIdxCaIm(k,caImEvent,lastIndex,channel,endPoint)
                lastIndex = self._tIdxCaIm[k]
            self.tCaIm, self.pOUC = self._correcttCaIm(self.tEEG[channel][self._tIdxCaIm])
            if writeFile:
                with open((self.filePath+'//syncCaMovieTimes.csv'), 'w', newline='') as nf:
                    writer = csv.writer(nf) 
                    pOUC = []
                    # pOUC.append('Period(s) of Uncertainty')
                    pOUC.append(self.pOUC)
                    # writer.writerow(pOUC)
                    header = []
                    header.append('Frame')
                    header.append('Time(s)')
                    writer.writerow(header)
                    lastIndex = 0
                    for k, ti in enumerate(self.tCaIm):
                        line = []
                        line.append(k)
                        line.append(ti)
                        writer.writerow(line)


    def _correcttCaIm(self, tCaIm):
        dtCaIm = np.diff(tCaIm)
        frameRate = self.experiment['frameRate']
        lTTLaI = np.where(dtCaIm > .040)[0] # long TTL array index
        nAFPI = [] # number add frames per index
        for i in lTTLaI:
            nAFPI.append(round(dtCaIm[i]/(1/frameRate)))
        nT = []
        # aug = 0
        start = []
        end = []
        pOUC = [] # period of uncertainty
        for h, ti in enumerate(tCaIm):
            if h in lTTLaI:
                idx = int(np.where(lTTLaI==(h))[0])
                nFD = nAFPI[idx] + 1
                l = np.linspace(tCaIm[h], tCaIm[h+1], nFD)
                start.append(h)
                end.append(h+1)
                for i, num in enumerate(l):
                    if i != (len(l) - 1):
                        nT.append(num)
                # aug+=nFD
            else:
                nT.append(tCaIm[h])
       
        for k, idx in enumerate(start):
            pOUC.append(str(f"{round(tCaIm[idx],4):08}") + '-' + str(f"{round(tCaIm[end[k]],4):08}")) #FIXME
        return(nT, pOUC)


    def _phaseCaEvents(self, channel, neuron='all'):
        """Compare calcium events to the phase extracted from a specified EEG channel."""
        self._syncCaMovieTimes(channel)
        phaseEEG = self.computePhase(channel)
        neurons = self.thresholdedEvents #FIXME to be the output of the thresholding function
        if neuron == 'all':
            self.CaEventsPhases = phaseEEG[:] #FIXME to work with actual data
            self.CaEventsNeurons = neurons[:] #FIXME to work with actual data
        elif type(neuron) == int:
            self.CaEventsPhases = phaseEEG[:] #FIXME to work with actual data
            self.CaEventsNeurons = neurons[:] #FIXME to work with actual data


    def phaseCaEventsHistogram(self, channel='CBvsPFCEEG', neuron='all', bins=18, plotHistogram=False):
        """Compute the histogram of calcium events vs phase.
        CHANNEL is the channel to compare the timing of calcium events to.
        NEURON is a list of the neuron indexes to compare. All neurons can be selected with 'all'.
        PLOTHISTOGRAM chooses whether or not to plot the computed histogram."""
        self._phaseCaEvents(channel, neuron)
        if plotHistogram:
            plt.figure()
            ax = misc_Functions.prepAxes(xLabel='Phase (rad)', yLabel='Event Count')
            self.hist, self.binEdges = ax.hist(self.CaEventsPhases, bins=bins)
        else:
            self.hist, self.binEdges = np.histogram(self.CaEventsPhases, bins=bins)


    def phaseCaEventsPolarPlot(self, channel='CBvsPFCEEG', neuron='all', bins=18, plotMeanVector=True):
        """"""
        pass


    def saveData(self):
        """Saves extracted phases of calcium events, along with neuron and rat IDs and other info, to a CSV file for further processing."""
        df = pd.read_csv("miniscope_EEG_rats.csv", encoding="ISO-8859-1" )  #reading csv file
        for index, row in df.iterrows():   # filtering the rows where job is Govt
        	if self.experiment['id'] in row['Rat ID']:
        		sex = row['Sex']
        else:
            print("No such variable found")
        length = len(self.CaEventsPhases)
        list_data = {"Phase":self.CaEventsPhases, 'NeuronID':self.CaEventsNeurons, 'RatID':[self.experiment['id']] * length, 'Sex': [sex] * length, 'Condition':[self.experiment["systemic drug"]] * length}
        #FIXME There needs to be code here to write this array back to the CSV file. Call Isaac's code in misc_Functions to do so.


    def correctTimeStamps(self,channel='CBvsPFCEEG', plot=False):
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
                file = misc_Functions._findFilePaths(directory=self.experiment['directory'],fileStartsWith='syncCaMovieTimes')[0]
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


    def _turningPoints(self,timeStamps,numDroppedFrames,plot=False):
        # step detection algorithm borrowed from https://stackoverflow.com/questions/48000663/step-detection-in-one-dimensional-data
        self.clockTime = self.tCaIm - self.tCaIm[0] # FIXME make not self throughout function
        self.clockDiffStart = self.timeStamps - self.clockTime[:len(timeStamps)] 
        self.clockDiffEnd = self.timeStamps[len(timeStamps)-numDroppedFrames:] - self.clockTime[len(timeStamps):] # FIXME consider if you need to add number of dropped frames so this is right
        #check the beginning
        startInd = self._stepID(self.clockDiffStart,plot)
        #check the end
        endInd = self._stepID(self.clockDiffEnd,plot) + len(timeStamps)
        self.inds = np.concatenate((startInd,endInd))
        return(self.inds)


    def _angle(self,directions):
        """Return the angle between vectors
        """
        vec2 = directions[1:]
        vec1 = directions[:-1]
    
        norm1 = np.sqrt((vec1 ** 2).sum(axis=1))
        norm2 = np.sqrt((vec2 ** 2).sum(axis=1))
        cos = (vec1 * vec2).sum(axis=1) / (norm1 * norm2)   
        return np.arccos(cos)


    def _stepID(self,clockDiff,plot):
        d = clockDiff
        dary = np.array([*map(float, d)])
        dary -= np.average(dary)
        step = np.hstack((np.ones(len(dary)), -1*np.ones(len(dary))))
        dary_step = np.convolve(dary, step, mode='valid')
        
        # using RDP algorithm borrowed from https://www.gakhov.com/articles/find-turning-points-for-a-trajectory-in-python.html
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


    def _findtIdxCaIm(self,k,caImEvent,lastIndex,channel,endPoint):
        if k == 0:
            _tIdxCaIm = np.abs(self.tEEG[channel][lastIndex:]-caImEvent).argmin()+lastIndex
        elif (len(self.tEEG[channel][lastIndex:]) - endPoint < 0):
            _tIdxCaIm = np.abs(self.tEEG[channel][lastIndex:]-caImEvent).argmin()+lastIndex
        else:
            _tIdxCaIm = np.abs(self.tEEG[channel][lastIndex:(lastIndex + endPoint)]-caImEvent).argmin()+lastIndex
        return(_tIdxCaIm)