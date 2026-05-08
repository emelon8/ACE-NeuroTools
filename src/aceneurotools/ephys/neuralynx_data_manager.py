"""
Neuralynx Ephys Data Manager

Handles loading and processing Neuralynx .nev and .ncs files into Channel objects.
"""

import os
import numpy as np
from neo.io import NeuralynxIO  # type: ignore
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.block_processor import BlockProcessor
from aceneurotools.shared.path_finder import PathFinder
from typing import List, Optional, Union, Any
from pathlib import Path

class NeuralynxDataManager(EphysDataManager):
    """
    Manages the import of raw Neuralynx ephys data.
    """

    @classmethod
    def can_handle(cls, directory: Union[str, Path]) -> bool:
        """Returns True if Neuralynx data files (.nev) are found in the directory."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return False
        return len(list(dir_path.glob('*.nev'))) > 0 or len(list(dir_path.glob('Events.nev'))) > 0

    def import_ephys_block(self, ephys_directory: Union[str, Path]) -> None:
        """Load raw Neuralynx data from disk into a Neo Block."""
        print('Importing raw Neuralynx ephys data...')
        ephys_file_path = self._find_ephys_file_path(ephys_directory)
        ephys_dir_path = os.path.dirname(ephys_file_path)
        file_reader = NeuralynxIO(dirname=ephys_dir_path)
        self.ephys_block = file_reader.read_block(signal_group_mode='split-all')

    def process_ephys_block_to_channels(
        self, 
        channels: Optional[List[str]] = None, 
        remove_artifacts: bool = False
    ) -> None:
        """Process raw ephys block data into Channel objects using BlockProcessor."""
        if self.ephys_block is None:
            raise ValueError("ephys_block is None. Must import data first.")
        
        processor = BlockProcessor(self.ephys_block, self.logger)
        new_channels = processor.process_raw_ephys(channels or [], remove_artifacts=remove_artifacts)
        for k, v in new_channels.items():
            self.channels[k] = v

    def _find_ephys_file_path(self, ephys_directory: Union[str, Path]) -> str:
        """Find the Events.nev file in the ephys directory."""
        path_finder = PathFinder()
        events_path = path_finder.find( 
                        directory=str(ephys_directory),
                        suffix=".nev",
                        prefix="Events"
            )
        if not events_path:
            raise FileNotFoundError(f"Could not find Events.nev in {ephys_directory}")
        return str(events_path[0])

    def get_sync_timestamps(self, channel_name: Optional[str] = None) -> np.ndarray:
        """
        Extract raw hardware sync TTL timestamps from an ephys channel.
        For Neuralynx, we look for the specific TTL label in the channel events.
        """
        import numpy as np
        
        if not self.channels:
            raise ValueError("No channels loaded. Call process_ephys_block_to_channels first.")
            
        # If no channel specified, just use the first one available
        if channel_name is None:
            channel_name = list(self.channels.keys())[0]
            
        channel = self.get_channel(channel_name)
        
        ttl_timestamps = []
        ttl_label_pattern = 'TTL Input on AcqSystem1_0 board 0 port 1 value (0x0001)'
        
        events = channel.events
        if events and 'labels' in events and 'timestamps' in events:
            for i, label in enumerate(events['labels']):
                if label == ttl_label_pattern:
                    ttl_timestamps.append(events['timestamps'][i])
                    
        return np.array(ttl_timestamps)
