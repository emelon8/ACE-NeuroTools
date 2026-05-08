import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy.typing import NDArray

class Projections:
    """Container for spatial and temporal projections of a calcium movie.
    
    Stores commonly used summary images computed across the movie frames.
    
    Attributes:
        max: Maximum projection (brightest pixel values across all frames).
        std: Standard deviation projection.
        min: Minimum projection.
        mean: Mean projection.
        median: Median projection.
        range: Range projection (max - min).
        time: Mean fluorescence over time (1D temporal trace).
    """
    
    max: np.ndarray
    std: np.ndarray
    min: np.ndarray
    mean: np.ndarray
    median: np.ndarray
    range: np.ndarray
    time: np.ndarray

    def __init__(
        self, 
        max: np.ndarray, 
        std: np.ndarray, 
        min: np.ndarray, 
        mean: np.ndarray, 
        median: np.ndarray, 
        range: np.ndarray, 
        time: np.ndarray
    ) -> None:
        """Initialize with all projection arrays.
        
        Args:
            max: 2D array of maximum values per pixel.
            std: 2D array of standard deviation per pixel.
            min: 2D array of minimum values per pixel.
            mean: 2D array of mean values per pixel.
            median: 2D array of median values per pixel.
            range: 2D array of range (max-min) per pixel.
            time: 1D array of mean fluorescence per frame.
        """
        self.max = max
        self.std = std
        self.min = min
        self.mean = mean
        self.median = median
        self.range = range
        self.time = time
        
        
        
    