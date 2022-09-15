# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 09:10:23 2020

@author: eric
"""

import experiment
from pylab import *
import numpy as np
from scipy.signal import hilbert, firwin, filtfilt
from scipy.signal import hann
import matplotlib.pyplot as plt
# plt.rcParams['svg.fonttype'] = 'none'
from mne.time_frequency import psd_array_multitaper
from neo.io import NeuralynxIO
import misc_Functions
import math
import sys
import time
get_ipython().run_line_magic('matplotlib', 'inline')
from scipy.io import loadmat

class NeuralynxEEG(experiment.experiment):
    """This is the class definition for handling Neuralynx EEG data."""
    
    def importEphysData(self,channels='all',importEvents=True,removeArtifacts=False, 
                        VThreshold=1500,TThreshold=60,plot=False,hannNum=75):
        """Import Neuralynx continuously sampled channel data and associated events.
        CHANNELS can be 'all', 'none' (if you just want to import the events),
        or a string or list of strings."""
        print('Importing ephys data...')
        start_time = time.time()
        self.filePath = misc_Functions._findFilePaths(self.experiment['directory'], fileExtensions='.nev', fileStartsWith='Events', removeFile=True)[0]
        self._recording = NeuralynxIO(self.filePath)
        self._ephysData = self._recording.read_block(signal_group_mode='split-all')
        self.samplingRate = {}
        self.tEEG = {}
        self.EEG = {}
        if channels == 'all':
            channels = self.experiment['LFP and EEG CSCs'].split(';')
        if channels != 'none':
            for k, c in enumerate(self._ephysData.segments[0].analogsignals):
                if c.name in channels:
                    self.samplingRate[c.name] = c.sampling_rate.magnitude
                    dt = 1/self.samplingRate[c.name]
                    tStart = c.t_start.magnitude
                    tStop = self._ephysData.segments[-1].analogsignals[k].t_stop.magnitude
                    # Since tStop is actually one timestep beyond the time of the last sample, 
                    # evaluate whether there needs to be another time point at the end
                    # to accommodate the timing of the last segment (and not leave the
                    # last element stranded). The '=' in the '<=' is to account for the
                    # fact that .argmin() in self._makeEEGarrays() looks for the first
                    # occurance of the minimum when there is more than one candidate.
                    if (tStop - tStart) % dt <= (dt / 2):
                        tStop -= 0.51 * dt # subtract just over half of a dt to bump it down a time point
                    self.tEEG[c.name] = np.arange(tStart, tStop, dt)
                    self._makeEEGarrays(k)
                    # For each channel, after making the EEG arrays, find the element
                    # of the time vector closest to self.experiment['zero time (s)']
                    # and subtract the time at that element from the entire time array
                    zeroIdx = (np.abs(self.tEEG[c.name] - self.experiment['zero time (s)'])).argmin()
                    self.tEEG[c.name] -= self.tEEG[c.name][zeroIdx]
                    if removeArtifacts:
                        self.artifactRemoval(channel=c.name,VThreshold=VThreshold,
                                             TThreshold=TThreshold,plot=plot,hannNum=hannNum)
        if importEvents:
            self.NeuralynxImportEvents(analogSignalImported=True)
        print('--- %s seconds ---' % (time.time() - start_time))
    
    def _makeEEGarrays(self, chNum):
        """Method for concatenating EEG data and interpolating data between timestamp jumps.
        CHNUM is the channel number"""
        # Make a vector of NaNs equal in length to the time vector
        chName = self._ephysData.segments[0].analogsignals[chNum].name
        self.EEG[chName] = np.nan * np.ones(np.shape(self.tEEG[chName]))
        for seg in self._ephysData.segments:
            segSize = seg.analogsignals[chNum].size
            startIdx = (np.abs(self.tEEG[chName] - seg.t_start.magnitude)).argmin()
            # Interpolate the chunk between the last segment and the start of the current segment
            if seg.index > 0:
                interpStartIdx = np.where(np.isnan(self.EEG[chName]))[0][0]
                interpSegSize = startIdx-interpStartIdx
                self.EEG[chName][interpStartIdx:startIdx] = np.reshape(np.linspace(self.EEG[chName][interpStartIdx-1], seg.analogsignals[chNum][0].magnitude, interpSegSize+2)[1:-1], interpSegSize)
            # Add on the current segment
            self.EEG[chName][startIdx:(startIdx+segSize)] = np.reshape(seg.analogsignals[chNum].magnitude, segSize)


    def NeuralynxImportEvents(self, analogSignalImported=False):
        """Method for importing Neuralynx events."""
        print('Importing ephys events...')
        if not analogSignalImported:
            self.filePath = misc_Functions._findFilePaths(self.experiment['directory'], fileExtensions='.nev', fileStartsWith='Events', removeFile=True)[0]
            self._recording = NeuralynxIO(self.filePath)
            self._ephysData = self._recording.read_block(signal_group_mode='split-all')
        unsortedEventLabels = []
        unsortedEventTimestamps = []
        self.NeuralynxEvents = {}
        for seg in self._ephysData.segments:
            for e in seg.events:
                for k, l in enumerate(e.labels.astype(str)):
                    unsortedEventLabels.append(l)
                    unsortedEventTimestamps.append(e.times[k].magnitude)
        # Sort all of the events
        npUnsortedEventLabels = np.array(unsortedEventLabels)
        npUnsortedEventTimestamps = np.array(unsortedEventTimestamps)
        evSortInds = np.argsort(npUnsortedEventTimestamps)
        self.NeuralynxEvents['labels'] = npUnsortedEventLabels[evSortInds]
        self.NeuralynxEvents['timestamps'] = npUnsortedEventTimestamps[evSortInds] - self.experiment['zero time (s)']

        
    def computeSpectrogram(self, channel='CBvsPFCEEG', windowLength=30, 
                           windowStep=3, freqLims=[0,50], bandwidth=2, 
                           plotSpectrogram=False, plotEvents=True):
        """Estimate (and plot) the multi-taper spectrogram of a specified ephys channel. Developed with code mostly from Morgan Siegmann."""
        print('Computing spectrogram...')
        fs = int(self.samplingRate[channel])
        windowLengthSamples = windowLength * fs
        windowStepSamples = windowStep * fs
        EEGMat = misc_Functions._overlapBinning(self.EEG[channel], windowLengthSamples, windowStepSamples)
        # Make a time vector
        tMat = misc_Functions._overlapBinning(self.tEEG[channel], windowLengthSamples, windowStepSamples)
        self.tSpect = tMat[:,windowLengthSamples // 2]
        PSDSpect, self.freqsSpect = psd_array_multitaper(EEGMat, fs, fmin=freqLims[0], fmax=freqLims[1], bandwidth=bandwidth)
        self.pSpect = np.transpose(10 * np.log10(PSDSpect))
        if plotSpectrogram:
            h, ax = misc_Functions.spectrogram(self.tSpect/60, self.freqsSpect, self.pSpect, xLabel='Time (min)')
            if plotEvents:
                misc_Functions.markEvents(ax, self.NeuralynxEvents['timestamps']/60)
            return h, ax


    def computePhase(self, channel):
        """Compute the instantaneous phase of a specified ephys channel."""
        print('Computing instantaneous phase...')
        analyticSignalEEG = hilbert(self.EEG[channel])
        self.instantaneousPhaseEEG = np.unwrap(np.angle(analyticSignalEEG))
    
    
    def artifactRemoval(self, channel='CBvsPFCEEG', VThreshold=1500, TThreshold=60, 
                        plot=True, hannNum=75): 
        """artifactRemoval is a 2 x L matrix with the beginning and end times 
        (in seconds) that shoulb be removed from the raw signal.
        VThreshold= voltage threshold
        TThreshold= time threshold, in (s) if the gap time between threshold crossing is less than TThresh, all the voltage in between them will also be converted to 0"""
        print("Removing artifacts...")
        try:
            EEG = self.EEG[channel]
        except:
            self.importEphysData(channels=channel)
            EEG = self.EEG[channel]
        
        dt = self.tEEG[channel][1]-self.tEEG[channel][0]
        mean = np.mean(EEG) 
        meanCalcVect = np.vectorize(misc_Functions._calcNumMinusMean)
        EEG = meanCalcVect(EEG,mean)

        # implement thresholding
        
        compVThreshVect = np.vectorize(misc_Functions._compVThresh)
        decimateMask = compVThreshVect(EEG,VThreshold)
    
        # find area with small gap in between threshold crossing
        
        diffMask = np.diff(decimateMask)
        diffMaskNeg1 = np.where(diffMask == -1)[0]

        for k in diffMaskNeg1:
            diffMaskNext1 = np.where(diffMask[k:] == 1)[0]
            for index in diffMaskNext1:
                if (index - 1) < TThreshold/dt:
                    decimateMask[k:(k - 2 + index)] = True
        han = hann(hannNum) 
        invHan = abs(han - 1) 
        halfHan = math.floor(np.size(invHan)/2)
        decLocs = np.where(decimateMask)[0]
        
        for ele in decLocs:
            plusH = ele + halfHan + 1
            minusH = ele - halfHan 
            
            if np.size(EEG) >= plusH:
                if minusH > 0:
                    EEG[minusH: plusH] = np.multiply(EEG[minusH: plusH], invHan) 
                else:
                    EEG[0: plusH] = np.multiply(EEG[0: plusH], invHan[(halfHan - decLocs + 1):])
            else:
                sizeEEGmod = np.size(EEG[minusH:])
                EEG[minusH:] = np.multiply(EEG[minusH:], invHan[0: sizeEEGmod]) 
        
        self.EEG[channel]=EEG
        if plot:
            print('Plotting ' + channel + '...')
            plt.figure()
            plt.plot(EEG)
            plt.title('{0}'.format(channel))
            plt.xlabel('Time(s)')
            plt.ylabel('Voltage(\u03BC'+'V)')
            
    class filteredEEG():
        """This is an empty class in which to store filtering properties and filtered data."""
        pass
   
    def filterEEG(n=5, wn=[0.5,4], channel='CBvsPFCEEG', ftype = 'Butterworth', btype = 'band'):
        """Method for filtering the ephys channel of choice with either a Butterworth or FIR filter."""
        print('Filtering ' + channel + ' with a(n) ' + ftype + ' filter ...')
        fdata = self.filteredEEG()
        try:
            fdata.data = misc_Functions.filterData(self.tEEG[channel], self.EEG[channel], n=n, wn=wn, ftype=ftype, btype=btype)
        except:
            self.importEphysData(channels=channel)
            fdata.data = misc_Functions.filterData(self.tEEG[channel], self.EEG[channel], n=n, wn=wn, ftype=ftype, btype=btype)
        fdata.channel = channel
        fdata.cutoff = wn
        fdata.ftype = ftype
        fdata.btype = btype
        fdata.order = n
        
        try:
            self.fdata.append(fdata)
            
        except:
            self.fdata = []
            self.fdata.append(fdata)
