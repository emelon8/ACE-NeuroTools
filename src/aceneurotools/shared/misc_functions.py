

import numpy as np
import math
import matplotlib.pyplot as plt
from typing import List, Optional, Union, Any, Tuple, Dict
from pathlib import Path

plt.rcParams['svg.fonttype'] = 'none'
import os
import pickle
import cv2
from tqdm import tqdm
from scipy.signal import butter, freqz, filtfilt, firwin, bode
import csv
from scipy import stats
from aceneurotools.shared.path_finder import PathFinder


def _prep_axes(
    title: Union[str, List[str]] = '', 
    xLabel: Union[str, List[str]] = '', 
    yLabel: Union[str, List[str]] = '', 
    subPlots: Optional[List[int]] = None
) -> Tuple[plt.Figure, Union[plt.Axes, List[plt.Axes]]]:
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
            while len(xLabel) != len(yLabel):
                yLabel.append('')
        if len(yLabel) > len(xLabel):
            while len(xLabel) != len(yLabel):
                xLabel.append('')
    elif isinstance(xLabel, list) and isinstance(yLabel, str):
        yLabel_list: List[str] = [yLabel]
        while len(xLabel) != len(yLabel_list):
            yLabel_list.append('')
        yLabel = yLabel_list
    elif isinstance(xLabel, str) and isinstance(yLabel, list):
        xLabel_list: List[str] = [xLabel]
        while len(xLabel_list) != len(yLabel):
            xLabel_list.append('')
        xLabel = xLabel_list

    h: plt.Figure = plt.figure()
    # h.set_layout_engine('constrained')
    if subPlots is None:
        ax: plt.Axes = h.add_subplot()
        ax.set_title(str(title))
        ax.set_xlabel(str(xLabel))
        ax.set_ylabel(str(yLabel))
    else:
        axes_list: List[plt.Axes] = []
        num_subplots: int = subPlots[0] * subPlots[1]
        
        final_titles: List[str] = [title] * num_subplots if isinstance(title, str) else title
        final_xlabels: List[str] = [xLabel] * num_subplots if isinstance(xLabel, str) else xLabel
        final_ylabels: List[str] = [yLabel] * num_subplots if isinstance(yLabel, str) else yLabel
        
        for k in range(num_subplots):
            axes_list.append(h.add_subplot(subPlots[0], subPlots[1], k + 1))
            if k < len(final_titles):
                axes_list[k].set_title(final_titles[k])
            if k < len(final_xlabels):
                axes_list[k].set_xlabel(final_xlabels[k])
            if k < len(final_ylabels):
                axes_list[k].set_ylabel(final_ylabels[k])
        h.tight_layout() # incompatible with the 'constrained' layout engine
        return h, axes_list
    h.tight_layout()
    return h, ax


def spectrogram(
    tVec: np.ndarray, 
    freqVec: np.ndarray, 
    specData: np.ndarray, 
    cBarPercentLims: List[float] = [5., 95.], 
    xLabel: str = 'Time (s)', 
    yLabel: str = 'Frequency (Hz)',
    cLabel: str = 'Power (dB)'
) -> Tuple[plt.Figure, plt.Axes]:
    """
    Plots a spectrogram that has already been computed.
    TVEC is a vector of the x-axis time points or a time vector consisting of just [min, max].
    FREQVEC is a vector of the y-axis frequency points, or a frequency vector consisting of just [min, max].
    SPECDATA is the matrix of spectral power.
    CBARPERCENTLIMS sets the bounds on the color bar by finding the specified percentages of the power in specData.
    """
    h, ax = _prep_axes(xLabel=xLabel, yLabel=yLabel)
    if isinstance(ax, list):
        ax = ax[0]
    
    cBarMin = np.percentile(specData, cBarPercentLims[0])
    cBarMax = np.percentile(specData, cBarPercentLims[1])
    spectrogramPlot = ax.imshow(specData, interpolation='none', extent=(tVec[0], tVec[-1], freqVec[0], freqVec[-1]),
                                aspect='auto', vmin=cBarMin, vmax=cBarMax, origin='lower')
    cbar = h.colorbar(spectrogramPlot, ax=ax)
    cbar.set_label(cLabel)
    return h, ax


