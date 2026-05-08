import numpy as np
from typing import Dict, Any, List, Optional


class Spectrogram:
    """Represents a computed spectrogram from ephys data.
    
    Stores the power spectral density (PSD) matrix and associated time
    and frequency coordinate vectors.
    
    Attributes:
        psd: 2D numpy array [frequency x time] of power values (e.g., in dB).
        stimes: 1D numpy array of timestamps for each time bin (s).
        sfreqs: 1D numpy array of frequency values for each bin (Hz).
    """

    psd: np.ndarray
    stimes: np.ndarray
    sfreqs: np.ndarray
    
    def __init__(self, psd: np.ndarray, stimes: np.ndarray, sfreqs: np.ndarray) -> None:
        """Initialize a Spectrogram with PSD data and coordinates.
        
        Args:
            psd: 2D array of power values (rows=freqs, cols=times).
            stimes: 1D array of time bin centers.
            sfreqs: 1D array of frequency bin centers.
        """
        self.psd = psd
        self.stimes = stimes
        self.sfreqs = sfreqs
