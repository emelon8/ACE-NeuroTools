# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 09:10:23 2020

@author: eric

This file contains classes that are used to analyze electrophysiology data,
including EEG/LFP data from a Neuralynx DAQ. Methods to import and analyze the
data are included.
"""

import experiment
import numpy as np
from scipy.signal import hilbert
from scipy.signal import hann
import matplotlib.pyplot as plt
# plt.rcParams['svg.fonttype'] = 'none'
from multitaper_spectrogram_python import multitaper_spectrogram
from neo.io import NeuralynxIO
import misc_functions
import math
import time
# get_ipython().run_line_magic('matplotlib', 'inline')
import csv
from datetime import datetime

class NeuralynxEphys(experiment.experiment):
    """This is the class definition for handling Neuralynx ephys data."""
    
    def importEphysData(self,channels='all',removeArtifacts=False, 
                        VThreshold=1500,TThreshold=60,plot=False,hannNum=75):
        """Import Neuralynx continuously sampled channel data and associated events.
        CHANNELS can be 'all', 'none' (if you just want to import the events),
        or a string or list of strings."""
        print('Importing ephys data...')
        start_time = time.time()
        self.ephysFilePath = misc_functions._findFilePaths(self.experiment['ephys directory'], fileExtensions='.nev', fileStartsWith='Events', removeFile=True)[0]
        self._recording = NeuralynxIO(self.ephysFilePath)
        self._ephysData = self._recording.read_block(signal_group_mode='split-all')
        self.samplingRate = {}
        self.tEphys = {}
        self.ephys = {}
        self.zeroTime = {}
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
                    # fact that .argmin() in self._makeEphysArrays() looks for the first
                    # occurance of the minimum when there is more than one candidate.
                    if (tStop - tStart) % dt <= (dt / 2):
                        tStop -= 0.51 * dt # subtract just over half of a dt to bump it down a time point
                    self.tEphys[c.name] = np.arange(tStart, tStop, dt)
                    self._makeEphysArrays(k)
                    # For each channel, after making the ephys arrays, find the element
                    # of the time vector closest to self.experiment['zero time (s)']
                    # and subtract the time at that element from the entire time array
                    # zeroIdx = (np.abs(self.tEphys[c.name] - self._analysisParamsDict['zero time (s)'])).argmin()
                    # self.zeroTime[c.name] = self.tEphys[c.name][zeroIdx]
                    # self.tEphys[c.name] -= self.zeroTime[c.name]
                    if removeArtifacts:
                        self.artifactRemoval(channel=c.name,VThreshold=VThreshold,
                                             TThreshold=TThreshold,plot=plot,hannNum=hannNum)
        print('--- %s seconds ---' % (time.time() - start_time))


    def _makeEphysArrays(self, chNum):
        """Method for concatenating ephys data and interpolating data between timestamp jumps.
        CHNUM is the channel number"""
        # Make a vector of NaNs equal in length to the time vector
        chName = self._ephysData.segments[0].analogsignals[chNum].name
        self.ephys[chName] = np.nan * np.ones(np.shape(self.tEphys[chName]))
        for seg in self._ephysData.segments:
            segSize = seg.analogsignals[chNum].size
            startIdx = (np.abs(self.tEphys[chName] - seg.t_start.magnitude)).argmin()
            # Interpolate the chunk between the last segment and the start of the current segment
            if seg.index > 0:
                interpStartIdx = np.where(np.isnan(self.ephys[chName]))[0][0]
                interpSegSize = startIdx-interpStartIdx
                self.ephys[chName][interpStartIdx:startIdx] = np.reshape(np.linspace(self.ephys[chName][interpStartIdx-1], seg.analogsignals[chNum][0].magnitude, interpSegSize+2)[1:-1], interpSegSize)
            # Add on the current segment
            self.ephys[chName][startIdx:(startIdx+segSize)] = np.reshape(seg.analogsignals[chNum].magnitude, segSize)


    def importNeuralynxEvents(self):
        """Method for importing Neuralynx events."""
        try:
            ephysLength = len(self.ephys)
        except AttributeError:
            self.importEphysData()
        finally:
            print('Importing ephys events...')
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
            self.NeuralynxEvents['timestamps'] = npUnsortedEventTimestamps[evSortInds] # - self.zeroTime[next(iter(self.zeroTime))]


    def importAgentAnalyzerData(self, filename='S5DataExport.csv'):
        """Method for importing agent analyzer (Datex-Ohmeda S/5) data that was recorded using VSCapture."""
        print('Importing agent analyzer data...')
        filepath = self.experiment['ephys directory'] + '/' + filename
        agentAnalyzerCSV = []
        with open(filepath, newline='', encoding='utf-8-sig') as s:
            reader = csv.reader(s)
            for row in reader:
                agentAnalyzerCSV.append(row)
                
        # Make a dictionary with each of the columns in the CSV file
        self.agentAnalyzer = {}
        for k, columnTitle in enumerate(agentAnalyzerCSV[0]):
            try:
                self.agentAnalyzer[columnTitle] = []
                if columnTitle == 'Time':
                    for h in range(1,len(agentAnalyzerCSV)):
                        tempDateTime = datetime.strptime(agentAnalyzerCSV[h][k], "%d-%m-%Y  %H:%M:%S")
                        self.agentAnalyzer[columnTitle].append(tempDateTime)
                    try:
                        self.NeuralynxEvents['labels'][np.where(np.char.find(self.NeuralynxEvents['labels'],'time')==0)[0]] #TODO make this into a function that pulls this time into the recording and finds the closest time to the start of the agent analyzer
                        self.agentAnalyzer[columnTitle]
                    except NameError:
                        break
                else:
                    for h in range(1,len(agentAnalyzerCSV)):
                        self.agentAnalyzer[columnTitle].append(agentAnalyzerCSV[h][k])
                    if (columnTitle == 'AA_FI') or (columnTitle == 'O2_FI'):
                        self.agentAnalyzer[columnTitle] = np.array(self.agentAnalyzer[columnTitle], dtype=float)
            except:
                break

        
    def computeSpectrogram(self, channel='PFCLFPvsCBEEG', windowLength=30, windowStep=3, freqLims=[0,50], timeBandwidth=2, plotSpectrogram=True, plotEvents=False):
        """Estimate (and plot) the multi-taper spectrogram of a specified ephys channel. Developed with Mike Prerau's function."""
        print('Computing spectrogram...')
        # Set spectrogram params
        fs = int(self.samplingRate[channel])
        numTapers = timeBandwidth * 2 - 1
        windowParams = [windowLength, windowStep]
        minNfft = 0  # No minimum nfft
        detrendOpt = 'constant'  # detrend each window by subtracting the average
        multiprocess = True  # use multiprocessing
        nJobs = 3  # use 3 cores in multiprocessing
        weighting = 'unity'  # weight each taper at 1
        plotOn = False  # plot spectrogram using multitaper_spectrogram()
        returnFig = False  # do not return plotted spectrogram
        climScale = False # do not auto-scale colormap
        verbose = True  # print extra info
        xyflip = False  # do not transpose spect output matrix
        
        # Compute the multitaper spectrogram and convert the output to decibels
        PSDSpect, self.tSpect, self.freqsSpect = multitaper_spectrogram(self.ephys[channel], fs, freqLims, timeBandwidth, numTapers, windowParams, minNfft, detrendOpt, multiprocess, nJobs, weighting, plotOn, returnFig, climScale, verbose, xyflip)
        self.pSpect = 10 * np.log10(PSDSpect)
        
        # Plot the multitaper spectrogram
        if plotSpectrogram:
            h, ax = misc_functions.spectrogram(self.tSpect/60, self.freqsSpect, self.pSpect, xLabel='Time (min)')
            if plotEvents:
                misc_functions.markEvents(ax, self.NeuralynxEvents['timestamps']/60)
            return h, ax
    


    def computePhase(self, channel='PFCLFPvsCBEEG', data=None):
        """Compute the instantaneous phase of a specified ephys channel."""
        print('Computing instantaneous phase...')
        if data is None:
            data = self.ephys[channel]
        try:
            lengthInstantaneousPhaseEphys = len(self.instantaneousPhaseEphys)
        except:
            self.instantaneousPhaseEphys = {}
        finally:
            analyticSignalEphys = hilbert(data)
            self.instantaneousPhaseEphys[channel] = np.angle(analyticSignalEphys)
    
    
    def artifactRemoval(self, channel='PFCLFPvsCBEEG', VThreshold=1500, TThreshold=60, 
                        plot=True, hannNum=75): 
        """artifactRemoval is a 2 x L matrix with the beginning and end times 
        (in seconds) that shoulb be removed from the raw signal.
        VThreshold= voltage threshold
        TThreshold= time threshold, in (s) if the gap time between threshold crossing is less than TThresh, all the voltage in between them will also be converted to 0"""
        print("Removing artifacts...")
        try:
            ephysLength = len(self.ephys[channel])
        except NameError:
            self.importEphysData(channels=channel)
        finally:
            dt = self.tEphys[channel][1]-self.tEphys[channel][0]
            mean = np.mean(self.ephys[channel]) 
            meanCalcVect = np.vectorize(misc_functions._calcNumMinusMean)
            self.ephys[channel] = meanCalcVect(self.ephys[channel],mean)
    
            # implement thresholding
            
            compVThreshVect = np.vectorize(misc_functions._compVThresh)
            decimateMask = compVThreshVect(self.ephys[channel],VThreshold)
        
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
                
                if np.size(self.ephys[channel]) >= plusH:
                    if minusH > 0:
                        self.ephys[channel][minusH: plusH] = np.multiply(self.ephys[channel][minusH: plusH], invHan) 
                    else:
                        self.ephys[channel][0: plusH] = np.multiply(self.ephys[channel][0: plusH], invHan[(halfHan - decLocs + 1):])
                else:
                    sizeEphysmod = np.size(self.ephys[channel][minusH:])
                    self.ephys[channel][minusH:] = np.multiply(self.ephys[channel][minusH:], invHan[0: sizeEphysmod]) 
    
            if plot:
                print('Plotting ' + channel + '...')
                plt.figure()
                plt.plot(self.ephys[channel])
                plt.title('{0}'.format(channel))
                plt.xlabel('Time(s)')
                plt.ylabel('Voltage(\u03BC'+'V)')


    class filteredEphys():
        """This is an empty class in which to store filtering properties and filtered data."""
        pass


    def filterEphys(self, n=2, cut=[0.5,4], channel='PFCLFPvsCBEEG', ftype='butter', btype='bandpass', inline=False):
        """Method for filtering the ephys channel of choice with either a Butterworth or FIR filter."""
        print('Filtering ' + channel + ' with a(n) ' + ftype + ' filter ...')
        fdata = self.filteredEphys()
        try:
            ephysLength = len(self.ephys[channel])
        except NameError:
            self.importEphysData(channels=channel)
        finally:
            fdata.data = misc_functions.filterData(self.ephys[channel], n=n, cut=cut, ftype=ftype, btype=btype, fs=self.samplingRate[channel])
            
            if inline:
                self.ephys[channel] = fdata.data
            else:
                fdata.channel = channel
                fdata.cutoff = cut
                fdata.ftype = ftype
                fdata.btype = btype
                fdata.order = n
                
                try:
                    self.fdata.append(fdata)
                except AttributeError:
                    self.fdata = []
                    self.fdata.append(fdata)