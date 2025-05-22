import sys
import numpy as np

from src2.ephys.channel import Channel
from src2.ephys.ephys_data_manager import EphysDataManager


def syncNeuralynxMiniscopeTimestamps(channel: Channel, miniscope_dm: EphysDataManager, deleteTTLs=True, fixTTLGaps=False, onlyExperimentEvents=True):
    print('Syncing calcium movie times...')
    frameAcqIdx = (channel.events['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).') | (channel.events['labels'] == 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0001).')
    tCaIm = channel.events['timestamps'][frameAcqIdx]

    lowConfidencePeriods = np.empty((0,2))
    tCaIm, lowConfidencePeriods, miniscope_dm = _correcttCaIm(channel.events['labels'][frameAcqIdx], tCaIm, lowConfidencePeriods=lowConfidencePeriods, fixTTLGaps=fixTTLGaps)

        # make an array of the Neuralynx events with the TTL events removed
    if onlyExperimentEvents:
        experimentEventIdx = np.invert(frameAcqIdx)
        channel.events['labels'] = channel.events['labels'][experimentEventIdx]
        channel.events['timestamps'] = channel.events['timestamps'][experimentEventIdx]
    
    # delete the TTL events that correspond to dropped frames in the saved calcium movie, specified in analysis_parameters.csv. This currently assumes that any gaps in the TTL events have been corrected already.
    #TODO Add a method that plots the 3 figures of the timestamps for help in deciding which events to drop, then writes to analysis_parameters.csv and self._analysisParamsDict['indices of TTL events to delete'].
    if deleteTTLs:
        tCaIm = np.delete(tCaIm, miniscope_dm.analysis_params['indices of TTL events to delete'])

    return tCaIm, lowConfidencePeriods, channel, miniscope_dm



        


def _correcttCaIm(eventLabels, tCaIm, lowConfidencePeriods, miniscope_dm, threshold=0.065, fixTTLGaps=False):
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
    
    print('Finding any gaps in the TTL events...')
    dtCaIm = np.diff(tCaIm)
    idxTTLGap = np.where(dtCaIm > threshold)[0] # indices of gaps in the TTL events
    if len(idxTTLGap) == 0:
        print('No gaps were found with a threshold of ' + str(threshold*1000) + ' ms.')
    elif fixTTLGaps:
        print('Fixing any gaps in the TTL events...')
        flippedIdxTTLGap = np.flip(idxTTLGap) # Reverse the order of idxTTLGap so that inserting TTLs in the loop doesn't affect the indices of the next iteration of the loop.
        gapLength = [] # number dropped frames per index
        for k, gapIdx in enumerate(flippedIdxTTLGap):
            gapLength.append(round(dtCaIm[gapIdx]/(1/miniscope_dm.metadata['frameRate']))) # Guesses how many timesteps occur in the gap. E.g., a 30 Hz video with a gap of 67 ms will have 2 timesteps in the gap.
            print(str(gapLength[k]-1) + ' TTL event(s) is/are missing between index numbers ' + str(gapIdx) + ' and ' + str(gapIdx + 1) + '.')
            estimatedEventTimes = np.linspace(tCaIm[gapIdx], tCaIm[gapIdx+1], gapLength[k]+1) # Estimates the timing of the TTLs, beginning at the one before the gap and ending at the one after the gap.
            tCaIm = np.insert(tCaIm, gapIdx+1, estimatedEventTimes[1:-1])
            lowConfidencePeriods = np.append(lowConfidencePeriods, [[gapIdx, gapIdx+gapLength[k]]], axis=0)
    else:
        print('Gaps were found. Review self.tCaIm before proceeding.')
        sys.exit() # Exit program execution if this condition is reached.

    return tCaIm, lowConfidencePeriods, miniscope_dm


def findEphysIdxOfTTLEvents(self, channel='PFCLFPvsCBEEG', allTTLEvents=True, CaEvents=False, fixTTLGaps=False):
    """Finds the index of a calcium event in the Neuralynx timespace. If the miniscope class method to find the timing of calcium events has not been run yet, it runs that first.
    CHANNEL is the ephys channel with which to compare the timing of the ephys samples to the calcium event timing."""
    # Match up all calcium movie timestamps with their corresponding ephys timestamps.
    if allTTLEvents:
        try:
            tCaImLength = len(self.tCaIm)
        except AttributeError:
            self.syncNeuralynxMiniscopeTimestamps(channel=channel, fixTTLGaps=fixTTLGaps)
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


def findCaMovieNums(self, timeRange=None, channel='PFCLFPvsCBEEG', filenameEndsWith='', fixTTLGaps=False):
    """Determine the calcium imaging movie file(s) that correspond to a specified time period (in seconds) in the electrophysiological signal. Set SELF.MOVIEFILEPATHS to these movies' paths.
    TIMERANGE is a list specifing the boundaries of the time period.
    FILENAMEENDSWITH specifies any appended characters to the filenames, such as '_cropped'."""
    if timeRange == None:
        timeSecStart = self._analysisParamsDict['periods of high slow wave power (s)'][0]
        timeSecEnd = self._analysisParamsDict['periods of high slow wave power (s)'][-1]
    else:
        timeSecStart = timeRange[0]
        timeSecEnd = timeRange[1]

    try:
        lenEphysIdxAllTTLEvents = len(self.ephysIdxAllTTLEvents)
    except:
        self.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False, fixTTLGaps=fixTTLGaps)
    finally:
        print('Finding the miniscope frames and movie corresponding to the specified time period...')
        self.movieFrames = np.zeros(2, dtype=int)
        self.movieFrames[0] = np.where(self.tEphys[channel][self.ephysIdxAllTTLEvents]>=timeSecStart)[0][0] # Start frame
        self.movieFrames[1] = np.where(self.tEphys[channel][self.ephysIdxAllTTLEvents]<=timeSecEnd)[0][-1] # End frame
        firstMovie = int(self.movieFrames[0]/self.experiment['framesPerFile']) # Truncates result to just the integer part
        lastMovie = int(self.movieFrames[1]/self.experiment['framesPerFile']) # Truncates result to just the integer part

        print('The first movie in the sequence is ' + str(firstMovie) + '.avi.')
        print('The last movie in the sequence is ' + str(lastMovie) + '.avi.')
        
        movieRange = tuple([str(x) + filenameEndsWith + '.' for x in range(firstMovie, lastMovie+1)])
        self.findMovieFilePaths(fileStartsWith=movieRange)