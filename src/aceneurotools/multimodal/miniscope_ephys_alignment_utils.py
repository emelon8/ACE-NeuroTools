from typing import TYPE_CHECKING

import numpy as np

from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
from aceneurotools.shared.exceptions import DataFormatError
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
        ttl_label_pattern = 'TTL Input on AcqSystem1_0 board 0 port 1 value (0x0001)'
        ttl_label_pattern_off = 'TTL Input on AcqSystem1_0 board 0 port 0 value (0x0000)'

        # Remove BOTH on and off pulses if they exist, assuming port 0 and 1 are used
        frame_acq_idx = np.char.startswith(channel.events['labels'].astype(str), 'TTL Input')
        experiment_event_idx = np.invert(frame_acq_idx)
        channel.events['labels'] = channel.events['labels'][experiment_event_idx]
        channel.events['timestamps'] = channel.events['timestamps'][experiment_event_idx]

    return tCaIm, low_confidence_periods, channel, miniscope_dm


def _correct_tCaIm(
    event_labels: np.ndarray,
    tCaIm: np.ndarray,
    low_confidence_periods: np.ndarray,
    miniscope_dm: 'MiniscopeDataManager',
    threshold: float = 0.065,
    fix_TTL_gaps: bool = False
) -> tuple[np.ndarray, np.ndarray, 'MiniscopeDataManager']:
    """This method first confirms that the TTL events alternate and then checks for missing TTL events. If there are any, the method guesses their timing and inserts them into the calcium imaging time vector.
    event_labels is the array of imported Neuralynx event labels.
    THRESHOLD is the time threshold, in seconds, for detecting gaps in the TTL events."""
    print('Checking that TTL events alternate...')
    # Print a message if the TTL event labels do not alternate between HIGH and LOW
    alternating = []
    for q in range(0,len(event_labels)-2):
        alternating.append(np.char.equal(event_labels[q+2], event_labels[q]))
    alternating.append(np.char.not_equal(event_labels[-1], event_labels[-2]))
    if sum(alternating) != (len(event_labels) - 1):
        print('TTL does not alternate!')
        raise DataFormatError(
            "TTL events do not alternate between HIGH and LOW as expected.",
            stage="_correct_tCaIm",
            hint="Inspect the raw TTL event labels for unexpected sequences.",
        )

    print('Finding any gaps in the TTL events...')
    dtCaIm = np.diff(tCaIm)
    idx_TTL_gap = np.where(dtCaIm > threshold)[0] # indices of gaps in the TTL events
    if len(idx_TTL_gap) == 0:
        print('No gaps were found with a threshold of ' + str(threshold*1000) + ' ms.')
    elif fix_TTL_gaps:
        print('Fixing any gaps in the TTL events...')
        flippedidx_TTL_gap = np.flip(idx_TTL_gap) # Reverse the order of idx_TTL_gap so that inserting TTLs in the loop doesn't affect the indices of the next iteration of the loop.
        gap_length = [] # number dropped frames per index
        for k, gap_idx in enumerate(flippedidx_TTL_gap):
            frame_rate = float(miniscope_dm.metadata.get('frameRate', 30.0)) if miniscope_dm.metadata else 30.0
            gap_length.append(int(np.round(dtCaIm[gap_idx]/(1/frame_rate)))) # Guesses how many timesteps occur in the gap. E.g., a 30 Hz video with a gap of 67 ms will have 2 timesteps in the gap.
            print(str(gap_length[k]-1) + ' TTL event(s) is/are missing between index numbers ' + str(gap_idx) + ' and ' + str(gap_idx + 1) + '.')
            estimated_event_times = np.linspace(tCaIm[gap_idx], tCaIm[gap_idx+1], gap_length[k]+1) # Estimates the timing of the TTLs, beginning at the one before the gap and ending at the one after the gap.
            tCaIm = np.insert(tCaIm, gap_idx+1, estimated_event_times[1:-1])
            low_confidence_periods = np.append(low_confidence_periods, [[gap_idx, gap_idx+gap_length[k]]], axis=0)
    else:
        raise DataFormatError(
            "Gaps were found in TTL events. Review tCaIm before proceeding.",
            stage="_correct_tCaIm",
            hint="Pass fix_TTL_gaps=True to interpolate missing TTL pulses automatically.",
        )

    return tCaIm, low_confidence_periods, miniscope_dm


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

    # Match up all calcium movie timestamps with their corresponding ephys timestamps.
    if all_TTL_events:
        print('Finding the indices of ephys timestamps that are closest to all calcium movie frame acquisition TTL events...')
        ephys_idx_all_TTL_events = np.empty(len(tCaIm),dtype=int)
        # Choose a number of indices after the last_index before which you are confident that the next index will be.
        # I am choosing the number of ephys indices during the time it takes for two calcium imaging frames.
        endPoint = round(int(channel.sampling_rate) * 2 / int(frame_rate))
        last_index = 0

        for k, CaIm_TTL_Event in enumerate(tCaIm):
            if k == 0:
                ephys_idx_all_TTL_events[k] = np.abs(channel.time_vector[last_index:] - CaIm_TTL_Event).argmin() + last_index
            elif len(channel.time_vector[last_index:]) - endPoint < 0:
                ephys_idx_all_TTL_events[k] = np.abs(channel.time_vector[last_index:] - CaIm_TTL_Event).argmin() + last_index
            else:
                ephys_idx_all_TTL_events[k] = np.abs(channel.time_vector[last_index:(last_index + endPoint)] - CaIm_TTL_Event).argmin() + last_index
            last_index = ephys_idx_all_TTL_events[k]

    # Look for the indices of the ephys timestamps that are closest to the calcium event (Neuralynx) timestamps.
    if ca_events_idx:
        print('Finding the indices of ephys timestamps that are closest to the calcium event (Neuralynx) timestamps...')
        ephys_idx_ca_events_res = {}
        for k in list(ca_events_idx.keys()):
            temp_list = []
            last_index = 0
            for j in range(len(ca_events_idx[k])):
                idx = np.abs(channel.time_vector[last_index:] - tCaIm[ca_events_idx[k][j]]).argmin() + last_index
                temp_list.append(idx)
                # Check to see if the gap between the calcium event time and the corresponding ephys timestamp is reasonable (within 1 frame's timestep).
                if np.abs(channel.time_vector[idx]-tCaIm[ca_events_idx[k][j]]) > (1/frame_rate):
                    # print('There are no ephys timestamps closer to the calcium event timestamp than the duration of a calcium movie frame!')
                    pass
                last_index = idx
            ephys_idx_ca_events_res[k] = np.array(temp_list)

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

