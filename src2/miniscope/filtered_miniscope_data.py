from src2.shared.misc_functions import filter_data


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
    
    def __init__(self, projections, frame_rate, n=2, cut=[0.1,1.5], ftype='butter', btype='bandpass'):
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
    


    def filter_miniscope_data(self):
        """Apply the configured filter to the projection data."""
        self.filtered_data = filter_data(self.data, n=self.n, cut=self.cut, ftype=self.ftype, btype=self.btype, fs=self.frame_rate)