def mark_events(axisHandle: plt.Axes, eventTimes: Union[float, List[float], np.ndarray]) -> None:
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
    if not isinstance(eventTimes, (list, np.ndarray)):
        eventPoints = [eventTimes]
    else:
        eventPoints = eventTimes
        
    axisHandle.eventplot(eventPoints, lineoffsets=float(lineOffset), linelengths=float(lineLength), colors='k')
    axisHandle.axis((xLimits[0], xLimits[1], yLimits[0], yLimits[1]))


def _find_file_paths(
    directory: Optional[Union[str, Path]] = None,
    fileExtensions: Optional[Union[str, List[str], Tuple[str, ...]]] = None, 
    fileStartsWith: Optional[Union[str, List[str], Tuple[str, ...]]] = None,
    removeFile: bool = False, 
    printPath: bool = False, 
    fileAndDirectory: bool = False
) -> Union[List[str], Tuple[List[str], List[str]]]:
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

    if (fileExtensions is None and fileStartsWith is None):
        raise AttributeError('Not enough information to determine path')

    if printPath:
        print('Finding file path...')
        print(f'directory={directory}')
        print(f'fileExtensions={fileExtensions}')
        print(f'fileStartsWith={fileStartsWith}')
    
    fileExtensionsTuple: Optional[Tuple[str, ...]] = None
    if fileExtensions is not None:
        if isinstance(fileExtensions, str):
            fileExtensionsTuple = (fileExtensions,)
        else:
            fileExtensionsTuple = tuple(fileExtensions)

    fileStartsWithTuple: Optional[Tuple[str, ...]] = None
    if fileStartsWith is not None:
        if isinstance(fileStartsWith, str):
            fileStartsWithTuple = (fileStartsWith,)
        else:
            fileStartsWithTuple = tuple(fileStartsWith)
            
    filePaths: List[str] = []
    fileDirectory: List[str] = []

    for root, dirs, files in os.walk(str(directory)):
        for file1 in files:
            if fileExtensionsTuple is not None:
                if file1.endswith(fileExtensionsTuple):
                    if fileStartsWithTuple is None:
                        if removeFile:
                            filePaths.append(root)
                        elif fileAndDirectory:
                            filePaths.append(os.path.join(root, file1))
                            fileDirectory.append(root)
                        else:
                            filePaths.append(os.path.join(root, file1))
                    elif file1.startswith(fileStartsWithTuple):
                        if removeFile:
                            filePaths.append(root)
                        elif fileAndDirectory:
                            filePaths.append(os.path.join(root, file1))
                            fileDirectory.append(root)
                        else:
                            filePaths.append(os.path.join(root, file1))
            else:
                if fileStartsWithTuple and file1.startswith(fileStartsWithTuple):
                    if removeFile:
                        filePaths.append(root)
                    elif fileAndDirectory:
                        filePaths.append(os.path.join(root, file1))
                        fileDirectory.append(root)
                    else:
                        filePaths.append(os.path.join(root, file1))

    if not filePaths:
        raise AttributeError('No path found')
    
    if printPath:
        print(f'filePaths={filePaths}')
        
    if fileAndDirectory:
        return (sorted(list(set(filePaths)), key=os.path.getmtime), sorted(list(set(fileDirectory)), key=os.path.getmtime))
    else:
        return sorted(list(set(filePaths)), key=os.path.getmtime)


def load_obj(filename: Union[str, Path]) -> Any:
    """Load a pickled object from disk.
    
    Useful for loading previously saved class instances.
    
    Args:
        filename: Path to the pickle file.
        
    Returns:
        The unpickled Python object.
    """
    with open(filename, 'rb') as fileToRead:
        loadedObject = pickle.load(fileToRead)
    return loadedObject


def _create_vignette_mask(rows: int, cols: int) -> np.ndarray:
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


