"""Lightweight ephys loading function for use by higher-level modules.

This module lives at the ``ephys/`` layer so that ``multimodal/`` can import
ephys-loading logic without creating a cross-layer dependency on ``pipelines/``.

``pipelines/ephys.py`` delegates to :func:`load_ephys_for_analysis` so the
pipeline remains a thin CLI wrapper with no duplicated logic.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aceneurotools.shared.file_downloader as file_downloader
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.shared.exceptions import DataNotFoundError, PipelineExecutionError
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager


def load_ephys_for_analysis(
    line_num: int,
    project_path: str | Path,
    data_path: str | Path | None,
    channel_names: list[str],
    filter_type: str | None = None,
    filter_range: list[float] = [0.5, 4.0],
    remove_artifacts: bool = False,
    logging_level: str | int = "CRITICAL",
) -> EphysDataManager:
    """Load and optionally filter ephys channels without CLI/pipeline overhead.

    This function encapsulates the core data-loading logic shared by
    :meth:`~aceneurotools.pipelines.ephys.EphysPipeline.run` and
    :meth:`~aceneurotools.pipelines.ephys.EphysPipeline.run_multiple_channels`.
    It performs a **single** disk read regardless of how many channels are
    requested, which is important for multi-GB recordings.

    Steps performed:
        1. Load experiment metadata via :class:`~aceneurotools.shared.experiment_data_manager.ExperimentDataManager`.
        2. Verify the ephys data file is present via
           :func:`~aceneurotools.shared.file_downloader.verify_file_by_line`.
        3. Construct an :class:`~aceneurotools.ephys.ephys_data_manager.EphysDataManager`
           via its factory and import the ephys block.
        4. Process all requested *channel_names* from the block in one pass.
        5. Apply bandpass filtering to each channel if *filter_type* is not ``None``.

    Args:
        line_num: Experiment row in ``experiments.csv``.
        project_path: Directory containing ``experiments.csv``.
        data_path: Base directory for raw experimental data.  Uses the value
            from ``experiments.csv`` when ``None``.
        channel_names: One or more channel names to load.  All names must
            appear in the recording file.  A single disk read covers all of
            them, so prefer passing multiple names over calling this function
            once per channel.
        filter_type: Filter family (``'butter'``, ``'fir'``) or ``None`` to
            skip filtering.
        filter_range: ``[low_hz, high_hz]`` bandpass cutoffs.
        remove_artifacts: If ``True``, apply Hann-window artifact removal.
        logging_level: Python logging level string or integer.

    Returns:
        An :class:`~aceneurotools.ephys.ephys_data_manager.EphysDataManager` with
        all requested channels loaded and (optionally) filtered.  Access
        individual channels via ``ephys_dm.get_channel(name)``.

    Raises:
        :class:`~aceneurotools.shared.exceptions.DataNotFoundError`: If project
            metadata files are missing.
        :class:`~aceneurotools.shared.exceptions.PipelineExecutionError`: On any
            loading, processing, or filtering failure.
        ValueError: If the ephys directory cannot be determined from metadata.
    """
    project_path = Path(project_path)
    data_path = Path(data_path) if data_path is not None else None

    logger = logging.getLogger(__name__)
    logger.setLevel(logging_level)

    # 1. Load experiment metadata
    try:
        experiment_data_manager = ExperimentDataManager(
            line_num,
            project_path=project_path,
            data_path=data_path,
            logging_level=logging_level,
        )
    except FileNotFoundError as exc:
        raise DataNotFoundError(
            "Project metadata files were not found.",
            stage="load_ephys_for_analysis:load_experiment_metadata",
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            hint="Ensure project_path points to a directory containing experiments.csv.",
        ) from exc
    except Exception as exc:
        raise PipelineExecutionError(
            "Failed to initialise ExperimentDataManager.",
            stage="load_ephys_for_analysis:load_experiment_metadata",
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            hint="Check metadata formatting and path configuration.",
        ) from exc

    ephys_directory = experiment_data_manager.get_ephys_directory()

    # 2. Verify data file presence
    experiments_csv = experiment_data_manager.project_path / "experiments.csv"
    try:
        file_downloader.verify_file_by_line(
            line_num=line_num,
            csv_path=experiments_csv,
            do_type="ephys",
            base_file_path=experiment_data_manager.data_path,
        )
    except Exception as exc:
        raise PipelineExecutionError(
            "Ephys data verification failed.",
            stage="load_ephys_for_analysis:verify_ephys_data",
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            hint="Confirm ephys files are present and accessible from metadata paths.",
        ) from exc

    if ephys_directory is None:
        raise ValueError(
            f"Ephys directory could not be determined from experiment metadata for line {line_num}."
        )

    # 3 & 4. Create data manager, import block, process all requested channels
    try:
        ephys_dm = EphysDataManager.create(
            ephys_directory=ephys_directory,
            auto_import_ephys_block=True,
            auto_process_block=False,
            auto_compute_phases=False,
        )
        ephys_dm.process_ephys_block_to_channels(
            channels=channel_names,
            remove_artifacts=remove_artifacts,
        )
    except Exception as exc:
        raise PipelineExecutionError(
            "Failed to import/process ephys block into channels.",
            stage="load_ephys_for_analysis:process_ephys_block",
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            hint="Verify ephys channel metadata and raw recording format compatibility.",
        ) from exc

    # 5. Apply filtering to each channel if requested
    if filter_type is not None:
        for ch_name in channel_names:
            logger.debug(f'Filtering ephys channel "{ch_name}" with {filter_type} filter at {filter_range} Hz')
            try:
                ephys_dm.filter_ephys(
                    ch_name,
                    ftype=str(filter_type),
                    cut=filter_range,
                    replace_signal=False,
                )
            except Exception as exc:
                raise PipelineExecutionError(
                    f"Ephys filtering failed for channel '{ch_name}'.",
                    stage="load_ephys_for_analysis:filter_ephys",
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    hint="Check filter_type/filter_range for valid values.",
                ) from exc

    return ephys_dm
