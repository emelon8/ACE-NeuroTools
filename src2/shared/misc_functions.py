# -*- coding: utf-8 -*-
"""
Created on Wed Sep  9 18:44:28 2020

Miscellaneous functions

@author: eric

This file contains funcitons that are not tied to a single type of data
analysis.
"""

import numpy as np
import math
import matplotlib.pyplot as plt

plt.rcParams['svg.fonttype'] = 'none'
import os
import pickle
import cv2
from tqdm import tqdm
from scipy.signal import butter, freqz, filtfilt, firwin, bode
from IPython.display import clear_output
import os.path
from os import path
from matplotlib import pyplot as plt
import csv
from scipy import stats
from src2.shared.path_finder import PathFinder


def _prep_axes(title='', xLabel='', yLabel='', subPlots=None):
    """
    Prepare figure and axis/axes for plotting. Returns the figure handle and either the axis handle or a list of axes handles.
    TITLE is the title of the axis or list of titles (in order) for the axes.
    XLABEL is the xlabel of the axis or list of xlabels (in order) for the axes.
    YLABEL is the ylabel of the axis or list of ylabels (in order) for the axes.
    SUBPLOTS is a list to prepare the subplot axes: [number of rows, number of columns].
    The elements in TITLE, XLABEL, and YLABEL label the plots first from left to right, then from top to bottom.
    """
    if isinstance(xLabel, list) and isinstance(yLabel, list):
        if len(xLabel) > len(yLabel):
            while len(xLabel) is not len(yLabel):
                yLabel.append('')
        if len(yLabel) > len(xLabel):
            while len(xLabel) is not len(yLabel):
                xLabel.append('')
    elif isinstance(xLabel, list) and isinstance(yLabel, str):
        yLabel.append('')
        while len(xLabel) is not len(yLabel):
            yLabel.append('')
    elif isinstance(xLabel, str) and isinstance(yLabel, list):
        xLabel.append('')
        while len(xLabel) is not len(yLabel):
            xLabel.append('')

    h = plt.figure()
    # h.set_layout_engine('constrained')
    if subPlots is None:
        ax = h.add_subplot()
        ax.set_title(title)
        ax.set_xlabel(xLabel)
        ax.set_ylabel(yLabel)
    else:
        ax = []
        if type(title) is str:
            title = [title] * (subPlots[0] * subPlots[1])
        if type(xLabel) is str:
            xLabel = [xLabel] * (subPlots[0] * subPlots[1])
        if type(yLabel) is str:
            yLabel = [yLabel] * (subPlots[0] * subPlots[1])
        for k in range(subPlots[0] * subPlots[1]):
            ax.append(h.add_subplot(subPlots[0], subPlots[1], k + 1))
            if k <= len(title):
                ax[k].set_title(title[k])
            if k <= len(xLabel):
                ax[k].set_xlabel(xLabel[k])
            if k <= len(yLabel):
                ax[k].set_ylabel(yLabel[k])
    h.tight_layout() # incompatible with the 'constrained' layout engine
    return h, ax


def spectrogram(tVec, freqVec, specData, cBarPercentLims=[5., 95.], xLabel='Time (s)', yLabel='Frequency (Hz)',
                cLabel='Power (dB)'):
    """
    Plots a spectrogram that has already been computed.
    TVEC is a vector of the x-axis time points or a time vector consisting of just [min, max].
    FREQVEC is a vector of the y-axis frequency points, or a frequency vector consisting of just [min, max].
    SPECDATA is the matrix of spectral power.
    CBARPERCENTLIMS sets the bounds on the color bar by finding the specified percentages of the power in specData.
    """
    h, ax = _prep_axes(xLabel=xLabel, yLabel=yLabel)
    cBarMin = np.percentile(specData, cBarPercentLims[0])
    cBarMax = np.percentile(specData, cBarPercentLims[1])
    spectrogramPlot = ax.imshow(specData, interpolation='none', extent=[tVec[0], tVec[-1], freqVec[0], freqVec[-1]],
                                aspect='auto', vmin=cBarMin, vmax=cBarMax, origin='lower')
    cbar = h.colorbar(spectrogramPlot, ax=ax)
    cbar.set_label(cLabel)
    return h, ax


