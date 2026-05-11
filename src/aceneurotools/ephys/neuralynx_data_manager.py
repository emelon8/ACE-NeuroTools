"""
Neuralynx Ephys Data Manager

Handles loading and processing Neuralynx .nev and .ncs files into Channel objects.
"""

import os
from pathlib import Path

import numpy as np
from neo.io import NeuralynxIO  # type: ignore

from aceneurotools.ephys.block_processor import BlockProcessor
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.shared.path_finder import PathFinder


class NeuralynxDataManager(EphysDataManager):
    """
    Manages the import of raw Neuralynx ephys data.
    """

    @classmethod
    def can_handle(cls, directory: str | Path) -> bool:
        """Returns True if Neuralynx data files (.nev) are found in the directory."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return False
        return len(list(dir_path.glob('*.nev'))) > 0 or len(list(dir_path.glob('Events.nev'))) > 0

    def import_ephys_block(self, ephys_directory: str | Path) -> None:
        """Load raw Neuralynx data from disk into a Neo Block."""
        print('Importing raw Neuralynx ephys data...')
        ephys_file_path = self._find_ephys_file_path(ephys_directory)
        ephys_dir_path = os.path.dirname(ephys_file_path)
        file_reader = NeuralynxIO(dirname=ephys_dir_path)
        self.ephys_block = file_reader.read_block(signal_group_mode='split-all')

    def process_ephys_block_to_channels(
        self,
        channels: list[str] | None = None,
        remove_artifacts: bool = False
    ) -> None:
        """Process raw ephys block data into Channel objects using BlockProcessor."""
        if self.ephys_block is None:
            raise ValueError("ephys_block is None. Must import data first.")

        processor = BlockProcessor(self.ephys_block, self.logger)
        new_channels = processor.process_raw_ephys(channels or [], remove_artifacts=remove_artifacts)
        for k, v in new_channels.items():
            self.channels[k] = v

    def _find_ephys_file_path(self, ephys_directory: str | Path) -> str:
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

    def get_sync_timestamps(self, channel_name: str | None = None) -> np.ndarray:
        """
        Extract hardware sync TTL timestamps from an ephys channel.

        Matches the label patterns recorded by Neuralynx Cheetah for both the
        rising (0x0001) and falling (0x0000) edges of the miniscope frame-sync
        TTL on port 0, matching the original analysis scripts exactly.
        """
        if not self.channels:
            raise ValueError("No channels loaded. Call process_ephys_block_to_channels first.")

        if channel_name is None:
            channel_name = list(self.channels.keys())[0]

        channel = self.get_channel(channel_name)
        events = channel.events

        if not (events and 'labels' in events and 'timestamps' in events):
            return np.array([])

        labels = np.asarray(events['labels']).astype(str)
        timestamps = np.asarray(events['timestamps'])

        ttl_high = 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0001).'
        ttl_low  = 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000).'
        mask = (labels == ttl_high) | (labels == ttl_low)
        return timestamps[mask]
