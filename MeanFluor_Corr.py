### testing
"""
Created on Fri June 9 9:00:00 2023

@author: Rachael Fisher 

This script is used to crop within lens and find average fluorescence and compare with Ephys data, correlation and cross correlation metrics.
Forloop, No graphs, dataframe result
"""

from scipy.signal import correlate, correlation_lags, coherence
import pandas as pd
from scipy.stats import pearsonr
import miniscope_ephys
import matplotlib.pyplot as plt
import numpy as np
import misc_functions

df_centered = pd.DataFrame(columns=['experiment', 'rat', 'drug', 'MPE', 'MPELag', 'MNE', 'MNELag', 'MPC', 'MPCLag', 'MNC', 'MNCLag', 'expR', 'expP', 'conR', 'conP'])
nonTg = [35,37,38,83,90,92,36,43,44,86,39,42,45,85,40,41,48,87,46,47,64,88]
#nonTg = [35,37,38,83,90,92,36,43,44,86,99, 103, 39,42,45,85, 95,96,40,41,48,87,93,94,46,47,64,88,97,101]
Tg = [53,54,67,70,58,66,72,76,56,60,74,75,57,63,69,73,62,65,80]

for i in nonTg: 
    lineNum = i
    channel = 'PFCLFPvsCBEEG'
    
    obj = miniscope_ephys.miniscopeEphys(lineNum)
    fr = obj.experiment['frameRate']
    obj.importEphysData(channels=[channel])
    obj.importNeuralynxEvents(analogSignalImported=True)
    obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj.findEphysIdxOfTTLEvents(channel=channel, CaEvents=False)
    
    drug = obj.experiment['systemic drug']
    rat = obj.experiment['animalID']
    
    meanFluorescence = np.load('/home/lab/Desktop/Correlation Project/npzFiles/meanFluorescence_'+ str(lineNum)+ '.npz')
    
    fdataM = misc_functions.filterData(meanFluorescence['meanFluorescence'], n=2, cut=[1,3], ftype='butter', btype='bandpass', fs=fr)
    obj.filterEphys(channel=channel, n=2, cut=[1,3], ftype='butter', inline=False)
    
    # Times (s) to analyze based on the ephys spectrogram
    begin = obj._analysisParamsDict['periods of high slow wave power (s)'][0]
    end = obj._analysisParamsDict['periods of high slow wave power (s)'][1]
    beginControl = obj._analysisParamsDict['control periods (s)'][0]
    endControl = obj._analysisParamsDict['control periods (s)'][1]
    
    start = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>begin)[0][0]
    stop = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>end)[0][0]
    startControl = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>beginControl)[0][0]
    stopControl = np.where(obj.tEphys[channel][obj.ephysIdxAllTTLEvents]>endControl)[0][0]
    
    ephys = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][start:stop]
    minis = fdataM[start:stop]
    ephysControl = obj.fdata[0].data[obj.ephysIdxAllTTLEvents][startControl:stopControl]
    minisControl = fdataM[startControl:stopControl]
    
    # Calculate and plot the normalized cross-correlation
    nminis = minis/np.std(minis)
    nminis_centered = nminis - np.average(nminis)
    nephys = ephys/np.std(ephys)
    nephys_centered = nephys - np.average(nephys)
    nxcorr = correlate(nminis_centered, nephys_centered) / nminis_centered.size
    nxcorrLags = correlation_lags(nminis_centered.size, nephys_centered.size) / fr
    nlag = nxcorrLags[np.argmax(nxcorr)]
    
    extremes = [np.max(nxcorr),np.min(nxcorr)]
    extremesTimestamps = [nxcorrLags[np.argmax(nxcorr)],nxcorrLags[np.argmin(nxcorr)]]
    
    if np.max(nxcorr) >= abs(np.min(nxcorr)):
         xlimitLeft = nxcorrLags[np.argmax(nxcorr)] - 2
         xlimitRight = nxcorrLags[np.argmax(nxcorr)] + 2
         print('The maximum normalized cross correlation of for the experimental period is ' + str(np.max(nxcorr)) + ' at time ' +  str(nxcorrLags[np.argmax(nxcorr)]) + ' seconds')
    else:
         xlimitLeft = nxcorrLags[np.argmin(nxcorr)] - 2
         xlimitRight = nxcorrLags[np.argmin(nxcorr)] + 2
         print('The minimum normalized cross correlation of for the experimental period is ' + str(np.min(nxcorr)) + ' at time ' +  str(nxcorrLags[np.argmin(nxcorr)])+ ' seconds')
    
    nminisControl = minisControl/np.std(minisControl)
    nminisControlCentered = nminisControl - (np.average(nminisControl))
    nephysControl = ephysControl/np.std(ephysControl)
    nephysControlCentered = nephysControl - (np.average(nephysControl))
    nxcorrControl = correlate(nminisControlCentered, nephysControlCentered) / nminisControlCentered.size
    nxcorrLagsControl = correlation_lags(nminisControlCentered.size, nephysControlCentered.size) / fr
    nlagControl = nxcorrLagsControl[np.argmax(nxcorrControl)]
    
    extremesCon = [np.max(nxcorrControl),np.min(nxcorrControl)]
    extremesTimestampsCon  = [nxcorrLagsControl[np.argmax(nxcorrControl)],nxcorrLagsControl[np.argmin(nxcorrControl)]]
    
    nacorrMinis = correlate(nminis_centered, nminis_centered) / nminis_centered.size
    nacorrLagsMinis = correlation_lags(nminis_centered.size, nminis_centered.size) / fr
    nlag = nacorrLagsMinis[np.argmax(nacorrMinis)]
    
    nacorrMinisControl = correlate(nminisControlCentered, nminisControlCentered) / nminisControlCentered.size
    nacorrLagsMinisControl = correlation_lags(nminisControlCentered.size, nminisControlCentered.size) / fr
    nlagMinisControl = nacorrLagsMinisControl[np.argmax(nacorrMinisControl)]
    
    nacorrEphys = correlate(nephys_centered, nephys_centered) / nephys_centered.size
    nacorrLagsEphys = correlation_lags(nephys_centered.size, nephys_centered.size) / fr
    nlagEphys = nacorrLagsEphys[np.argmax(nacorrEphys)]
    
    nacorrEphysControl = correlate(nephysControlCentered, nephysControlCentered) / nephysControlCentered.size
    nacorrLagsEphysControl = correlation_lags(nephysControlCentered.size, nephysControlCentered.size) / fr
    nlagEphysControl = nacorrLagsEphysControl[np.argmax(nacorrEphysControl)]
    
    R1,P1 = pearsonr(nminis_centered, nephys_centered)
    
    R2,P2 = pearsonr(nminisControlCentered, nephysControlCentered)
    
    data = [lineNum, rat, drug, extremes[0], extremesTimestamps[0], extremes[1], extremesTimestamps[1], extremesCon[0], extremesTimestampsCon[0], extremesCon[1], extremesTimestampsCon[1], R1, P1, R2, P2]
    
    df_centered.loc[ len(df_centered) ] = data