def mark_events(axisHandle, eventTimes):
    """Draw vertical event markers on a plot at specified times.
    
    Args:
        axisHandle: Matplotlib axis to draw on.
        eventTimes: Single time or list of times to mark.
    """
    # Mark Neuralynx events on a given plot
    yLimits = axisHandle.get_ylim()
    xLimits = axisHandle.get_xlim()
    lineLength = np.diff(yLimits)
    lineOffset = yLimits[0] + (lineLength / 2)
    if type(eventTimes) != list:
        eventTimes = [eventTimes]
    axisHandle.eventplot(eventTimes, lineoffsets=lineOffset, linelengths=lineLength, colors='k')
    axisHandle.axis([xLimits[0], xLimits[1], yLimits[0], yLimits[1]])


def _find_file_paths(directory=None, fileExtensions=None, fileStartsWith=None,
                   removeFile=False, printPath=False, fileAndDirectory=False):
    """Find file paths matching extension and prefix criteria.
    
    Makes a list of the full paths of all files of type fileExtensions in
    directory, sorted by last modification time.
    
    Args:
        directory: Directory to search.
        fileExtensions: String or list of file extensions to match.
        fileStartsWith: String or tuple of filename prefixes to include.
        removeFile: If True, return folder path instead of file path.
        printPath: If True, print found paths.
        fileAndDirectory: If True, return tuple of (files, directories).
        
    Returns:
        Sorted list of matching file paths, or tuple if fileAndDirectory=True.
    """

    if (fileExtensions == None and fileStartsWith == None):
        raise AttributeError('Not enough information to determine path')

    if printPath:
        print('Finding file path...')
        print('directory=' + str(directory))
        print('fileExtensions=' + str(fileExtensions))
        print('fileStartsWith=' + str(fileStartsWith))
    if fileExtensions != None:
        if type(fileExtensions) is str:
            fileExtensionsTuple = (fileExtensions,)
        else:
            fileExtensionsTuple = tuple(fileExtensions)
    else:
        fileExtensionsTuple = None
    if fileStartsWith != None:
        if type(fileStartsWith) is str:
            fileStartsWith = (fileStartsWith,)
        else:
            fileStartsWith = tuple(fileStartsWith)
    filePaths = []
    fileDirectory = []

    for root, dirs, files in os.walk(directory):
        for file1 in files:
            if fileExtensionsTuple != None:
                if file1.endswith(fileExtensionsTuple):
                    if fileStartsWith == None:
                        if removeFile:
                            filePaths.append(os.path.join(root))
                        elif fileAndDirectory:
                            filePaths.append(os.path.join(root, file1))
                            fileDirectory.append(os.path.join(root))
                        else:
                            filePaths.append(os.path.join(root, file1))
                    elif file1.startswith(fileStartsWith):
                        if removeFile:
                            filePaths.append(os.path.join(root))
                        elif fileAndDirectory:
                            filePaths.append(os.path.join(root, file1))
                            fileDirectory.append(os.path.join(root))
                        else:
                            filePaths.append(os.path.join(root, file1))
            else:
                if file1.startswith(fileStartsWith):
                    if removeFile:
                        filePaths.append(os.path.join(root))
                    elif fileAndDirectory:
                        filePaths.append(os.path.join(root, file1))
                        fileDirectory.append(os.path.join(root))
                    else:
                        filePaths.append(os.path.join(root, file1))

    if filePaths == []:
        raise AttributeError('No path found')
    if printPath:
        print('filePaths=' + str(filePaths))
    if fileAndDirectory:
        return (sorted(set(filePaths), key=os.path.getmtime), sorted(set(fileDirectory), key=os.path.getmtime))
    else:
        return sorted(set(filePaths), key=os.path.getmtime)


def load_obj(filename):
    """Load a pickled object from disk.
    
    Useful for loading previously saved class instances.
    
    Args:
        filename: Path to the pickle file.
        
    Returns:
        The unpickled Python object.
    """
    fileToRead = open(filename, 'rb')
    loadedObject = pickle.load(fileToRead)
    fileToRead.close()
    return loadedObject


