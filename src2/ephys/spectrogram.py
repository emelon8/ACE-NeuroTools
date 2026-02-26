import numpy as np


class Spectrogram:
    """Container for spectrogram data computed from an ephys signal.
    
    Attributes:
        psd_matrix_db: 2D array of power spectral density values in dB.
        time_points: 1D array of time values for spectrogram columns.
        freq_points: 1D array of frequency values for spectrogram rows.
    """
    
    def __init__(self, psd_matrix_db: np.array, time_points: np.array, freq_points: np.array):
        """Initialize a Spectrogram with computed PSD data.
        
        Args:
            psd_matrix_db: 2D numpy array of PSD values in decibels (freq x time).
            time_points: 1D numpy array of time values in seconds.
            freq_points: 1D numpy array of frequency values in Hz.
        """
        self.psd_matrix_db = psd_matrix_db
        self.time_points = time_points
        self.freq_points = freq_points
