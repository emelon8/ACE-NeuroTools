import numpy as np
import matplotlib.pyplot as plt
from abc import ABC, abstractmethod
from aceneurotools.ephys.channel import Channel
import logging
from scipy.signal import hilbert  # type: ignore
from typing import List, Optional, Union, Dict, Any, Type, TypeVar, cast
from pathlib import Path

T = TypeVar("T", bound="EphysDataManager")

class EphysDataManager(ABC):
    """
    Abstract base class for ephys data managers.
    Manages the import of raw ephys data and processes it into channels.
    Stores the processed channels in self.channels, where the key is the channel name and the value is a Channel object.
    """

    _registry: List[Type['EphysDataManager']] = []
    logger: logging.Logger
    channels: Dict[str, Channel]
    ephys_block: Any

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls not in cls._registry:
            cls._registry.append(cls)

    @classmethod
    def create(cls: Type[T], ephys_directory: Union[str, Path], **kwargs: Any) -> T:
        """Factory method to create the appropriate subclasses for the directory."""
        if ephys_directory is None:
            raise ValueError("ephys_directory must be provided to create() factory.")
            
        for subclass in cls._registry:
            if subclass.can_handle(ephys_directory):
                return cast(T, subclass(ephys_directory=ephys_directory, **kwargs))
                
        raise ValueError(f"No EphysDataManager subclass found that can handle directory: {ephys_directory}")

    @classmethod
    @abstractmethod
    def can_handle(cls, directory: Union[str, Path]) -> bool:
        """Return True if this class can handle the format in the given directory."""
        pass


    def __init__(
        self, 
        ephys_directory: Optional[Union[str, Path]] = None,
        auto_import_ephys_block: bool = True, 
        auto_process_block: bool = True, 
        auto_compute_phases: bool = True, 
        level: Union[str, int] = "CRITICAL", 
        channels: Optional[List[str]] = None, 
        remove_artifacts: bool = False
    ) -> None:
        """Initialize the EphysDataManager and optionally load data.
        
        Args:
            ephys_directory: Path to directory containing ephys data.
            auto_import_ephys_block: If True, automatically import raw ephys data.
            auto_process_block: If True, automatically process block into channels.
            auto_compute_phases: If True, automatically compute phase for all channels.
            level: Logging level string.
            channels: Channel names to process (optional).
            remove_artifacts: If True, apply artifact removal during processing.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(level)
        
        self.channels = {}  # Processed channels
        self.ephys_block = None  # Raw data storage

        if auto_import_ephys_block:
            assert ephys_directory is not None
            self.import_ephys_block(ephys_directory)

        if auto_process_block:
            self.process_ephys_block_to_channels(channels=channels, remove_artifacts=remove_artifacts)
            
        if auto_compute_phases:
            self.compute_phases_all_channels()
        

    @abstractmethod
    def import_ephys_block(self, ephys_directory: Union[str, Path]) -> None:
        """Load raw ephys data from disk."""
        pass

    @abstractmethod
    def process_ephys_block_to_channels(self, channels: Optional[List[str]] = None, remove_artifacts: bool = False) -> None:
        """Process raw ephys data into Channel objects."""
        pass

    @abstractmethod
    def get_sync_timestamps(self, channel_name: Optional[str] = None) -> np.ndarray:
        """
        Extract raw hardware sync timestamps from an ephys channel.
        To be overridden by subclasses.
        """
        pass

    def compute_phases_all_channels(self) -> None:
        """Compute instantaneous phase for all loaded channels."""
        for key, value in self.channels.items():
            self.channels[key] = self.compute_phase(value)
            

    def compute_phase(self, channel: Channel) -> Channel:
        """Compute instantaneous phase using Hilbert transform.
        
        Args:
            channel: Channel object with signal data.
            
        Returns:
            Channel object with phases attribute populated.
        """
        print(f"Computing phase for {channel.name}")
        analytic_signal = hilbert(channel.signal)
        channel.phases = np.angle(analytic_signal)
        return channel
    

    def filter_ephys(
        self, 
        channel_name: str, 
        n: int = 2, 
        cut: Union[float, List[float], np.ndarray] = [0.5, 4], 
        ftype: str = 'butter', 
        btype: str = 'bandpass', 
        replace_signal: bool = True
    ) -> np.ndarray:
        """Apply a frequency filter to a channel's signal.
        
        Supports FIR and Butterworth filter types with configurable
        cutoff frequencies and band types.
        
        Args:
            channel_name: Name of the channel to filter.
            n: Filter order (Butterworth) or number of taps (FIR).
            cut: Cutoff frequency or [low, high] for bandpass.
            ftype: Filter type ('butter', 'butterworth', or 'fir').
            btype: Band type ('low', 'high', 'band', 'bandpass').
            replace_signal: If True, overwrite signal; else store in signal_filtered.
            
        Returns:
            Filtered signal as 1D numpy array.
            
        Raises:
            ValueError: If channel is not found in loaded channels.
        """
        # self.logger.info('Filtering ' + channel_name + ' with a(n) ' + ftype + ' filter ...')
        try:
            channel: Channel = self.channels[channel_name]
        except KeyError:
            raise ValueError("Channel not found in data_manager. Please import the data first.")
            
        print(f"Filtering the ephys signal: {channel_name}")
            
        filtered_data = self._filter_data(
            channel.signal,
            n=n,
            cut=cut,
            ftype=ftype,
            btype=btype,
            fs=channel.sampling_rate
        )
        
        if (replace_signal):
            self.channels[channel_name].signal = filtered_data
        else:
            self.channels[channel_name].signal_filtered = filtered_data

        return filtered_data
    
    def get_channels(self) -> Dict[str, Channel]:
        """Return dictionary of all processed channels."""
        return self.channels
    
    def get_channel(self, channel_name: str) -> Channel:
        """Return a single channel by name.
        
        Args:
            channel_name: Name of the channel to retrieve.
        """
        return self.channels[channel_name]

    
    @staticmethod
    def _filter_data(
        data: np.ndarray, 
        n: int, 
        cut: Union[float, List[float], np.ndarray], 
        ftype: str, 
        btype: str, 
        fs: float, 
        bodePlot: bool = False
    ) -> np.ndarray:
        """Apply FIR or Butterworth filter to signal data.
        
        Args:
            data: 1D numpy array of signal values.
            n: Filter order (Butterworth) or number of taps (FIR).
            cut: Cutoff frequency or [low, high] for bandpass.
            ftype: Filter type ('fir', 'butter', or 'butterworth').
            btype: Band type ('low', 'high', 'band', 'bandpass', etc.).
            fs: Sampling frequency in Hz.
            bodePlot: If True, plot Bode diagram of filter response.
            
        Returns:
            Filtered signal as 1D numpy array.
        """
        from scipy.signal import butter, freqz, filtfilt, firwin, bode  # type: ignore
        import logging

        # Set up logging
        logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s - %(levelname)s - %(message)s') # turn to DEBUG for more info
        
        # Log input variables
        logging.info(f"Input variables:")
        logging.info(f"- data: {data}")
        logging.info(f"- n: {n}")
        logging.info(f"- cut: {cut}")
        logging.info(f"- ftype: {ftype}")
        logging.info(f"- btype: {btype}")
        logging.info(f"- fs: {fs}")
        logging.info(f"- bodePlot: {bodePlot}")
        
        # For the FIR filter indicate a LowPass, HighPass, or BandPass with btype = lowpass, highpass, or bandpass, respectively. 
        # n is the length of the filter (number of coefficients, i.e. the filter order + 1). numtaps must be odd if a passband includes the Nyquist frequency.
        # A good value for n is 10000.
        # Channel should be set to desired .ncs file
        # 
        # The Butterworth filters have a more linear phase response in the pass-band than other types and is able to provide better group delay performance, and also a lower level of overshoot.
        # Indicate the filter type by setting btype = 'low', 'high', or 'band'.
        # The default for n is n = 2
        # For a bandpass filter indicate the lowstop and the highstop by using an array. example: wn= ([10, 30])

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
            print(f"fs: {type(fs)}")
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
        else:
            raise ValueError(f"Unknown filter type: {ftype}")

        return filteredData
        
        
        
        