def _create_vignette_mask(rows, cols):
    """Create a Gaussian vignette mask for edge weighting.
    
    Args:
        rows: Frame height.
        cols: Frame width.
        
    Returns:
        2D vignette mask array.
    """
    X_kernel = cv2.getGaussianKernel(cols, cols / 4)
    Y_kernel = cv2.getGaussianKernel(rows, rows / 4)
    kernel = Y_kernel * X_kernel.T
    return 255 * kernel / np.linalg.norm(kernel)


def _compute_mean_fft(filePath, dataFilePrefix, startingFileNum, framesPerFile, frameStep,
                      applyVignette, showVideo):
    """Compute average FFT magnitude across all frames.
    
    Args:
        filePath: Directory containing video files.
        dataFilePrefix: Filename prefix before number.
        startingFileNum: First file number to process.
        framesPerFile: Frames per file.
        frameStep: Step size for sampling frames.
        applyVignette: Whether to apply vignette mask.
        showVideo: Display frames during processing.
        
    Returns:
        Tuple of (sumFFT, rows, cols, vignette_mask).
    """
    fileNum = startingFileNum
    sumFFT = None
    rows, cols = 0, 0
    vignette = None
    running = True

    while path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi") and running:
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        fileNum += 1
        
        for frameNum in tqdm(range(0, framesPerFile, frameStep), 
                             total=framesPerFile / frameStep,
                             desc=f"Computing FFT file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            if vignette is None:
                rows, cols = frame.shape[:2]
                vignette = _create_vignette_mask(rows, cols) if applyVignette else 1
            
            frame = frame[:, :, 1] * vignette
            dft = cv2.dft(np.float32(frame), flags=cv2.DFT_COMPLEX_OUTPUT)
            dft_shift = np.fft.fftshift(dft)
            magnitude = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])
            
            sumFFT = magnitude if sumFFT is None else sumFFT + magnitude
            
            if showVideo:
                cv2.imshow("Vid", frame / 255)
                if cv2.waitKey(10) & 0xFF == ord('q'):
                    running = False
                    break
                    
        cap.release()
    
    cv2.destroyAllWindows()
    return sumFFT, rows, cols, vignette


def _create_fft_mask(rows, cols, goodRadius, notchHalfWidth, centerHalfHeightToLeave):
    """Create FFT spatial frequency mask with center notch.
    
    Args:
        rows, cols: Frame dimensions.
        goodRadius: Radius for circular pass region.
        notchHalfWidth: Width of center notch filter.
        centerHalfHeightToLeave: Height of center pass band.
        
    Returns:
        2-channel FFT mask array.
    """
    crow, ccol = rows // 2, cols // 2
    maskFFT = np.zeros((rows, cols, 2), np.float32)
    cv2.circle(maskFFT, (crow, ccol), goodRadius, 1, thickness=-1)
    
    # Apply notch filter to remove horizontal bands
    maskFFT[(crow + centerHalfHeightToLeave):, (ccol - notchHalfWidth):(ccol + notchHalfWidth), 0] = 0
    maskFFT[:(crow - centerHalfHeightToLeave), (ccol - notchHalfWidth):(ccol + notchHalfWidth), 0] = 0
    maskFFT[:, :, 1] = maskFFT[:, :, 0]
    
    return maskFFT


