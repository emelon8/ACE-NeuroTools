from typing import Any

import numpy as np

from aceneurotools.miniscope.projections import Projections
from aceneurotools.shared.misc_functions import filter_data


class FilterMiniscopeData:
    """Container for filtered miniscope projection data.
    
    Used during post-processing to store and filter calcium imaging projections.
    
    Attributes:
        data: Raw projection data from the miniscope.
        filtered_data: Filtered version of the data (populated after filtering).
        frame_rate: Recording frame rate in Hz.
        n: Filter order.
        cut: Cutoff frequency or [low, high] for bandpass.
        ftype: Filter type ('butter' for Butterworth).
        btype: Band type ('bandpass', 'low', 'high').
    """

    data: np.ndarray
    filtered_data: list[Any] | np.ndarray
    frame_rate: float
    n: int
    cut: float | list[float]
    ftype: str
    btype: str

    def __init__(
        self,
        projections: Projections,
        frame_rate: float,
        n: int = 2,
        cut: float | list[float] = [0.1, 1.5],
        ftype: str = 'butter',
        btype: str = 'bandpass'
    ) -> None:
        """Initialize with projection data and filter parameters.
        
        Args:
            projections: Projections object with time attribute.
            frame_rate: Recording frame rate in Hz.
            n: Filter order (default 2).
            cut: Cutoff frequencies for bandpass filter.
            ftype: Filter type (default 'butter').
            btype: Band type (default 'bandpass').
        """
        self.data = projections.time
        self.filtered_data = []
        self.frame_rate = frame_rate
        self.n = n
        self.cut = cut
        self.ftype = ftype
        self.btype = btype



    def filter_miniscope_data(self) -> None:
        """Apply the configured filter to the projection data."""
        self.filtered_data = filter_data(self.data, n=self.n, cut=self.cut, ftype=self.ftype, btype=self.btype, fs=self.frame_rate)
