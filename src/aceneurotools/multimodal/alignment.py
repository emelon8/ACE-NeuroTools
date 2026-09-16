from typing import TYPE_CHECKING

import numpy as np

from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
from aceneurotools.shared.path_finder import PathFinder

if TYPE_CHECKING:
    from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager


def sync_neuralynx_miniscope_timestamps(
    channel: Channel,
    miniscope_dm: 'MiniscopeDataManager',
    ephys_dm: EphysDataManager,
    delete_TTLs: bool = True,
    fix_TTL_gaps: bool = False,
    only_experiment_events: bool = True
) -> tuple[np.ndarray, np.ndarray, Channel, 'MiniscopeDataManager']:
    """Synchronize Neuralynx and miniscope timestamps.
    
    This is a legacy wrapper. It delegates to the new MiniscopeDataManager
    sync_timestamps architecture.
    
    Args:
        channel: Channel object containing ephys events.
        miniscope_dm: MiniscopeDataManager with frame info and analysis params.
        ephys_dm: EphysDataManager to extract TTLs from.
        delete_TTLs: If True, remove TTLs for dropped frames from analysis_params.
        fix_TTL_gaps: If True, interpolate missing TTL events.
        only_experiment_events: If True, remove TTL events from event list.
        
    Returns:
        Tuple of (tCaIm, low_confidence_periods, channel, miniscope_dm)
    """
    print('Syncing calcium movie times using Data Manager...')

    # Let the data managers handle TTL extraction and alignment natively
    tCaIm, low_confidence_periods = miniscope_dm.sync_timestamps(
        ephys_dm=ephys_dm,
        channel_name=channel.name,
        delete_TTLs=delete_TTLs,
        fix_TTL_gaps=fix_TTL_gaps
    )

    # Make an array of the Neuralynx events with the TTL events removed
    if only_experiment_events and isinstance(ephys_dm, NeuralynxDataManager):
        # Remove BOTH on and off pulses if they exist, assuming port 0 and 1 are used
        frame_acq_idx = np.char.startswith(channel.events['labels'].astype(str), 'TTL Input')
        experiment_event_idx = np.invert(frame_acq_idx)
        channel.events['labels'] = channel.events['labels'][experiment_event_idx]
        channel.events['timestamps'] = channel.events['timestamps'][experiment_event_idx]

    return tCaIm, low_confidence_periods, channel, miniscope_dm


def _nearest_sorted_index(sorted_values: np.ndarray, queries: np.ndarray) -> np.ndarray:
    """Return, for each query, the index of the nearest element in a sorted array.

    Vectorized nearest-neighbor via :func:`numpy.searchsorted` (O((N+M)) instead
    of a per-query scan). A query exactly between two samples resolves to the
    lower index, matching the first-occurrence tie-break of the previous
    ``np.abs(...).argmin()`` implementation. For monotonically increasing
    ``time_vector`` and query timestamps this yields identical indices to the
    old forward-scanning loop, while also removing its window-clamp artifact on
    large TTL gaps.
    """
    sorted_values = np.asarray(sorted_values)
    queries = np.asarray(queries)
    n = len(sorted_values)
    if n == 0:
        return np.empty(0, dtype=int)
    if n == 1:
        return np.zeros(len(queries), dtype=int)

    pos = np.searchsorted(sorted_values, queries)
    pos = np.clip(pos, 1, n - 1)
    left = sorted_values[pos - 1]
    right = sorted_values[pos]
    choose_left = (queries - left) <= (right - queries)
    return np.where(choose_left, pos - 1, pos).astype(int)