def _preview_filtered_video(filePath, dataFilePrefix, startingFileNum, framesPerFile, 
                            frameStep, maskFFT):
    """Display side-by-side comparison of raw and filtered video.
    
    Args:
        filePath: Directory containing video files.
        dataFilePrefix: Filename prefix.
        startingFileNum: First file number.
        framesPerFile: Frames per file.
        frameStep: Frame sampling step.
        maskFFT: FFT filter mask.
    """
    fileNum = startingFileNum
    running = True

    while path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi") and running:
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        fileNum += 1
        
        for frameNum in tqdm(range(0, framesPerFile, frameStep),
                             total=framesPerFile / frameStep,
                             desc=f"Preview file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            frame = frame[:, :, 1]
            img_back = _apply_fft_filter(frame, maskFFT)
            
            im_diff = (128 + (frame - img_back) * 2)
            im_v = cv2.hconcat([frame, img_back, im_diff])
            cv2.imshow("Raw, Filtered, Difference", im_v / 255)
            
            if cv2.waitKey(10) & 0xFF == ord('q'):
                running = False
                break
                
        cap.release()
    
    cv2.destroyAllWindows()


def _apply_fft_filter(frame, maskFFT):
    """Apply FFT spatial filter to a single frame.
    
    Args:
        frame: 2D grayscale frame.
        maskFFT: FFT filter mask.
        
    Returns:
        Filtered frame as uint8.
    """
    dft = cv2.dft(np.float32(frame), flags=cv2.DFT_COMPLEX_OUTPUT | cv2.DFT_SCALE)
    dft_shift = np.fft.fftshift(dft)
    fshift = dft_shift * maskFFT
    f_ishift = np.fft.ifftshift(fshift)
    img_back = cv2.idft(f_ishift)
    img_back = cv2.magnitude(img_back[:, :, 0], img_back[:, :, 1])
    img_back[img_back > 255] = 255
    return np.uint8(img_back)


def _compute_mean_fluorescence(filePath, dataFilePrefix, startingFileNum, framesPerFile, maskFFT):
    """Calculate mean fluorescence per frame after FFT filtering.
    
    Args:
        filePath: Directory containing video files.
        dataFilePrefix: Filename prefix.
        startingFileNum: First file number.
        framesPerFile: Frames per file.
        maskFFT: FFT filter mask.
        
    Returns:
        Array of mean fluorescence values per frame.
    """
    fileNum = startingFileNum
    meanFrameList = []
    
    while path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi"):
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        fileNum += 1
        
        for frameNum in tqdm(range(0, framesPerFile, 1),  # Always step=1 for mean calculation
                             total=framesPerFile,
                             desc=f"Mean fluorescence file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            frame = frame[:, :, 1]
            dft = cv2.dft(np.float32(frame), flags=cv2.DFT_COMPLEX_OUTPUT | cv2.DFT_SCALE)
            dft_shift = np.fft.fftshift(dft)
            fshift = dft_shift * maskFFT
            f_ishift = np.fft.ifftshift(fshift)
            img_back = cv2.idft(f_ishift)
            img_back = cv2.magnitude(img_back[:, :, 0], img_back[:, :, 1])
            meanFrameList.append(img_back.mean())
            
        cap.release()
    
    return np.array(meanFrameList)


def _create_lowpass_filter(meanFrame, fs, cutoff, butterOrder):
    """Design and apply Butterworth lowpass filter to mean fluorescence.
    
    Args:
        meanFrame: Array of mean fluorescence values.
        fs: Sampling frequency.
        cutoff: Cutoff frequency.
        butterOrder: Filter order.
        
    Returns:
        Filtered mean fluorescence array.
    """
    b, a = butter(butterOrder, cutoff / (0.5 * fs), btype='low', analog=False)
    return filtfilt(b, a, meanFrame)


def _process_and_save_frames(filePath, dataFilePrefix, startingFileNum, framesPerFile,
                              maskFFT, meanFiltered, mode, compressionCodec, jobID,
                              rows, cols):
    """Apply filters and save/display final denoised frames.
    
    Args:
        filePath: Directory containing video files.
        dataFilePrefix: Filename prefix.
        startingFileNum: First file number.
        framesPerFile: Frames per file.
        maskFFT: FFT filter mask.
        meanFiltered: Lowpass-filtered mean fluorescence.
        mode: 'save' or 'display'.
        compressionCodec: Video codec string.
        jobID: Job identifier for output filenames.
        rows, cols: Frame dimensions.
    """
    frameStep = 1 if mode == 'save' else 10
    fileNum = startingFileNum
    frameCount = 0
    running = True
    
    codec = cv2.VideoWriter_fourcc(*compressionCodec)
    
    if mode == "save" and not path.exists(filePath + "Denoised"):
        os.mkdir(filePath + "Denoised")

    while path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi") and running:
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        writeFile = None
        
        if mode == "save":
            outPath = f"{filePath}Denoised/{jobID}{dataFilePrefix}denoised{fileNum:.0f}.avi"
            writeFile = cv2.VideoWriter(outPath, codec, 60, (cols, rows), isColor=False)

        fileNum += 1
        
        for frameNum in tqdm(range(0, framesPerFile, frameStep),
                             total=framesPerFile / frameStep,
                             desc=f"Processing file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
            
            frame = frame[:, :, 1]
            img_back = _apply_fft_filter(frame, maskFFT).astype(np.float32)
            
            # Apply temporal correction using mean fluorescence
            meanF = img_back.mean()
            img_back = img_back * (1 + (meanFiltered[frameCount] - meanF) / meanF)
            img_back[img_back > 255] = 255
            img_back = np.uint8(img_back)
            
            if mode == "save":
                writeFile.write(img_back)
            elif mode == "display":
                im_diff = (128 + (frame - img_back) * 2)
                im_v = cv2.hconcat([frame, img_back, im_diff])
                cv2.imshow("Cleaned video", im_v / 255)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    running = False
                    break
            
            frameCount += 1
        
        cap.release()
        if writeFile:
            writeFile.release()

    cv2.destroyAllWindows()


def denoise_movie(dataDir, dataFilePrefix='', showVideo=False, startingFileNum=0,
                  framesPerFile=1000, fs=30, frameStep=10, goodRadius=2000,
                  notchHalfWidth=3, centerHalfHeightToLeave=90, cutoff=3.0,
                  butterOrder=6, mode='display', compressionCodec='FFV1', jobID=''):
    """Remove horizontal bands and slow flicker from miniscope movies.
    
    Applies 2D FFT-based denoising to remove traveling horizontal bands and
    whole-image flicker artifacts. Based on Daniel Aharoni's denoising notebook:
    https://github.com/Aharoni-Lab/Miniscope-v4/tree/master/Miniscope-v4-Denoising-Notebook
    
    Args:
        dataDir: Directory containing movie files to denoise.
        dataFilePrefix: Prefix before file numbers (e.g., 'msCam' for 'msCam0.avi').
        showVideo: If True, display movie before analysis.
        startingFileNum: First file number to process; all subsequent files included.
        framesPerFile: Number of frames per file (set by Miniscope software).
        fs: Frame acquisition rate in Hz.
        frameStep: Step size for 2D FFT generation (skip frames to speed up).
        goodRadius: Radius parameter for FFT filtering.
        notchHalfWidth: Half-width of notch filter.
        centerHalfHeightToLeave: Half-height of pass frequencies in 2D FFT.
        cutoff: Cutoff frequency for filtering.
        butterOrder: Butterworth filter order (4-9 recommended to avoid artifacts).
        mode: 'save' to write output or 'display' to show denoised movie.
        compressionCodec: Video codec for saving ('FFV1' or 'GREY').
        jobID: Optional job identifier string.
    """
    difVideos = []
    
    if not isinstance(dataDir, list):
        dataDir = [dataDir]
    
    print(f"Processing directories: {dataDir}")
    
    for filePath in dataDir:
        # Skip already-denoised directories
        if 'Denoised' in filePath or (filePath + '\\Denoised') in dataDir:
            print(f"Skipping denoised directory: {filePath}")
            continue
        
        # Ensure path ends with /
        if filePath[-1] != "/":
            filePath = filePath + "/"
        print(f"Processing: {filePath}")
        
        # Step 1: Compute mean FFT across all frames
        sumFFT, rows, cols, vignette = _compute_mean_fft(
            filePath, dataFilePrefix, startingFileNum, framesPerFile, 
            frameStep, applyVignette=True, showVideo=showVideo
        )
        
        if sumFFT is None:
            print(f"No video files found in {filePath}")
            continue
        
        # Step 2: Create FFT spatial filter mask
        maskFFT = _create_fft_mask(rows, cols, goodRadius, notchHalfWidth, centerHalfHeightToLeave)
        
        # Step 3: Optional preview of filtered video
        if showVideo:
            _preview_filtered_video(filePath, dataFilePrefix, startingFileNum, 
                                   framesPerFile, frameStep, maskFFT)
        
        # Step 4: Calculate mean fluorescence per frame
        meanFrame = _compute_mean_fluorescence(filePath, dataFilePrefix, startingFileNum,
                                                framesPerFile, maskFFT)
        
        # Step 5: Apply temporal lowpass filter
        try:
            meanFiltered = _create_lowpass_filter(meanFrame, fs, cutoff, butterOrder)
        except (ValueError, RuntimeError) as e:
            print(f"ERROR filtering {filePath}: {e}")
            difVideos.append(filePath)
            continue
        
        # Step 6: Process and save/display final output
        _process_and_save_frames(filePath, dataFilePrefix, startingFileNum, framesPerFile,
                                  maskFFT, meanFiltered, mode, compressionCodec, jobID,
                                  rows, cols)
    
    if difVideos:
        print(f"ERRORS with: {difVideos}")
        print("Consider investigating")


def import_video_as_numpy_array(filename, frames='all', displayFrame=False, frameToDisplay=10):
    """Code stolen from https://stackoverflow.com/questions/42163058/how-to-turn-a-video-into-numpy-array and edited."""
    cap = cv2.VideoCapture(filename)
    frameCount = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frames != 'all':
        frameCount = frames
    buf = np.empty((frameCount, frameHeight, frameWidth, 3), np.dtype('uint8'))
    fc = 0
    ret = True
    while (fc < frameCount and ret):
        ret, buf[fc] = cap.read()
        fc += 1
    cap.release()
    if displayFrame:
        cv2.namedWindow('frame ' + str(frameToDisplay))
        cv2.imshow('frame ' + str(frameToDisplay), buf[frameToDisplay - 1])
    return buf


def quat_to_euler(qw, qx, qy, qz, degrees=False):
    """Convert quaternion to Euler angles (roll, pitch, yaw).
    
    Args:
        qw, qx, qy, qz: Quaternion components.
        degrees: If True, return angles in degrees; otherwise radians.
        
    Returns:
        List of [roll, pitch, yaw] angles.
    """
    m00 = 1.0 - 2.0 * qy * qy - 2.0 * qz * qz
    m01 = 2.0 * qx * qy + 2.0 * qz * qw
    m02 = 2.0 * qx * qz - 2.0 * qy * qw
    m10 = 2.0 * qx * qy - 2.0 * qz * qw
    m11 = 1 - 2.0 * qx * qx - 2.0 * qz * qz
    m12 = 2.0 * qy * qz + 2.0 * qx * qw
    m20 = 2.0 * qx * qz + 2.0 * qy * qw
    m21 = 2.0 * qy * qz - 2.0 * qx * qw
    m22 = 1.0 - 2.0 * qx * qx - 2.0 * qy * qy

    eulerAngles = []

    R = np.arctan2(m12, m22)  # Roll
    eulerAngles.append(R)
    c2 = np.sqrt(m00 * m00 + m01 * m01)
    P = np.arctan2(-m02, c2)  # Pitch
    eulerAngles.append(P)
    s1 = np.sin(R)
    c1 = np.cos(R)
    Y = np.arctan2(s1 * m20 - c1 * m10, c1 * m11 - s1 * m21)  # Yaw
    eulerAngles.append(Y)
    if degrees == True:
        eulerAngles = [math.degrees(R), math.degrees(P), math.degrees(Y)]
    return eulerAngles


def _conv_quat_to_euler(line):
    """Convert a CSV line of quaternion data to Euler angles.
    
    Args:
        line: List of [time, qw, qx, qy, qz].
        
    Returns:
        List of [time, roll, pitch, yaw].
    """
    if len(line) != 5:
        print('!!! ERROR: Invalid file')  # FIXME
        return
    time = line[0]
    qw = line[1]
    qx = line[2]
    qy = line[3]
    qz = line[4]
    eulerAngles = list(quat_to_euler(qw, qx, qy, qz, degrees=False))
    eulerAngles.insert(0, time)  # prepend time
    return eulerAngles


def _calc_num_minus_mean(num, mean):
    """Subtract mean from a number."""
    return (num - mean)


def _comp_v_thresh(num, VThresh):
    """Return 1 if abs(num) >= abs(VThresh), else 0."""
    x = int(abs(num) >= abs(VThresh))
    return x


def _find_step_index(conArray):
    """Find indices where step changes occur in an array."""
    x = np.diff(np.round(np.diff(conArray), 3))
    index = np.asarray(np.where(abs(x) > 1)[0]) + 1
    return index


def thresh_func(dataArray, threshVal):
    """Find indices where data crosses above a threshold.
    
    Args:
        dataArray: Input data array.
        threshVal: Threshold value.
        
    Returns:
        Array of indices where threshold crossings occur.
    """
    dataArray = np.where(dataArray >= threshVal, 1, 0)
    dataArray = np.argwhere(np.diff(dataArray) == 1)
    addArr = np.zeros(np.shape(dataArray))
    addArr[..., -1] = 1
    dataArray = dataArray + addArr
    return dataArray


def filter_data(data, n, cut, ftype, btype, fs, bodePlot=False):
    """ Use ftype to indicate FIR or Butterworth filter.
    
    For the FIR filter indicate a LowPass, HighPass, or BandPass with btype = lowpass, highpass, or bandpass, respectively. 
    n is the length of the filter (number of coefficients, i.e. the filter order + 1). numtaps must be odd if a passband includes the Nyquist frequency.
    A good value for n is 10000.
    Channel should be set to desired .ncs file
    
    The Butterworth filters have a more linear phase response in the pass-band than other types and is able to provide better group delay performance, and also a lower level of overshoot.
    Indicate the filter type by setting btype = 'low', 'high', or 'band'.
    The default for n is n = 2
    For a bandpass filter indicate the lowstop and the highstop by using an array. example: wn= ([10, 30])"""

    if ftype.lower() == 'fir':
        h = firwin(n, cut, pass_zero=btype, fs=fs)  # Build the FIR filter
        filteredData = filtfilt(h, 1, data)  # Zero-phase filter the data
        if bodePlot:
            w, a = freqz(h, worN=10000,fs=2000)
            plt.figure()
            plt.semilogx(w, abs(a))
            
            w, mag, phase = bode((h,1),w=2*np.pi*w)
            plt.figure()
            plt.semilogx(w,mag)
            plt.figure()
            plt.semilogx(w,phase)

    if ftype.lower() == 'butterworth' or ftype.lower() == 'butter':
        b, a = butter(n, cut, btype=btype, fs=fs)
        filteredData = filtfilt(b, a, data)
        
        if bodePlot:
            w, h = freqz(b, a, worN=10000,fs=2000)
            plt.figure()
            plt.semilogx(w, abs(h))
            
            w, mag, phase = bode((b,a),w=2*np.pi*w)
            plt.figure()
            plt.semilogx(w,mag)
            plt.figure()
            plt.semilogx(w,phase)

    return filteredData


def update_csv_cell(data, columnTitle, lineNum, csvFile):
    """Update a single cell in a CSV file.
    
    Args:
        data: New value to write.
        columnTitle: Column header name.
        lineNum: Line number to update.
        csvFile: Path to CSV file.
    """
    # get the correct column
    with open(csvFile) as file:
        reader = csv.DictReader(file)
        csvData = []
        for row in reader:
            csvData.append(row)
            if dict(row).get('line number') == str(lineNum):
                row[columnTitle] = str(data)

        with open(csvFile, 'w', newline='') as writeFile:
            writer = csv.DictWriter(writeFile, fieldnames=reader.fieldnames)
            writer.writeheader()
            for lineData in csvData:
                writer.writerow(lineData)


def append_row_csv(data, filename):
    """Appends a new row to a CSV file.
    Args:
        data: Dictionary of data to be added to the csv file
        filename: Name of the CSV file to write to.
    """
    if not os.path.exists(filename):
        with open(filename, 'a', newline='') as file:
            writer = csv.DictWriter(file, dict(data).keys())
            writer.writeheader()
            writer.writerow(dict(data))
    else:
        with open(filename, 'a', newline='') as file:
            writer = csv.DictWriter(file, dict(data).keys())
            writer.writerow(dict(data))


def spike_trig_avg(eventArray, dataArray, framesb, framesa):       
    """
    Compute the average spike values starting 'framesb' before the event
    and ending 'framesa' after the event.
    
    Args:
        eventArray: A numpy array of when and/or where events occur. Can either
                    be in the format of [[component, frame],...] or
                    [[frame],...]
        dataArray: A numpy array of the signal values at each frame
        framesb, framesa: the number of frames before and after the event that
                          that are to be included in the average spike
    Returns:
        avgEventDict: a dictionary dictionary where the keys represent the
                      component number from the dataArray and the value is
                      a numpy array of the average values at each frame
                      of the designated window around the event
    """
    avgEventDict = {}
    if dataArray.ndim == 1:
        for event in eventArray:
            if event[0]>=framesb and event[0]<=dataArray.size-framesa-1:
                if 0 in avgEventDict.keys():
                    avgEventDict[0] = np.add(avgEventDict[0], dataArray[int(event[0])-framesb:int(event[0])+framesa+1], dtype=object)
                else:
                    avgEventDict[0] = dataArray[int(event[0])-framesb:int(event[0])+framesa+1]
        avgEventDict[0] /= len(eventArray)
    else:
        for event in eventArray:
            if event[1]>=framesb and event[1]<=dataArray[0].size-framesa-1:
                if event[0] in avgEventDict.keys():
                    avgEventDict[int(event[0])] = np.add(avgEventDict[int(event[0])], dataArray[int(event[0])][int(event[1])-framesb:int(event[1])+framesa+1], dtype=object)
                else:
                    avgEventDict[int(event[0])] = dataArray[int(event[0])][int(event[1])-framesb:int(event[1])+framesa+1]
        for component in range(0,len(dataArray)):
            if component in avgEventDict.keys():
                avgEventDict[component] /= len(np.argwhere(eventArray==component))
    return avgEventDict


def z_score(dataArray, frameWindow = 1000):
    """
    Compute the z-score of the data array values every designated frame window
    length based on the values within that frame window
    
    Args:
        dataArray: A numpy array of values where the row represents the component
                   and the column represents the frame number
        frameWindow: An integer value that determines the length of the window
                     which the function z-scores across. Defaults to 1000 frames
    
    Returns:
        zScoreArray: A numpy array of the same shape as dataArray containing the 
                     z-score values of each frame
    """
    
    zScoreArray = np.ndarray(np.shape(dataArray))
    for i in range(0, int(dataArray[0].size/frameWindow)):
        if i*frameWindow < dataArray[0].size - frameWindow:
            zScoreArray[:][i*frameWindow:i*frameWindow+frameWindow] = stats.zscore(dataArray[:][i*frameWindow:i*frameWindow+frameWindow], axis=1)
            
        else:
            zScoreArray[:][i*frameWindow:] = stats.zscore(dataArray[:][i*frameWindow:], axis=1)
    zScoreArray = np.nan_to_num(zScoreArray)
    return zScoreArray


def get_coords_dict_from_analysis_params(miniscope_data_manager):
    """Extract crop coordinates from analysis parameters.
    
    Reads from the 'crop' column in analysis_parameters.csv.
    
    Args:
        miniscope_data_manager: Data manager with analysis_params.
        
    Returns:
        Tuple of (coords_dict, crop_job_name). coords_dict is None if
        no crop coordinates are found.
    """
    coords_dict = None
    crop_job_name = '_crop'
    try:
        previous_coords = miniscope_data_manager.analysis_params['crop']
        coords_dict = { 'x0': previous_coords[0], 'y0': previous_coords[1], 'x1': previous_coords[2], 'y1': previous_coords[3]}
    except KeyError:
        pass  # No saved coordinates; coords_dict stays None
    
    return coords_dict, crop_job_name
        
