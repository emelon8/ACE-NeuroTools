"""
RHS2116 Ephys Data Manager

Manages the import of RHS2116 .raw ephys data (AC/DC/Clock) using neo.rawio.
"""
import os
from pathlib import Path
import numpy as np
from neo.rawio import RawBinarySignalRawIO  # type: ignore
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.channel import Channel
from typing import List, Optional, Union, Any, Dict, TYPE_CHECKING
import decimal

if TYPE_CHECKING:
    from numpy.typing import DTypeLike

class RHS2116DataManager(EphysDataManager):
    """
    Manages the import of raw RHS2116 ephys data.
    Loads AC, DC, and Clock data from .raw files using neo.rawio to optimize memory.
    """

    # RHS2116 constants
    AC_UV_MULTIPLIER: float = 0.195
    AC_OFFSET: int = 32768
    DC_MV_MULTIPLIER: float = -19.23
    DC_OFFSET: int = 512
    NUM_CHANNELS: int = 32

    data_directory: Path
    suffix: str
    meta: np.ndarray
    sampling_rate: float
    clock_path: Path
    ac_path: Path
    dc_path: Path

    @classmethod
    def can_handle(cls, directory: Union[str, Path]) -> bool:
        """Returns True if RHS2116 data files (.raw) are found in the directory."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return False
        return len(list(dir_path.glob('*.raw'))) > 0 or len(list(dir_path.glob('rhs2116*.raw'))) > 0

    def import_ephys_block(self, ephys_directory: Union[str, Path]) -> None:
        """Prepare raw RHS2116 data streams."""
        print('Importing RHS2116 ephys data headers...')
        self.data_directory = Path(ephys_directory)

        # Find suffix from start-time CSV
        start_time_files = list(self.data_directory.glob('start-time_*.csv'))
        # Exclude miniscope metadata files if they matched
        start_time_files = [f for f in start_time_files if 'miniscope' not in f.name]
        
        if not start_time_files:
             raise FileNotFoundError(f"No start-time CSV found in {self.data_directory}")
             
        start_time_path = start_time_files[0]
        self.suffix = start_time_path.stem.split('_')[-1]
        
        dt = {'names': ('time', 'acq_clk_hz', 'block_read_sz', 'block_write_sz'),
              'formats': ('datetime64[us]', 'u4', 'u4', 'u4')}
        self.meta = np.genfromtxt(start_time_path, delimiter=',', dtype=dt, skip_header=0)
        
        self.logger.critical(f"Recording was started at {self.meta['time']} GMT")
        self.logger.critical(f'Acquisition clock rate was {self.meta["acq_clk_hz"] / 1e6 } MHz')
        self.sampling_rate = float(self.meta['acq_clk_hz'])
        
        # Validate files
        self.clock_path = self.data_directory / f'rhs2116pair-clock_{self.suffix}.raw'
        self.ac_path = self.data_directory / f'rhs2116pair-ac_{self.suffix}.raw'
        self.dc_path = self.data_directory / f'rhs2116pair-dc_{self.suffix}.raw'

        for p in [self.clock_path, self.ac_path, self.dc_path]:
            if not p.exists():
                raise FileNotFoundError(f"Required file not found: {p}")

        # The actual loading of signals is done in process_ephys_block_to_channels
        # to match the block_processing chunking paradigm and save memory dynamically.
        self.ephys_block = "RHS2116_RawBinarySignalRawIO_Ready" # Placeholder to indicate import succeeds

    def process_ephys_block_to_channels(
        self, 
        channels: Optional[List[str]] = None, 
        remove_artifacts: bool = False
    ) -> None:
        """Process RawBinarySignalRawIO data into Channel objects natively."""
        if not self.ephys_block:
            raise ValueError("Data not imported. Call import_ephys_block first.")

        # 1. Load clock vector
        print("Loading hardware clock vector...")
        clock_data = np.fromfile(self.clock_path, dtype=np.uint64)
        time_vector = clock_data / self.sampling_rate

        offset = -(self.AC_OFFSET * self.AC_UV_MULTIPLIER)
        
        reader = RawBinarySignalRawIO(
            filename=str(self.ac_path),
            dtype='uint16',
            sampling_rate=self.sampling_rate,
            nb_channel=self.NUM_CHANNELS,
            bytesoffset=0,
            signal_gain=self.AC_UV_MULTIPLIER,
            signal_offset=offset
        )
        reader.parse_header()
        
        # Load in a large but safe chunk
        print("Fetching analog signal chunk...")
        ac_data = reader.get_analogsignal_chunk(
            block_index=0, 
            seg_index=0, 
            i_start=0, 
            i_stop=min(3000000, len(time_vector)),
            stream_index=0
        )
        print("Rescaling chunk...")
        ac_data_float = reader.rescale_signal_raw_to_float(
            ac_data,
            dtype='float32',
            stream_index=0
        )

        # Calculate effective sampling rate so analysis features (like spectrograms) don't crash trying to allocate 250M samples/sec
        # During verification, `time_vector` can be massive, stalling `np.diff`. calculating on the first thousands elements is sufficient
        subset_size = min(10000, len(time_vector))
        effective_sampling_rate = float(1.0 / np.median(np.diff(time_vector[:subset_size]))) if subset_size > 1 else self.sampling_rate

        # Trim the time vector down to the loaded signal chunk size
        time_vector = time_vector[:ac_data_float.shape[0]]

        # Create Channel objects compatible with downstream processing
        for i in range(self.NUM_CHANNELS):
            channel_name = f"RHS2116_AC_{i}"
            # If particular channels were requested, skip others
            if channels is not None and channel_name not in channels and i not in channels and str(i) not in channels:
                continue
                
            signal = ac_data_float[:, i]
            events = {'labels': [], 'timestamps': []}
            
            chan = Channel(channel_name, signal, effective_sampling_rate, time_vector, events)
            self.channels[channel_name] = chan

    def get_sync_timestamps(self, channel_name: Optional[str] = None) -> np.ndarray:
        """
        RHS2116 (ONIX) uses an absolute hardware clock that inherently synchronizes 
        with the ONIX miniscope clock, rather than external TTL pulses.
        """
        return np.array([])