def find_ephys_idx_of_TTL_events(
    tCaIm: np.ndarray,
    channel: Channel,
    frame_rate: float,
    ca_events_idx: dict[int, np.ndarray] | None = None,
    all_TTL_events: bool = True
) -> tuple[np.ndarray | None, dict[int, np.ndarray] | None]:
    """Finds the index of a calcium event in the Neuralynx timespace. If the miniscope class method to find the timing of calcium events has not been run yet, it runs that first.
    CHANNEL is the ephys channel with which to compare the timing of the ephys samples to the calcium event timing."""
    ephys_idx_all_TTL_events: np.ndarray | None = None
    ephys_idx_ca_events_res: dict[int, np.ndarray] | None = None

    time_vector = np.asarray(channel.time_vector)
    tCaIm = np.asarray(tCaIm)

    # Match up all calcium movie timestamps with their corresponding ephys timestamps.
    if all_TTL_events:
        print('Finding the indices of ephys timestamps that are closest to all calcium movie frame acquisition TTL events...')
        ephys_idx_all_TTL_events = _nearest_sorted_index(time_vector, tCaIm)

    # Look for the indices of the ephys timestamps that are closest to the calcium event (Neuralynx) timestamps.
    if ca_events_idx:
        print('Finding the indices of ephys timestamps that are closest to the calcium event (Neuralynx) timestamps...')
        ephys_idx_ca_events_res = {}
        for k in list(ca_events_idx.keys()):
            event_frame_idx = np.asarray(ca_events_idx[k], dtype=int)
            ephys_idx_ca_events_res[k] = _nearest_sorted_index(time_vector, tCaIm[event_frame_idx])

    return ephys_idx_all_TTL_events, ephys_idx_ca_events_res


def find_ca_movie_frame_num_of_ephys_idx(
    channel: Channel,
    ephys_idx_all_TTL_events: np.ndarray
) -> np.ndarray:
    """Method to create an array the same size as obj.ephys[channel], where each element is the frame number of the corresponding calcium movie frame."""
    ca_frame_num_of_ephys_idx = np.zeros(np.shape(channel.signal),dtype=int)

    # Assign a frame number to each element of ca_frame_num_of_ephys_idx. I'm not sure if the sample of obj.ephys that's closest to the TTL event should be paired with the preceding frame or not.
    for k, i in enumerate(ephys_idx_all_TTL_events[1:]):
        ca_frame_num_of_ephys_idx[i:ephys_idx_all_TTL_events[k]:-1] = k+1

    return ca_frame_num_of_ephys_idx


def find_ca_movie_filenums(
    channel: Channel,
    ephys_idx_all_TTL_events: np.ndarray,
    miniscope_dm: 'MiniscopeDataManager',
    time_range: list[float] | None = None
) -> tuple[list[str], np.ndarray]:
    """Determine the calcium imaging movie file(s) that correspond to a specified time period (in seconds) in the electrophysiological signal.
    TIME_RANGE is a list specifing the boundaries of the time period.
    """
    if time_range == None:
        if miniscope_dm.analysis_params:
            periods = miniscope_dm.analysis_params.get('periods of high slow wave power (s)', [])
            if periods and isinstance(periods, list):
                time_sec_start = float(periods[0])
                time_sec_end = float(periods[-1])
            else:
                time_sec_start = 0.0
                time_sec_end = 0.0
        else:
            time_sec_start = 0.0
            time_sec_end = 0.0
    else:
        time_sec_start = time_range[0]
        time_sec_end = time_range[1]

    print('Finding the miniscope frames and movie corresponding to the specified time period...')
    movie_frames = np.zeros(2, dtype=int)
    movie_frames[0] = np.where(channel.time_vector[ephys_idx_all_TTL_events]>=time_sec_start)[0][0] # Start frame
    movie_frames[1] = np.where(channel.time_vector[ephys_idx_all_TTL_events]<=time_sec_end)[0][-1] # End frame
    frames_per_file = int(miniscope_dm.metadata.get('framesPerFile', 1000)) if miniscope_dm.metadata else 1000
    first_movie = int(movie_frames[0]/frames_per_file) # Truncates result to just the integer part
    last_movie = int(movie_frames[1]/frames_per_file) # Truncates result to just the integer part

    print('The first movie in the sequence is ' + str(first_movie) + '.avi.')
    print('The last movie in the sequence is ' + str(last_movie) + '.avi.')

    movie_range = tuple([str(x) for x in range(first_movie, last_movie+1)])
    cal_imaging_dir = str(miniscope_dm.metadata.get('calcium imaging directory', '')) if miniscope_dm.metadata else ''
    movie_file_paths_in_this_range = PathFinder.find(directory=cal_imaging_dir, suffix=".avi", prefix=movie_range, file_and_directory=False)

    # Ensure movie_file_paths_in_this_range is a list of strings
    if movie_file_paths_in_this_range is None:
        return [], movie_frames
    if isinstance(movie_file_paths_in_this_range, list):
        return [str(p) for p in movie_file_paths_in_this_range], movie_frames
    return [str(movie_file_paths_in_this_range)], movie_frames

