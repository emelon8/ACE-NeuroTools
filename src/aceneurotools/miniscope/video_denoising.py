"""FFT-based miniscope movie denoising.

Removes traveling horizontal bands and whole-image flicker artifacts from raw
miniscope ``.avi`` recordings via a 2-D FFT notch filter plus a temporal
low-pass correction of mean fluorescence. Based on Daniel Aharoni's denoising
notebook:
https://github.com/Aharoni-Lab/Miniscope-v4/tree/master/Miniscope-v4-Denoising-Notebook

Public entry point: :func:`denoise_movie`.
"""

import os

import cv2
import numpy as np
from scipy.signal import butter, filtfilt
from tqdm import tqdm


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
) -> tuple[np.ndarray | None, int, int, np.ndarray | int | None]:
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
    sumFFT: np.ndarray | None = None
    rows: int = 0
    cols: int = 0
    vignette: np.ndarray | int | None = None
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
    meanFrameList: list[float] = []

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
    dataDir: str | list[str],
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

