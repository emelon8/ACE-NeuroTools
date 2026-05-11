"""Projections data container and shared computation helper.

The :func:`compute_projections` module-level function is the single canonical
implementation shared by :class:`~aceneurotools.miniscope.miniscope_preprocessor.MiniscopePreprocessor`
and :class:`~aceneurotools.miniscope.miniscope_postprocessor.MiniscopePostprocessor`.
Any changes to the projection computation should be made here.
"""

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass


def compute_projections(movie: "np.ndarray") -> "Projections":
    """Compute spatial and temporal projections of a calcium movie.

    Calculates max, min, mean, median, standard-deviation, and range
    projections across frames (axis 0), plus a mean-fluorescence time series.

    This is the single authoritative implementation.  Both
    :class:`~aceneurotools.miniscope.miniscope_preprocessor.MiniscopePreprocessor`
    and :class:`~aceneurotools.miniscope.miniscope_postprocessor.MiniscopePostprocessor`
    delegate to this function so that algorithmic changes only need to be made here.

    Args:
        movie: 3-D array of shape ``(frames, height, width)`` (CaImAn movie or
            plain NumPy array).

    Returns:
        :class:`Projections` object containing all computed projection arrays.
    """
    from tqdm import tqdm  # imported here to keep the module lightweight

    print("\n\nComputing projections...\n")

    operations = {
        "max": lambda m: np.amax(m, axis=0),
        "std": lambda m: np.std(m, axis=0),
        "min": lambda m: np.amin(m, axis=0),
        "mean": lambda m: np.mean(m, axis=0),
        "median": lambda m: np.median(m, axis=0),
        "time": lambda m: m.mean(axis=(1, 2)),
    }

    results: dict = {}
    for name, op in tqdm(operations.items(), desc="Computing Projections"):
        results[name] = op(movie)

    results["range"] = results["max"] - results["min"]

    return Projections(
        results["max"],
        results["std"],
        results["min"],
        results["mean"],
        results["median"],
        results["range"],
        results["time"],
    )


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



