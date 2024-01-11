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
import matplotlib.animation as animation
import misc_functions
import sys
import pandas as pd

class miniscopeEphys(ephys.NeuralynxEphys, miniscope.UCLAMiniscope):
    """This is the class definition for handling miniscopes and simultaneous ephys data."""
#%% Methods for importing experiment info, metadata, and analysis parameters
    def __init__(self, lineNum=None, filename='experiments.csv', filenameMiniscope='metaData.json', analysisFilename='analysis_parameters.csv', jobID=''):
        super().__init__(lineNum=lineNum, filename=filename, filenameMiniscope=filenameMiniscope, analysisFilename=analysisFilename, jobID=jobID) #FIXME Does this init statment need to be here? Will it inherit from ephys or miniscope if it's not?


#%% Methods for extracting timing of calcium image acquisition, deleting timestamps of dropped frames, and matching timestamps with ephys timestamps
    def syncNeuralynxMiniscopeTimestamps(self, channel='PFCLFPvsCBEEG', deleteTTLs=True, onlyExperimentEvents=True):
        """Create time vector for calcium movies from TTL events in Neuralynx."""
        try:
            eventsLength = len(self.NeuralynxEvents)
        except AttributeError:
            self.importNeuralynxEvents()
        finally:
            print('Syncing calcium movie times...')
            # create the self.tCaIm, which is the array of labels and timestamps for the Neuralynx events that occur for each calcium image frame acquisition
            frameAcqIdx = (self.NeuralynxEvents['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).') | (self.NeuralynxEvents['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0001).')
            self.tCaIm = self.NeuralynxEvents['timestamps'][frameAcqIdx]
            
            # Check for gaps in the TTL event timestamps and insert a timestamp guess if needed
            self.lowConfidencePeriods = np.empty((0,2))
            self._correcttCaIm(self.NeuralynxEvents['labels'][frameAcqIdx])
            
            # make an array of the Neuralynx events with the TTL events removed
            if onlyExperimentEvents:
                experimentEventIdx = np.invert(frameAcqIdx)
                self.NeuralynxEvents['labels'] = self.NeuralynxEvents['labels'][experimentEventIdx]
                self.NeuralynxEvents['timestamps'] = self.NeuralynxEvents['timestamps'][experimentEventIdx]
            
            # delete the TTL events that correspond to dropped frames in the saved calcium movie, specified in analysis_parameters.csv. This currently assumes that any gaps in the TTL events have been corrected already.
            #TODO Add a method that plots the 3 figures of the timestamps for help in deciding which events to drop, then writes to analysis_parameters.csv and self._analysisParamsDict['indices of TTL events to delete'].
            if deleteTTLs:
                self.tCaIm = np.delete(self.tCaIm, self._analysisParamsDict['indices of TTL events to delete'])


    def _correcttCaIm(self, eventLabels, threshold=0.06):
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
            self.tCaIm = np.insert(self.tCaIm, gapIdx+1, estimatedEventTimes[1:-1])
            self.lowConfidencePeriods = np.append(self.lowConfidencePeriods, [[gapIdx, gapIdx+gapLength[k]]], axis=0)


    def findEphysIdxOfTTLEvents(self, channel='PFCLFPvsCBEEG', allTTLEvents=True, CaEvents=False):
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


    def findCaMovieFrameNumOfEphysIdx(self, channel='PFCLFPvsCBEEG'): #TODO Make sure this method works correctly (e.g., it handles ephys indices before and after the start of the movie correctly), is placed in the most logical place in this file, and is fleshed out more.
        """Method to create an array the same size as obj.ephys[channel], where each element is the frame number of the corresponding calcium movie frame."""
        self.CaFrameNumOfEphysIdx = np.zeros(np.shape(self.ephys[channel]),dtype=int)

        # Assign a frame number to each element of self.CaFrameNumOfEphysIdx. I'm not sure if the sample of obj.ephys that's closest to the TTL event should be paired with the preceding frame or not.
        for k, i in enumerate(self.ephysIdxAllTTLEvents[1:]):
            self.CaFrameNumOfEphysIdx[i:self.ephysIdxAllTTLEvents[k]:-1] = k+1


#%% Methods to compare the mean fluorescence signal with the ephys signals
    def correlationMiniscopeEphys(self):
        """Compute the cross-correlation between the average miniscope fluorescence and a specified ephys signal."""
        pass
    
    
    def coherenceMiniscopeEphys(self):
        """Compute the coherence between the average miniscope fluorescence and a specified ephys signal."""
        pass


#%% Methods for visualizing the results
    def createCaEphysMovie(self, videoNum, channel='PFCLFPvsCBEEG', dFoverSqrtF=False, vmin=None, vmax=None, numFramesOfEphys=10, playbackInterval=33, playMovie=True, saveMovie=False):
        """Create a movie that has the ephys overlayed."""
        try:
            lenMovie = len(self.ephysIdxAllTTLEvents)
        except:
            self.findEphysIdxOfTTLEvents()
        finally:
            self.importCaMovies(str(videoNum) + '.avi')
            if dFoverSqrtF:
                self.computedFoverF(saveMovie=False)
            if vmin == None:
                vmin = self.movie.mean() - self.movie.std()*0
            if vmax == None:
                vmax = self.movie.mean() + self.movie.std()*4
    
            # Set up the plot
            fig, ax = plt.subplots(figsize=(5.4,5.4))
            plt.subplots_adjust(0,0,1,1)
    
            def update(frame):
                # Clear the plot
                ax.clear()
    
                # Plot the frame
                ax.imshow(np.flip(self.movie[frame], axis=0), vmin=vmin, vmax=vmax, cmap='gray')
    
                # Get the corresponding segment of the ephys recording
                frame += videoNum * self.experiment['framesPerFile']
                if frame > 0:
                    ephys_segment = self.ephys[channel][self.ephysIdxAllTTLEvents[frame-numFramesOfEphys]:self.ephysIdxAllTTLEvents[frame]]
                else:
                    ephys_segment = self.ephys[channel][self.ephysIdxAllTTLEvents[frame]-round(self.samplingRate[channel]/self.experiment['fr']):self.ephysIdxAllTTLEvents[frame]]
                ephys_segment = -np.flip(ephys_segment) # flip and invert signal so it is flipped and inverted again when the movie is written.
    
                # Plot the segment on top of the frame
                ax.plot(np.linspace(-0.5, self.movie.shape[2]-0.5, len(ephys_segment)), ephys_segment/5 + 508, color='red', linewidth=2)
                ax.set_xlim(-0.5, self.movie.shape[2]-0.5)
                ax.set_ylim(-0.5, self.movie.shape[1]-0.5)
                ax.set_axis_off()
    
            # Create the animation
            self.ani = animation.FuncAnimation(fig, update, frames=len(self.movie), interval=playbackInterval, repeat=False)
    
            # Display the animation
            if playMovie:
                plt.show()
    
            # Save the animation
            if saveMovie:
                if dFoverSqrtF:
                    self.ani.save(self.experiment['calcium imaging directory'] + '/Miniscope/' + str(videoNum) + '_CaIm_dFoverSqrtF_and_' + channel + '.mp4', dpi=300)
                else:
                    self.ani.save(self.experiment['calcium imaging directory'] + '/Miniscope/' + str(videoNum) + '_CaIm_and_' + channel + '.mp4', dpi=300)


#%% Methods to extract the instantaneous phase of the ephys signal, determine the phases of the calcium events, and summarize and save the results
    def ephysPhaseCaEvents(self, channel='PFCLFPvsCBEEG', neuron='all'):
        """Compare calcium events to the phase extracted from a specified ephys channel.
        CHANNEL is the ephys channel name.
        NEURON is the neuron number (i.e., the integer row number in self.estimates.C, starting with 0) of the neuron you want to compare. If you want to compare all of the neurons in the recording, pass 'all' as the argument."""
        try:
            ephysIdxCaEventsLength = len(self.ephysIdxCaEvents)
        except AttributeError:
            self.findEphysIdxOfTTLEvents(channel=channel, CaEvents=True)
        finally:
            self.computePhase(channel)
            print('Comparing the calcium events to the corresponding phase of ' + channel + '...')
            self.CaEventsPhasesEphys = {}
            if neuron == 'all':
                neurons = list(self.ephysIdxCaEvents.keys())
            elif type(neuron) != list:
                neurons = [neuron]
            for k in neurons:
                self.CaEventsPhasesEphys[k] = []
                for j in range(len(self.ephysIdxCaEvents[k])):
                    self.CaEventsPhasesEphys[k].append(self.instantaneousPhaseEphys[channel][self.ephysIdxCaEvents[k][j]])
                self.CaEventsPhasesEphys[k] = np.array(self.CaEventsPhasesEphys[k])


    def miniscopePhaseCaEvents(self, data=None, neuron='all'):
        """Compare calcium events to the phase extracted from the mean fluorescence of the (cropped) miniscope recording.
        DATA is the fluorescence signal.
        NEURON is the neuron number (i.e., the integer row number in self.estimates.C, starting with 0) of the neuron you want to compare. If you want to compare all of the neurons in the recording, pass 'all' as the argument."""
        try:
            ephysIdxCaEventsLength = len(self.ephysIdxCaEvents)
        except AttributeError:
            self.findEphysIdxOfTTLEvents(channel='PFCLFPvsCBEEG', CaEvents=True)
        finally:
            try:
                CaEventsIdxLength = len(self.CaEventsIdx)
            except AttributeError:
                self.findCalciumEvents()
            finally:
                self.computeMiniscopePhase(data=data)
                print('Comparing the calcium events to the corresponding phase of the mean fluorescence of the (cropped) miniscope recording...')
                self.CaEventsPhasesMiniscope = {}
                if neuron == 'all':
                    neurons = list(self.CaEventsIdx.keys())
                elif type(neuron) != list:
                    neurons = [neuron]
                for k in neurons:
                    self.CaEventsPhasesMiniscope[k] = []
                    for j in range(len(self.CaEventsIdx[k])):
                        self.CaEventsPhasesMiniscope[k].append(self.instantaneousPhaseMiniscope[self.CaEventsIdx[k][j]])
                    self.CaEventsPhasesMiniscope[k] = np.array(self.CaEventsPhasesMiniscope[k])


    def phaseCaEventsHistogram(self, channel=None, neuron='all', bins=18, histRange=(-np.pi,np.pi), density=False, meanDensity=True, plotHistogram=False, combined=False):
        """Compute the histogram of calcium events/probability density vs phase.
        CHANNEL is the channel to compare the timing of calcium events to.
        NEURON is a list of the neuron indexes to compare. All neurons can be selected with 'all'.
        BINS is the number of bins to sort the data into.
        HISTRANGE is a tuple of the range that the bins should cover.
        DENSITY determines whether the data will be bins will represent a probability density or a count.
        MEANDENSITY provides the mean of the density histograms of all specified neurons.
        PLOTHISTOGRAM chooses whether or not to plot the computed histogram.
        COMBINED is a boolean that determines whether to combine the data from all of the specified neurons or whether to create histograms for each of the specified neurons."""
        try:
            if channel is None:
                print('Creating a histogram of the phases of the mean fluorescence of the (cropped) miniscope recording relative to the calcium events...')
                lengthCaEventsPhases = len(self.CaEventsPhasesMiniscope)
            else:
                print('Creating a histogram of the phases of ' + channel + ' relative to the calcium events...')
                lengthCaEventsPhases = len(self.CaEventsPhasesEphys)
        except AttributeError:
            if channel is None:
                self.miniscopePhaseCaEvents(neuron)
            else:
                self.ephysPhaseCaEvents(channel, neuron)
        finally:
            if channel is None:
                CaEventsPhases = self.CaEventsPhasesMiniscope
            else:
                CaEventsPhases = self.CaEventsPhasesEphys
            if plotHistogram:
                if combined:
                    allCaEventsPhases = np.array([])
                    # Flatten the dictionary of numpy arrays so that all calcium events are contained in the same array
                    if neuron == 'all':
                        if density:
                            if meanDensity:
                                # Mean density histogram across neurons
                                CaEventsPhasesHist = np.empty((0, bins))
                                meanCaEventsVectors = np.empty((0, 2))
                                self.meanCaEventsVectorTheta = []
                                self.meanCaEventsVectorRadius = []
                                for i, k in enumerate(list(CaEventsPhases.keys())):
                                    hist, self.binEdges = np.histogram(CaEventsPhases[k], bins=bins, range=histRange, density=True)
                                    CaEventsPhasesHist = np.concatenate((CaEventsPhasesHist, hist.reshape((1,-1))), axis=0)
                                    # Find the mean vector for each neuron's calcium events
                                    CaEventsVectors = np.concatenate((np.cos(CaEventsPhases[k]).reshape((-1,1)), np.sin(CaEventsPhases[k]).reshape((-1,1))), axis=1)
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
                                CaEventsPhasesHist = list(CaEventsPhases.values())
                                h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(neuron))
                                self.hist, self.binEdges, _ = ax.hist(CaEventsPhasesHist, bins=bins, range=histRange, density=True, histtype='barstacked')
                        else:
                            for k in list(CaEventsPhases.keys()):
                                allCaEventsPhases = np.concatenate((allCaEventsPhases, CaEventsPhases[k]))
                            h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(neuron))
                            self.hist, self.binEdges, _ = ax.hist(allCaEventsPhases, bins=bins, range=histRange)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        if density:
                            CaEventsPhasesHist = {}
                            for k in neuron:
                                CaEventsPhasesHist[k] = CaEventsPhases[k]
                            # Barstacked density histogram across neurons
                            CaEventsPhasesHist = list(CaEventsPhases.values())
                            h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(neuron))
                            self.hist, self.binEdges, _ = ax.hist(CaEventsPhasesHist, bins=bins, range=histRange, density=True, histtype='barstacked')
                        else:
                            for k in neuron:
                                allCaEventsPhases = np.concatenate((allCaEventsPhases, CaEventsPhases[k]))
                            h, ax = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(neuron))
                            self.hist, self.binEdges, _ = ax.hist(allCaEventsPhases, bins=bins, range=histRange)
                else:
                    # Plot each of the neurons as separate histograms
                    ax = []
                    self.hist = {}
                    self.binEdges = {}
                    if neuron == 'all':
                        for i, k in enumerate(list(CaEventsPhases.keys())):
                            if density:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(k))
                            else:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(k))
                            ax.append(newAx)
                            self.hist[k], self.binEdges[k], _ = ax[i].hist(CaEventsPhases[k], bins=bins, range=histRange, density=density)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        for i, k in enumerate(neuron):
                            if density:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): '+str(k))
                            else:
                                newH, newAx = misc_functions._prepAxes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): '+str(k))
                            ax.append(newAx)
                            self.hist[k], self.binEdges[k], _ = ax[i].hist(CaEventsPhases[k], bins=bins, range=histRange, density=density)
            else:
                if combined:
                    allCaEventsPhases = np.array([])
                    # Flatten the dictionary of numpy arrays so that all calcium events are contained in the same array
                    if neuron == 'all':
                        for k in list(CaEventsPhases.keys()):
                            allCaEventsPhases = np.concatenate((allCaEventsPhases, CaEventsPhases[k]))
                        self.hist, self.binEdges = np.histogram(allCaEventsPhases, bins=bins, range=histRange, density=density)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        for k in neuron:
                            allCaEventsPhases = np.concatenate((allCaEventsPhases, CaEventsPhases[k]))
                        self.hist, self.binEdges = np.histogram(allCaEventsPhases, bins=bins, range=histRange, density=density)
                else:
                    # Plot each of the neurons as separate histograms
                    self.hist = {}
                    self.binEdges = {}
                    if neuron == 'all':
                        for k in list(CaEventsPhases.keys()):
                            self.hist[k], self.binEdges[k] = np.histogram(CaEventsPhases[k], bins=bins, range=histRange, density=density)
                    else:
                        if type(neuron) != list:
                            neuron = [neuron]
                        for k in neuron:
                            self.hist[k], self.binEdges[k] = np.histogram(CaEventsPhases[k], bins=bins, range=histRange, density=density)


    def phaseCaEventsPolarPlot(self, channel='PFCLFPvsCBEEG', neuron='all', bins=18, plotMeanVector=True):
        """"""
        plt.subplot() #TODO Figure out why misc_functions._prepAxes won't work with this method.
        self.hist


    def saveData(self, filename='neuron_phase.csv'):
        """Saves extracted phases of calcium events, along with neuron and rat IDs and other info, to a CSV file for further processing."""
        df = pd.read_csv("miniscope_Ephys_rats.csv", encoding="ISO-8859-1" )  #reading csv file
        for index, row in df.iterrows():   # filtering the rows where job is Govt
        	if self.experiment['id'] in row['Rat ID']:
        		sex = row['Sex']
        else:
            print("No such variable found")
        length = len(self.CaEventsPhasesEphys)
        list_data = {"Phase":self.CaEventsPhasesEphys, 'NeuronID':self.CaEventsNeurons, 'RatID':[self.experiment['id']] * length, 'Sex': [sex] * length, 'Condition':[self.experiment["systemic drug"]] * length}
        print('Saving calcium event phases and other attributes to ' + filename)
        misc_functions.appendRowCSV(list_data, filename=filename) #FIXME I haven't tested this yet.