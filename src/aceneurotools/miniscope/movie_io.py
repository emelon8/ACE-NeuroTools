import os

import caiman as cm
import cv2
import numpy as np


class MovieIO:
    """Static utility class for saving and loading CaImAn movies.
    
    Provides standardized methods for movie I/O to the saved_movies directory.
    """

    @staticmethod
    def save_movie(dm, movie_file_name, movie=None):
        """Save a movie to disk in the saved_movies directory.
        
        Args:
            dm: MiniscopeDataManager with metadata for directory path.
            movie_file_name: Base filename (without extension).
            movie: Optional movie to save; uses dm.movie if None.
            
        Returns:
            Full path to the saved .avi file.
        """

        # create the saved_movies directory if it doesn't exist
        miniscope_dir_path = dm.metadata['calcium imaging directory']

        saved_movies_dir = os.path.join(miniscope_dir_path, 'saved_movies')
        os.makedirs(saved_movies_dir, exist_ok=True)

        # create the filename
        file_name = os.path.join(saved_movies_dir, movie_file_name) + '.avi'

        # save movie
        print(f"saving movie: {file_name}\n\n")
        #uses caiman movie method .save() to save what is stored in data_manager.movie
        if movie is not None:
            movie.save(file_name, compress=0)
        else:
            dm.movie.save(file_name, compress=0)

        # return the full file path
        return file_name

    @staticmethod
    def load_movie(miniscope_dir_path, movie_file_name):
        """Load a movie from the saved_movies directory.
        
        Args:
            miniscope_dir_path: Path to the miniscope data directory.
            movie_file_name: Filename of the movie to load.
            
        Returns:
            CaImAn movie object.
        """
        # Load the movie from the specified file path
        path = os.path.join(miniscope_dir_path, 'saved_movies', movie_file_name)
        return cm.load(path)


def import_video_as_numpy_array(
    filename: str,
    frames: int | str = 'all',
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

