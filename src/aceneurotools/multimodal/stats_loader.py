"""
Lightweight data loader for ACE-NeuroTools statistical analyses.

Unlike the full :class:`~aceneurotools.pipelines.multimodal.MultimodalPipeline`,
this loader does **not** run motion correction, CNMF-E, or calcium event
detection.  It performs only the operations required to produce two
time-aligned signals at the miniscope frame rate:

1. Build a :class:`~aceneurotools.miniscope.miniscope_data_manager.MiniscopeDataManager`
   with ``auto_import_data=False`` to read frame-rate metadata and TTL events
   without loading any movie files.
2. Run :class:`~aceneurotools.pipelines.ephys.EphysPipeline` in silent mode to
   load and filter one (or two) ephys channels.
3. Synchronise timestamps via
   :func:`~aceneurotools.multimodal.miniscope_ephys_alignment_utils.sync_neuralynx_miniscope_timestamps`.
4. Downsample the ephys signal(s) to the miniscope frame rate via
   :func:`~aceneurotools.multimodal.miniscope_ephys_alignment_utils.find_ephys_idx_of_TTL_events`.
5. Optionally load mean-fluorescence ``.npz`` files produced by the
   :mod:`~aceneurotools.multimodal.time_projection_script`.

The returned objects are ready for the coherence and scatter analysis engines.

Typical use::

    from aceneurotools.multimodal.stats_loader import load_for_stats, load_calcium_signal

    channel_obj, miniscope_dm, fr = load_for_stats(
        line_num=97,
        project_path="/data/project",
        data_path="/data/raw",
        channel_name="CBvsPCEEG",
        freq_range=[0.5, 4.0],
    )
    calcium = load_calcium_signal(miniscope_dm, "/data/meanFluorescence", 97)
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np

import aceneurotools.miniscope.onix_miniscope_data_manager  # noqa: F401 — registers OnixMiniscopeDataManager
import aceneurotools.miniscope.ucla_data_manager  # noqa: F401 — registers UCLADataManager
from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.ephys_loader import load_ephys_for_analysis
from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
from aceneurotools.multimodal.miniscope_ephys_alignment_utils import (
    find_ephys_idx_of_TTL_events,
    sync_neuralynx_miniscope_timestamps,
)
from aceneurotools.shared.exceptions import PipelineExecutionError


def load_for_stats(
    line_num: int,
    project_path: str | Path,
    data_path: str | Path | None = None,
    channel_name: str = "CBvsPCEEG",
    freq_range: list[float] | None = None,
    delete_TTLs: bool = True,
    fix_TTL_gaps: bool = True,
    only_experiment_events: bool = True,
) -> tuple[Channel, MiniscopeDataManager, float]:
    """Load and synchronise a single ephys channel for statistical analysis.

    The returned channel object's ``.signal`` has been downsampled to the
    miniscope frame rate via TTL-event indexing.  Its ``.sampling_rate`` is
    updated to match ``fr``.

    Args:
        line_num: Experiment row in ``experiments.csv``.
        project_path: Directory containing ``experiments.csv``.
        data_path: Base directory for raw data.  Uses the value in
            ``experiments.csv`` when ``None``.
        channel_name: Ephys channel to load (e.g. ``'CBvsPCEEG'``).
        freq_range: ``[lowcut, highcut]`` bandpass for the ephys channel.
            Defaults to ``[0.5, 4.0]`` Hz.
        delete_TTLs: Remove dropped-frame TTL events listed in
            ``analysis_parameters.csv``.
        fix_TTL_gaps: Interpolate timestamps for missing TTL events.
        only_experiment_events: Strip TTL events from the channel event list,
            keeping only experiment events.

    Returns:
        ``(channel_object, miniscope_dm, fr)`` where *channel_object* carries
        the downsampled ephys signal, *miniscope_dm* is the metadata-only data
        manager used for TTL sync, and *fr* is the miniscope frame rate (Hz).

    Raises:
        :class:`~aceneurotools.shared.exceptions.PipelineExecutionError` on any
        loading or synchronisation failure.
    """
    if freq_range is None:
        freq_range = [0.5, 4.0]

    project_path = Path(project_path)
    data_path = Path(data_path) if data_path is not None else None

    # 1. Build a metadata-only MiniscopeDataManager (no movie loading)
    try:
        miniscope_dm = MiniscopeDataManager.create(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            auto_import_data=False,
            filenames=[],
        )
        fr: float = float(miniscope_dm.fr) if hasattr(miniscope_dm, "fr") and miniscope_dm.fr else 30.0
    except Exception as exc:
        raise PipelineExecutionError(
            f"Failed to create MiniscopeDataManager for line {line_num}.",
            stage="stats_loader_miniscope_dm",
            line_num=line_num,
            project_path=project_path,
            hint="Ensure the miniscope metadata files exist in the data directory.",
        ) from exc

    # 2. Load ephys via the ephys-layer loader (no pipelines/ import needed)
    try:
        ephys_dm = load_ephys_for_analysis(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            channel_names=[channel_name],
            filter_type=None,
            filter_range=freq_range,
            remove_artifacts=False,
            logging_level="CRITICAL",
        )
    except Exception as exc:
        raise PipelineExecutionError(
            f"load_ephys_for_analysis failed for line {line_num}, channel '{channel_name}'.",
            stage="stats_loader_ephys_pipeline",
            line_num=line_num,
            project_path=project_path,
            hint="Check that the ephys data files are present and the channel name is correct.",
        ) from exc

    channel_obj = ephys_dm.get_channel(channel_name)

    # 3. TTL timestamp synchronisation
    try:
        t_ca_im, _low_conf, channel_obj, miniscope_dm = sync_neuralynx_miniscope_timestamps(
            channel_obj,
            miniscope_dm,
            ephys_dm,
            delete_TTLs=delete_TTLs,
            fix_TTL_gaps=fix_TTL_gaps,
            only_experiment_events=only_experiment_events,
        )
    except Exception as exc:
        raise PipelineExecutionError(
            f"TTL timestamp sync failed for line {line_num}.",
            stage="stats_loader_ttl_sync",
            line_num=line_num,
            project_path=project_path,
            hint="Verify TTL events exist in the ephys file and the miniscope metadata is complete.",
        ) from exc

    # 4. Downsample ephys signal to miniscope frame rate
    try:
        ephys_idx_all_ttl, _ = find_ephys_idx_of_TTL_events(
            t_ca_im,
            channel=channel_obj,
            frame_rate=fr,
            ca_events_idx=None,
            all_TTL_events=True,
        )
        channel_obj.signal = channel_obj.signal[ephys_idx_all_ttl]
        channel_obj.sampling_rate = np.array(fr)
    except Exception as exc:
        raise PipelineExecutionError(
            f"Ephys downsampling failed for line {line_num}.",
            stage="stats_loader_downsample",
            line_num=line_num,
            project_path=project_path,
            hint="Check that find_ephys_idx_of_TTL_events returned valid indices.",
        ) from exc

    # Replace any NaNs introduced during downsampling
    if np.any(np.isnan(channel_obj.signal)):
        warnings.warn(
            f"Line {line_num}: NaNs found in '{channel_name}' after downsampling — replacing with zeros.",
            stacklevel=2,
        )
        channel_obj.signal = np.nan_to_num(channel_obj.signal, nan=0.0)

    return channel_obj, miniscope_dm, fr


def load_for_stats_two_channels(
    line_num: int,
    project_path: str | Path,
    data_path: str | Path | None = None,
    channel_name_1: str = "PFCLFPvsCBEEG",
    channel_name_2: str = "PFCEEGvsCBEEG",
    freq_range: list[float] | None = None,
    delete_TTLs: bool = True,
    fix_TTL_gaps: bool = True,
    only_experiment_events: bool = True,
) -> tuple[Channel, Channel, MiniscopeDataManager, float]:
    """Load two ephys channels downsampled to the same TTL indices.

    Used for ephys-ephys coherence analysis where two channels from the same
    recording are compared.  Both channels are downsampled using the indices
    derived from *channel_name_1*.

    Args:
        line_num: Experiment row in ``experiments.csv``.
        project_path: Directory containing ``experiments.csv``.
        data_path: Base directory for raw data.
        channel_name_1: First ephys channel (also used for TTL sync).
        channel_name_2: Second ephys channel.
        freq_range: ``[lowcut, highcut]`` bandpass.
        delete_TTLs: Remove dropped-frame TTL events.
        fix_TTL_gaps: Interpolate missing TTL events.
        only_experiment_events: Strip TTL events from event list.

    Returns:
        ``(ch1, ch2, miniscope_dm, fr)`` — both channel signals are
        downsampled to the miniscope frame rate using the same TTL indices.
    """
    if freq_range is None:
        freq_range = [0.5, 4.0]

    project_path = Path(project_path)
    data_path = Path(data_path) if data_path is not None else None

    # Metadata-only miniscope DM for frame rate + TTL sync
    try:
        miniscope_dm = MiniscopeDataManager.create(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            auto_import_data=False,
            filenames=[],
        )
        fr = float(miniscope_dm.fr) if hasattr(miniscope_dm, "fr") and miniscope_dm.fr else 30.0
    except Exception as exc:
        raise PipelineExecutionError(
            f"Failed to create MiniscopeDataManager for line {line_num}.",
            stage="stats_loader_two_ch_miniscope_dm",
            line_num=line_num,
            project_path=project_path,
            hint="Ensure the miniscope metadata files exist in the data directory.",
        ) from exc

    # Load both channels from the recording block in a single disk read.
    try:
        ephys_dm = load_ephys_for_analysis(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            channel_names=[channel_name_1, channel_name_2],
            filter_type=None,
            filter_range=freq_range,
            remove_artifacts=False,
            logging_level="CRITICAL",
        )
    except Exception as exc:
        raise PipelineExecutionError(
            f"load_ephys_for_analysis failed for channels '{channel_name_1}'/'{channel_name_2}', line {line_num}.",
            stage="stats_loader_two_ch_ephys",
            line_num=line_num,
            hint="Check that the ephys data and channel names are correct.",
        ) from exc

    ch1 = ephys_dm.get_channel(channel_name_1)
    ch2 = ephys_dm.get_channel(channel_name_2)

    # TTL sync using channel 1
    try:
        t_ca_im, _low_conf, ch1, miniscope_dm = sync_neuralynx_miniscope_timestamps(
            ch1,
            miniscope_dm,
            ephys_dm,
            delete_TTLs=delete_TTLs,
            fix_TTL_gaps=fix_TTL_gaps,
            only_experiment_events=only_experiment_events,
        )
    except Exception as exc:
        raise PipelineExecutionError(
            f"TTL timestamp sync failed for line {line_num}.",
            stage="stats_loader_two_ch_ttl_sync",
            line_num=line_num,
            hint="Verify TTL events exist in the ephys file.",
        ) from exc

    # Downsample both channels with the same indices
    try:
        ephys_idx_all_ttl, _ = find_ephys_idx_of_TTL_events(
            t_ca_im,
            channel=ch1,
            frame_rate=fr,
            ca_events_idx=None,
            all_TTL_events=True,
        )
        ch1.signal = ch1.signal[ephys_idx_all_ttl]
        ch2.signal = ch2.signal[ephys_idx_all_ttl]
        ch1.sampling_rate = np.array(fr)
        ch2.sampling_rate = np.array(fr)
    except Exception as exc:
        raise PipelineExecutionError(
            f"Ephys downsampling failed for line {line_num}.",
            stage="stats_loader_two_ch_downsample",
            line_num=line_num,
            hint="Check that TTL indices are within bounds of both channel signals.",
        ) from exc

    for ch, name in [(ch1, channel_name_1), (ch2, channel_name_2)]:
        if np.any(np.isnan(ch.signal)):
            warnings.warn(
                f"Line {line_num}: NaNs in '{name}' after downsampling — replacing with zeros.",
                stacklevel=2,
            )
            ch.signal = np.nan_to_num(ch.signal, nan=0.0)

    return ch1, ch2, miniscope_dm, fr


def load_calcium_signal(
    miniscope_dm: MiniscopeDataManager,
    calcium_signal_dir: str | Path,
    line_num: int,
    npz_key: str = "meanFluorescence",
) -> np.ndarray | None:
    """Load mean-fluorescence time series from a pre-computed ``.npz`` file.

    The expected filename pattern is
    ``<calcium_signal_dir>/meanFluorescence_<line_num>.npz``, matching the
    output of :mod:`~aceneurotools.multimodal.time_projection_script`.

    Args:
        miniscope_dm: A MiniscopeDataManager; the loaded array is stored in
            ``miniscope_dm.mean_fluorescence_dict`` as a side-effect.
        calcium_signal_dir: Directory containing the ``.npz`` files.
        line_num: Experiment line number (used to construct the filename).
        npz_key: Key inside the ``.npz`` archive for the fluorescence array.

    Returns:
        1-D NumPy array of mean fluorescence values, or ``None`` if the file
        does not exist.
    """
    filepath = Path(calcium_signal_dir) / f"meanFluorescence_{line_num}.npz"
    if not filepath.exists():
        warnings.warn(
            f"Calcium signal file not found: {filepath}.  "
            "Run time_projection_script first, or check --calcium-signal-dir.",
            stacklevel=2,
        )
        return None

    data = np.load(filepath)
    if npz_key not in data:
        available = list(data.keys())
        warnings.warn(
            f"Key '{npz_key}' not found in {filepath}.  Available keys: {available}",
            stacklevel=2,
        )
        return None

    signal: np.ndarray = data[npz_key]
    miniscope_dm.mean_fluorescence_dict = data  # type: ignore[attr-defined]
    return signal
