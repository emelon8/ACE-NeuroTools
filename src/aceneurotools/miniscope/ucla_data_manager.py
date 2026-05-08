"""
V3 Miniscope Data Manager
"""
import csv
import json
import numpy as np
from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
from aceneurotools.shared.path_finder import PathFinder
from aceneurotools.shared.exceptions import DataImportError
from typing import List, Optional, Union, Dict, Any, Tuple
from pathlib import Path

class UCLADataManager(MiniscopeDataManager):
    """
    Handles V3 Miniscope data formats (metaData.json, timeStamps.csv, default events).
    """

    @classmethod
    def can_handle(cls, directory: Union[str, Path]) -> bool:
        """Returns True if standard metaData.json is found in the directory."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return False
        # Search for any metaData*.json or timeStamps*.csv
        return len(list(dir_path.rglob('metaData*.json'))) > 0 or len(list(dir_path.rglob('timeStamps*.csv'))) > 0

    def _get_miniscope_metadata(self) -> Dict[str, Any]:
        """
        Imports miniscope metadata from a JSON file or multiple located at the paths returned by self._find_metadata_paths().
        """
        metadata_raw = self._find_metadata_paths()
        metadata_paths: List[str]
        if isinstance(metadata_raw, list):
            metadata_paths = [str(p) for p in metadata_raw]
        else:
            metadata_paths = [str(metadata_raw)] if metadata_raw else []

        print(f"Reading metadata from {metadata_paths}...")
        
        if not metadata_paths:
            print("No metadata paths found in your miniscope directory")
            return {}
        
        metadata: Dict[str, Any] = {}
        for metadata_path in metadata_paths:
            try:
                with open(metadata_path, 'r') as file:
                    data = json.load(file)
                    metadata.update(data)
            except (IOError, json.JSONDecodeError) as e:
                raise DataImportError(f"Error reading or parsing metadata file '{metadata_path}': {e}") from e
    
            # If 'frameRate' exists, try to convert it to a float
            if 'frameRate' in metadata:
                value = metadata['frameRate']
                if not isinstance(value, (int, float)):
                    try:
                        metadata['frameRate'] = float(value)
                    except ValueError:
                        cleaned_value = str(value).replace('FPS', '').strip()
                        try:
                            metadata['frameRate'] = float(cleaned_value)
                        except ValueError:
                            raise ValueError(f"Unable to convert frameRate value '{value}' to float.")
        return metadata

    def _get_timestamps(self) -> Tuple[np.ndarray, List[int]]:
        """Load frame timestamps and numbers from CSV file."""
        file_path_raw = self._find_timestamps_path()
        file_path = str(file_path_raw)
        time_stamps: List[float] = []
        frame_numbers: List[int] = []
        with open(file_path, newline='') as t:
            next(t)
            reader = csv.reader(t)
            for row in reader:
                frame_numbers.append(int(row[0]))
                time_stamps.append(float(row[1]))
        ts_array = np.divide(np.asarray(time_stamps), 1000)  # convert from ms to s
        return ts_array, frame_numbers

    def _get_miniscope_events(self) -> Dict[str, Union[List[Any], np.ndarray]]:
        """Import calcium imaging experiment events."""
        if self.metadata is None or 'calcium imaging directory' not in self.metadata:
            print("Warning: Metadata or calcium imaging directory missing. Cannot load events.")
            return {'timestamps': [], 'labels': []}

        miniscope_events_filepaths = PathFinder.find(str(self.metadata['calcium imaging directory']), '.csv', 'notes')
        
        if miniscope_events_filepaths is not None and len(miniscope_events_filepaths) == 1:
            miniscope_events_filepath = str(miniscope_events_filepaths[0])
        elif miniscope_events_filepaths is not None and len(miniscope_events_filepaths) > 1:
            raise ValueError('Found multiple event files')
        else:
             # Just return empty if none so it doesn't crash if it's optional
            miniscope_events_filepath = None
            
        miniscope_events: Dict[str, Any] = {}
        miniscope_events['timestamps'] = []
        miniscope_events['labels'] = []
        
        if miniscope_events_filepath:
            try:
                with open(miniscope_events_filepath, newline='') as t:
                    next(t)
                    reader = csv.reader(t)
                    for row in reader:
                        miniscope_events['timestamps'].append(int(row[0]))
                        miniscope_events['labels'].append(row[1])
                miniscope_events['timestamps'] = np.divide(np.asarray(miniscope_events['timestamps']), 1000)  # converts from ms to s
            except (IOError, IndexError, ValueError, csv.Error) as e:
                print(f"Failed to extract events from notes.csv ({e}). Storing an empty dictionary...")
                
        return miniscope_events

    def sync_timestamps(
        self, 
        ephys_dm: Optional[Any] = None, 
        channel_name: Optional[str] = None, 
        **kwargs: Any
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Synchronize V3 miniscope frame timestamps to ephys time using TTL pulses.
        
        Args:
            ephys_dm: EphysDataManager instance to extract TTL sync pulses from.
            channel_name: Optional specific channel name from ephys_dm (defaults to first available).
            
        Returns:
            Tuple of synced calcium timestamps and low confidence periods.
        """
        import sys
        import numpy as np
        
        if ephys_dm is None:
            raise ValueError(f"UCLADataManager requires an ephys_dm to sync timestamps (e.g. NeuralynxDataManager).")
            
        print("Extracting TTL sync pulses from ephys data...")
        # Get raw TTL timestamps (Rising edges) from the ephys data manager
        tCaIm = ephys_dm.get_sync_timestamps(channel_name)
        
        if len(tCaIm) == 0:
            raise ValueError("No TTL sync pulses found in ephys data. Cannot sync UCLA miniscope data.")
            
        print("Checking for missing TTL pulses in V3 data...")
        low_confidence_periods = np.empty((0, 2))
        threshold = kwargs.get('threshold', 0.065)
        fix_TTL_gaps = kwargs.get('fix_TTL_gaps', False)
        delete_TTLs = kwargs.get('delete_TTLs', True)
        
        # Check for gaps between TTLs. Since we only extracted the ON pulses,
        # consecutive pulses should be separated by ~1/fps seconds.
        dtCaIm = np.diff(tCaIm)
        idx_TTL_gap = np.where(dtCaIm > threshold)[0]
        
        if len(idx_TTL_gap) == 0:
            print(f"No gaps were found with a threshold of {threshold * 1000} ms.")
        elif fix_TTL_gaps:
            print("Fixing gaps in the TTL events...")
            # Reverse order so insertions don't shift subsequent indices
            flippedidx_TTL_gap = np.flip(idx_TTL_gap)
            for gap_idx in flippedidx_TTL_gap:
                gap_duration = dtCaIm[gap_idx]
                if self.metadata is not None and 'frameRate' in self.metadata:
                    expected_frame_duration = 1.0 / float(self.metadata['frameRate'])
                else:
                    expected_frame_duration = 0.0333  # default 30 fps
                gap_length = int(np.round(gap_duration / expected_frame_duration))
                print(f"{gap_length - 1} TTL event(s) missing between indices {gap_idx} and {gap_idx + 1}.")
                
                # Interpolate estimated event times
                estimated_event_times = np.linspace(tCaIm[gap_idx], tCaIm[gap_idx+1], gap_length + 1)
                tCaIm = np.insert(tCaIm, gap_idx + 1, estimated_event_times[1:-1])
                low_confidence_periods = np.append(low_confidence_periods, [[gap_idx, gap_idx + gap_length]], axis=0)
        else:
            print("Gaps were found. Review tCaIm before proceeding or set fix_TTL_gaps=True.")
            sys.exit()
            
        # Optional: drop TTLs according to analysis parameters
        if delete_TTLs and self.analysis_params and self.analysis_params.get('indices of TTL events to delete') is not None:
            indices_to_delete = self.analysis_params['indices of TTL events to delete']
            if len(indices_to_delete) > 0:
                print(f"Deleting the following annotated dropped TTL indices: {indices_to_delete}")
                tCaIm = np.delete(tCaIm, indices_to_delete)
                
        return tCaIm, low_confidence_periods