def _compute_mean_fft(
    filePath: str, 
    dataFilePrefix: str, 
    startingFileNum: int, 
    framesPerFile: int, 
    frameStep: int,
    applyVignette: bool, 
    showVideo: bool
) -> Tuple[Optional[np.ndarray], int, int, Optional[Union[np.ndarray, int]]]:
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
    fileNum: int = startingFileNum
    sumFFT: Optional[np.ndarray] = None
    rows: int = 0
    cols: int = 0
    vignette: Optional[Union[np.ndarray, int]] = None
    running: bool = True

    while os.path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi") and running:
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        fileNum += 1
        
        num_frames_to_process = int(framesPerFile / frameStep)
        for frameNum in tqdm(range(0, framesPerFile, frameStep), 
                             total=num_frames_to_process,
                             desc=f"Computing FFT file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            if vignette is None:
                rows, cols = frame.shape[:2]
                vignette = _create_vignette_mask(rows, cols) if applyVignette else 1
            
            # frame is BGR, usually grayscale miniscope data is in channel 1
            frame_single = frame[:, :, 1] * vignette
            dft = cv2.dft(np.float32(frame_single), flags=cv2.DFT_COMPLEX_OUTPUT)
            dft_shift = np.fft.fftshift(dft)
            magnitude = cv2.magnitude(dft_shift[:, :, 0], dft_shift[:, :, 1])
            
            sumFFT = magnitude if sumFFT is None else sumFFT + magnitude
            
            if showVideo:
                cv2.imshow("Vid", frame_single / 255)
                if cv2.waitKey(10) & 0xFF == ord('q'):
                    running = False
                    break
                    
        cap.release()
    
    cv2.destroyAllWindows()
    return sumFFT, rows, cols, vignette


def _create_fft_mask(rows: int, cols: int, goodRadius: int, notchHalfWidth: int, centerHalfHeightToLeave: int) -> np.ndarray:
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
    cv2.circle(maskFFT, (ccol, crow), goodRadius, (1, 1, 1), thickness=-1)
    
    # Apply notch filter to remove horizontal bands
    maskFFT[(crow + centerHalfHeightToLeave):, (ccol - notchHalfWidth):(ccol + notchHalfWidth), 0] = 0
    maskFFT[:(crow - centerHalfHeightToLeave), (ccol - notchHalfWidth):(ccol + notchHalfWidth), 0] = 0
    maskFFT[:, :, 1] = maskFFT[:, :, 0]
    
    return maskFFT


def _preview_filtered_video(
    filePath: str, 
    dataFilePrefix: str, 
    startingFileNum: int, 
    framesPerFile: int, 
    frameStep: int, 
    maskFFT: np.ndarray
) -> None:
    """Display side-by-side comparison of raw and filtered video.
    
    Args:
        filePath: Directory containing video files.
        dataFilePrefix: Filename prefix.
        startingFileNum: First file number.
        framesPerFile: Frames per file.
        frameStep: Frame sampling step.
        maskFFT: FFT filter mask.
    """
    fileNum: int = startingFileNum
    running: bool = True

    while os.path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi") and running:
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        fileNum += 1
        
        num_frames_to_process = int(framesPerFile / frameStep)
        for frameNum in tqdm(range(0, framesPerFile, frameStep),
                             total=num_frames_to_process,
                             desc=f"Preview file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            frame_gray = frame[:, :, 1]
            img_back = _apply_fft_filter(frame_gray, maskFFT)
            
            im_diff = (128 + (frame_gray - img_back) * 2)
            im_v = cv2.hconcat([frame_gray, img_back, im_diff.astype(np.uint8)])
            cv2.imshow("Raw, Filtered, Difference", im_v / 255)
            
            if cv2.waitKey(10) & 0xFF == ord('q'):
                running = False
                break
                
        cap.release()
    
    cv2.destroyAllWindows()


def _apply_fft_filter(frame: np.ndarray, maskFFT: np.ndarray) -> np.ndarray:
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
    img_back_complex = cv2.idft(f_ishift)
    img_back = cv2.magnitude(img_back_complex[:, :, 0], img_back_complex[:, :, 1])
    img_back[img_back > 255] = 255
    return np.array(img_back, dtype=np.uint8)


def _compute_mean_fluorescence(
    filePath: str, 
    dataFilePrefix: str, 
    startingFileNum: int, 
    framesPerFile: int, 
    maskFFT: np.ndarray
) -> np.ndarray:
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
    fileNum: int = startingFileNum
    meanFrameList: List[float] = []
    
    while os.path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi"):
        cap = cv2.VideoCapture(filePath + dataFilePrefix + f"{fileNum:.0f}.avi")
        fileNum += 1
        
        for frameNum in tqdm(range(0, framesPerFile, 1),  # Always step=1 for mean calculation
                             total=framesPerFile,
                             desc=f"Mean fluorescence file {fileNum - 1:.0f}.avi"):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frameNum)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            frame_gray = frame[:, :, 1]
            dft = cv2.dft(np.float32(frame_gray), flags=cv2.DFT_COMPLEX_OUTPUT | cv2.DFT_SCALE)
            dft_shift = np.fft.fftshift(dft)
            fshift = dft_shift * maskFFT
            f_ishift = np.fft.ifftshift(fshift)
            img_back_complex = cv2.idft(f_ishift)
            img_back = cv2.magnitude(img_back_complex[:, :, 0], img_back_complex[:, :, 1])
            meanFrameList.append(float(img_back.mean()))
            
        cap.release()
    
    return np.array(meanFrameList)


def _create_lowpass_filter(meanFrame: np.ndarray, fs: float, cutoff: float, butterOrder: int) -> np.ndarray:
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


def _process_and_save_frames(
    filePath: str, 
    dataFilePrefix: str, 
    startingFileNum: int, 
    framesPerFile: int,
    maskFFT: np.ndarray, 
    meanFiltered: np.ndarray, 
    mode: str, 
    compressionCodec: str, 
    jobID: str,
    rows: int, 
    cols: int
) -> None:
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
    
    if mode == "save" and not os.path.exists(filePath + "Denoised"):
        os.mkdir(filePath + "Denoised")

    while os.path.exists(filePath + dataFilePrefix + f"{fileNum:.0f}.avi") and running:
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
            
            if mode == "save" and writeFile is not None:
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


def denoise_movie(
    dataDir: Union[str, List[str]], 
    dataFilePrefix: str = '', 
    showVideo: bool = False, 
    startingFileNum: int = 0,
    framesPerFile: int = 1000, 
    fs: float = 30, 
    frameStep: int = 10, 
    goodRadius: int = 2000,
    notchHalfWidth: int = 3, 
    centerHalfHeightToLeave: int = 90, 
    cutoff: float = 3.0,
    butterOrder: int = 6, 
    mode: str = 'display', 
    compressionCodec: str = 'FFV1', 
    jobID: str = ''
) -> None:
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


def import_video_as_numpy_array(
    filename: str, 
    frames: Union[int, str] = 'all', 
    displayFrame: bool = False, 
    frameToDisplay: int = 10
) -> np.ndarray:
    """Import a video file directly into a NumPy array.
    
    This function leverages OpenCV to read video frames sequentially and load them
    into a preallocated 4D NumPy array `(frames, height, width, channels)`.
    
    *Credit: Adapted from https://stackoverflow.com/questions/42163058/how-to-turn-a-video-into-numpy-array*

    Args:
        filename (str): The absolute or relative path to the video file.
        frames (int or 'all', optional): Number of frames to read. Defaults to 'all'.
        displayFrame (bool, optional): If True, displays a specific frame after loading. Defaults to False.
        frameToDisplay (int, optional): The 1-indexed frame number to display if `displayFrame` is True. Defaults to 10.

    Returns:
        np.ndarray: A 4D uint8 array containing the video data `(frames, height, width, 3)`.
    """
    cap = cv2.VideoCapture(filename)
    frameCount = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frameWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frameHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frames != 'all':
        frameCount = int(frames)
    buf = np.empty((int(frameCount), int(frameHeight), int(frameWidth), 3), np.dtype('uint8'))
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


def quat_to_euler(qw: float, qx: float, qy: float, qz: float, degrees: bool = False) -> List[float]:
    """Convert quaternion to Euler angles (roll, pitch, yaw).
    
    Args:
        qw: Quaternion w component.
        qx: Quaternion x component.
        qy: Quaternion y component.
        qz: Quaternion z component.
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


def conv_quat_to_euler(line: List[Any]) -> Optional[List[Any]]:
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


def _calc_num_minus_mean(num: float, mean: float) -> float:
    """Subtract mean from a number."""
    return (num - mean)


def _comp_v_thresh(num: float, VThresh: float) -> int:
    """Return 1 if abs(num) >= abs(VThresh), else 0."""
    x = int(abs(num) >= abs(VThresh))
    return x


def _find_step_index(conArray: np.ndarray) -> np.ndarray:
    """Find indices where step changes occur in an array."""
    x = np.diff(np.round(np.diff(conArray), 3))
    index = np.asarray(np.where(abs(x) > 1)[0]) + 1
    return index


def thresh_func(dataArray: np.ndarray, threshVal: float) -> np.ndarray:
    """Find indices where data crosses above a threshold.
    
    Args:
        dataArray: Input data array.
        threshVal: Threshold value.
        
    Returns:
        Array of indices where threshold crossings occur.
    """
    binary_array = np.where(dataArray >= threshVal, 1, 0)
    indices = np.argwhere(np.diff(binary_array) == 1)
    addArr = np.zeros(np.shape(indices))
    if indices.size > 0:
        addArr[..., -1] = 1
    return indices + addArr


def filter_data(
    data: np.ndarray, 
    n: int, 
    cut: Union[float, List[float], np.ndarray], 
    ftype: str, 
    btype: str, 
    fs: float, 
    bodePlot: bool = False
) -> np.ndarray:
    """ Use ftype to indicate FIR or Butterworth filter.
    
    For the FIR filter indicate a LowPass, HighPass, or BandPass with btype = lowpass, highpass, or bandpass, respectively. 
    n is the length of the filter (number of coefficients, i.e. the filter order + 1). numtaps must be odd if a passband includes the Nyquist frequency.
    A good value for n is 10000.
    Channel should be set to desired .ncs file
    
    The Butterworth filters have a more linear phase response in the pass-band than other types and is able to provide better group delay performance, and also a lower level of overshoot.
    Indicate the filter type by setting btype = 'low', 'high', or 'band'.
    The default for n is n = 2
    For a bandpass filter indicate the lowstop and the highstop by using an array. example: wn= ([10, 30])"""

    filteredData: np.ndarray
    if ftype.lower() == 'fir':
        h = firwin(n, cut, pass_zero=btype, fs=fs)  # Build the FIR filter
        filteredData = filtfilt(h, 1, data)  # Zero-phase filter the data
        if bodePlot:
            w, a = freqz(h, worN=10000, fs=fs if fs else 2000)
            plt.figure()
            plt.semilogx(w, abs(a))
            
            w_b, mag, phase = bode((h, 1), w=2 * np.pi * w)
            plt.figure()
            plt.semilogx(w_b, mag)
            plt.figure()
            plt.semilogx(w_b, phase)

    elif ftype.lower() in ('butterworth', 'butter'):
        b, a_filt = butter(n, cut, btype=btype, fs=fs)
        filteredData = filtfilt(b, a_filt, data)
        
        if bodePlot:
            w, h_resp = freqz(b, a_filt, worN=10000, fs=fs if fs else 2000)
            plt.figure()
            plt.semilogx(w, abs(h_resp))
            
            w_b, mag, phase = bode((b, a_filt), w=2 * np.pi * w)
            plt.figure()
            plt.semilogx(w_b, mag)
            plt.figure()
            plt.semilogx(w_b, phase)
    else:
        raise ValueError(f"Unknown filter type: {ftype}")

    return filteredData


def update_csv_cell(data: Any, columnTitle: str, lineNum: int, csvFile: Union[str, Path]) -> None:
    """Update a single cell in a CSV file.
    
    Args:
        data: New value to write.
        columnTitle: Column header name.
        lineNum: Line number to update.
        csvFile: Path to CSV file.
    """
    csvData: List[Dict[str, str]] = []
    fieldnames: Optional[List[str]] = None
    
    with open(csvFile, 'r') as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is not None:
            fieldnames = list(reader.fieldnames)
        for row in reader:
            if row.get('line number') == str(lineNum):
                row[columnTitle] = str(data)
            csvData.append(row)

    if fieldnames:
        with open(csvFile, 'w', newline='') as writeFile:
            writer = csv.DictWriter(writeFile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csvData)


def append_row_csv(data: Dict[str, Any], filename: Union[str, Path]) -> None:
    """Appends a new row to a CSV file.
    Args:
        data: Dictionary of data to be added to the csv file
        filename: Name of the CSV file to write to.
    """
    file_exists = os.path.exists(filename)
    with open(filename, 'a', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(data.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)


def spike_trig_avg(eventArray: np.ndarray, dataArray: np.ndarray, framesb: int, framesa: int) -> Dict[int, np.ndarray]:       
    """
    Compute the average spike values starting 'framesb' before the event
    and ending 'framesa' after the event.
    
    Args:
        eventArray: A numpy array of when and/or where events occur. Can either
                    be in the format of [[component, frame],...] or
                    [[frame],...]
        dataArray: A numpy array of the signal values at each frame.
        framesb: Number of frames before the event to include.
        framesa: Number of frames after the event to include.
    Returns:
        avgEventDict: a dictionary dictionary where the keys represent the
                      component number from the dataArray and the value is
                      a numpy array of the average values at each frame
                      of the designated window around the event
    """
    avgEventDict: Dict[int, np.ndarray] = {}
    if dataArray.ndim == 1:
        valid_events = 0
        for event in eventArray:
            idx = int(event[0])
            if idx >= framesb and idx <= dataArray.size - framesa - 1:
                chunk = dataArray[idx - framesb:idx + framesa + 1]
                if 0 in avgEventDict:
                    avgEventDict[0] = avgEventDict[0] + chunk
                else:
                    avgEventDict[0] = chunk.astype(float)
                valid_events += 1
        if 0 in avgEventDict and valid_events > 0:
            avgEventDict[0] /= valid_events
    else:
        for event in eventArray:
            comp = int(event[0])
            idx = int(event[1])
            if idx >= framesb and idx <= dataArray[comp].size - framesa - 1:
                chunk = dataArray[comp][idx - framesb:idx + framesa + 1]
                if comp in avgEventDict:
                    avgEventDict[comp] = avgEventDict[comp] + chunk
                else:
                    avgEventDict[comp] = chunk.astype(float)
        
        for component in avgEventDict:
            num_events = len(np.argwhere(eventArray[:, 0] == component))
            if num_events > 0:
                avgEventDict[component] /= num_events
    return avgEventDict


def z_score(dataArray: np.ndarray, frameWindow: int = 1000) -> np.ndarray:
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
    
    zScoreArray = np.zeros_like(dataArray, dtype=float)
    num_components, num_frames = dataArray.shape if dataArray.ndim > 1 else (1, dataArray.size)
    
    for i in range(0, math.ceil(num_frames / frameWindow)):
        start = i * frameWindow
        end = min((i + 1) * frameWindow, num_frames)
        if start >= num_frames:
            break
            
        if dataArray.ndim == 1:
            zScoreArray[start:end] = stats.zscore(dataArray[start:end])
        else:
            zScoreArray[:, start:end] = stats.zscore(dataArray[:, start:end], axis=1)
            
    return np.nan_to_num(zScoreArray)


def get_coords_dict_from_analysis_params(miniscope_data_manager: Any) -> Tuple[Optional[Dict[str, int]], str]:
    """Extract crop coordinates from analysis parameters.
    
    Reads the 'crop_coords' column from analysis_params and returns
    a dict with x0, y0, x1, y1 keys suitable for cropping.
    
    Args:
        miniscope_data_manager: Data manager with analysis_params.
        
    Returns:
        Tuple of (coords_dict, crop_job_name). coords_dict is None
        if no crop coordinates are found.
    """
    coords_dict: Optional[Dict[str, int]] = None
    crop_job_name: str = ''
    try:
        if miniscope_data_manager.analysis_params:
            previous_coords = miniscope_data_manager.analysis_params.get('crop_coords')
            if previous_coords and len(previous_coords) >= 4:
                coords_dict = {
                    'x0': int(previous_coords[0]),
                    'y0': int(previous_coords[1]),
                    'x1': int(previous_coords[2]),
                    'y1': int(previous_coords[3])
                }
                crop_job_name = '_crop'
    except (KeyError, TypeError, IndexError):
        print("Did not find valid crop coordinates in analysis_params['crop_coords']")
    
    return coords_dict, crop_job_name
        
