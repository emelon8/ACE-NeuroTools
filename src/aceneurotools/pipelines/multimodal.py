import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np

from aceneurotools.multimodal.miniscope_ephys_alignment_utils import (
    find_ca_movie_frame_num_of_ephys_idx,
    find_ephys_idx_of_TTL_events,
    sync_neuralynx_miniscope_timestamps,
)
from aceneurotools.multimodal.phase_utils import (
    ephys_phase_ca_events,
    miniscope_phase_ca_events,
    phase_ca_events_histogram,
)
from aceneurotools.pipelines.ephys import EphysPipeline
from aceneurotools.pipelines.miniscope import MiniscopePipeline
from aceneurotools.shared.cli_utils import (
    apply_headless_policy,
    build_run_params,
    run_allowed_keys,
    validate_run_params,
)
from aceneurotools.shared.config_utils import load_analysis_params
from aceneurotools.shared.exceptions import AceNeuroError, PipelineExecutionError, print_cli_error


class MultimodalPipeline:
    """Orchestrates ephys + miniscope analysis and multimodal alignment.

    After :meth:`run`, these instance attributes are populated (``None`` if a
    stage did not apply):

    - :attr:`ephys_pipeline` — :class:`EphysPipeline` instance used for this run
    - :attr:`miniscope_pipeline` — :class:`MiniscopePipeline` instance used
    - :attr:`t_ca_im` — aligned calcium frame times from TTL sync
    - :attr:`low_confidence_periods` — sync quality mask from alignment
    - :attr:`ephys_idx_all_TTL_events` — ephys sample indices for TTL events
    - :attr:`ephys_idx_ca_events` — ephys indices at calcium events (if ``ca_events``)
    - :attr:`ca_frame_num_of_ephys_idx` — per-frame mapping (if TTL indices exist)
    - :attr:`ca_events_phases_ephys` — phase samples for CA events (ephys band)
    - :attr:`ca_events_phases_miniscope` — phase samples for CA events (miniscope)
    - :attr:`phase_hist_ephys` / :attr:`phase_bin_edges_ephys` — histogram of ephys phases
    - :attr:`phase_hist_miniscope` / :attr:`phase_bin_edges_miniscope` — histogram of miniscope phases
    """

    def __init__(self) -> None:
        self.miniscope_pipeline = MiniscopePipeline()
        self.ephys_pipeline = EphysPipeline()
        self.t_ca_im: np.ndarray | None = None
        self.low_confidence_periods: Any = None
        self.ephys_idx_all_TTL_events: Any = None
        self.ephys_idx_ca_events: Any = None
        self.ca_frame_num_of_ephys_idx: Any = None
        self.ca_events_phases_ephys: Any = None
        self.ca_events_phases_miniscope: Any = None
        self.phase_hist_ephys: Any = None
        self.phase_bin_edges_ephys: Any = None
        self.phase_hist_miniscope: Any = None
        self.phase_bin_edges_miniscope: Any = None

    def run(
        self,
        line_num: int,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        # ephys parameters
        channel_name: str = 'PFCLFPvsCBEEG',
        remove_artifacts: bool = False,
        filter_type: str | None = None,
        filter_range: list[float] = [0.5, 4],
        plot_channel: bool = False,
        plot_spectrogram: bool = False,
        plot_phases: bool = False,
        logging_level: str = "CRITICAL",

        # miniscope parameters
        miniscope_filenames: list[str] = [],
        # preprocessing parameters
        crop: bool = True,
        crop_coords: list[int] | tuple[int, int, int, int] | None = None,
        detrend_method: str = 'median',
        df_over_f: bool = False,
        # if df_over_f = True
        secs_window: float = 5,
        quantile_min: float = 8,
        df_over_f_method: str = 'delta_f_over_sqrt_f',

        # processing parameters
        parallel: bool = False,
        n_processes: int = 6,
        apply_motion_correction: bool = True,
        inspect_motion_correction: bool = True,
        plot_params: bool = False,
        run_CNMFE: bool = True,
        save_estimates: bool = True,
        save_CNMFE_estimates_filename: str = 'estimates.hdf5',
        save_CNMFE_params: bool = False,

        # post-processing parameters
        remove_components_with_gui: bool = True,
        find_calcium_events: bool = True,
        derivative_for_estimates: str = 'first',
        event_height: float = 5,
        compute_miniscope_phase: bool = True,
        filter_miniscope_data: bool = True,
        n: int = 2,
        cut: list[float] = [0.1, 1.5],
        ftype: str = 'butter',
        btype: str = 'bandpass',
        inline: bool = False,
        compute_miniscope_spectrogram: bool = True,
        window_length: float = 30,
        window_step: float = 3,
        freq_lims: list[float] = [0, 15],
        time_bandwidth: float = 2,

        # multimodal parameters
        delete_TTLs: bool = True,
        fix_TTL_gaps: bool = False,
        only_experiment_events: bool = True,
        all_TTL_events: bool = True,
        ca_events: bool = False,
        time_range: list[float] | None = None,
        headless: bool = False
    ) -> None:
        """Run the complete multimodal analysis pipeline.

        Executes both ephys and miniscope pipelines, synchronizes their
        timestamps via TTL events, and performs phase-locked calcium event
        analysis.

        Args:
            line_num: Experiment line number in experiments.csv.
            channel_name: Ephys channel name to analyze.
            remove_artifacts: If True, remove ephys artifacts.
            filter_type: Ephys filter type ('butter', 'fir') or None.
            filter_range: [low, high] bandpass cutoffs for ephys.
            plot_channel: If True, plot ephys time series.
            plot_spectrogram: If True, plot ephys spectrogram.
            plot_phases: If True, plot phase histograms.
            logging_level: Verbosity level.
            miniscope_filenames: List of movie files to load.
            crop: If True, crop the movie.
            crop_coords: Crop coordinates as (x0, y0, x1, y1) tuple/list.
                If None, reads from analysis_parameters.csv or opens the GUI.
            detrend_method: 'median' or 'linear' detrending.
            df_over_f: If True, compute DF/F.
            parallel: If True, use multiprocessing.
            n_processes: Number of parallel processes.
            apply_motion_correction: If True, correct motion.
            run_CNMFE: If True, run source extraction.
            delete_TTLs: If True, remove dropped frame TTLs.
            fix_TTL_gaps: If True, interpolate missing TTLs.
            only_experiment_events: If True, keep only experiment events.
            all_TTL_events: If True, process all TTL events.
            ca_events: If True, include calcium event analysis.
            time_range: Optional [start, end] time range to analyze.
            headless: If True, disable all GUI interactions.
        """
        self.t_ca_im = None
        self.low_confidence_periods = None
        self.ephys_idx_all_TTL_events = None
        self.ephys_idx_ca_events = None
        self.ca_frame_num_of_ephys_idx = None
        self.ca_events_phases_ephys = None
        self.ca_events_phases_miniscope = None
        self.phase_hist_ephys = None
        self.phase_bin_edges_ephys = None
        self.phase_hist_miniscope = None
        self.phase_bin_edges_miniscope = None

        self.ephys_pipeline = EphysPipeline()
        try:
            self.ephys_pipeline.run(
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                channel_name=channel_name,
                remove_artifacts=remove_artifacts,
                filter_type=filter_type,
                filter_range=filter_range,
                plot_channel=plot_channel,
                plot_spectrogram=plot_spectrogram,
                plot_phases=plot_phases,
                logging_level=logging_level,
                headless=headless,
            )
        except Exception as e:
            raise PipelineExecutionError(
                "Multimodal run failed during ephys sub-pipeline.",
                stage="run_ephys_pipeline",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Check ephys input paths and channel parameters before multimodal sync.",
            ) from e

        self.miniscope_pipeline = MiniscopePipeline()
        try:
            self.miniscope_pipeline.run(
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                filenames=miniscope_filenames,
                crop=crop,
                crop_coords=crop_coords,
                detrend_method=detrend_method,
                df_over_f=df_over_f,
                secs_window=secs_window,
                quantile_min=quantile_min,
                df_over_f_method=df_over_f_method,
                parallel=parallel,
                n_processes=n_processes,
                apply_motion_correction=apply_motion_correction,
                inspect_motion_correction=inspect_motion_correction,
                plot_params=plot_params,
                run_CNMFE=run_CNMFE,
                save_estimates=save_estimates,
                save_CNMFE_estimates_filename=save_CNMFE_estimates_filename,
                save_CNMFE_params=save_CNMFE_params,
                remove_components_with_gui=remove_components_with_gui,
                find_calcium_events=find_calcium_events,
                derivative_for_estimates=derivative_for_estimates,
                event_height=event_height,
                compute_miniscope_phase=compute_miniscope_phase,
                filter_miniscope_data=filter_miniscope_data,
                n=n,
                cut=cut,
                ftype=ftype,
                btype=btype,
                inline=inline,
                compute_miniscope_spectrogram=compute_miniscope_spectrogram,
                window_length=window_length,
                window_step=window_step,
                freq_lims=freq_lims,
                time_bandwidth=time_bandwidth,
                headless=headless,
            )
        except Exception as e:
            raise PipelineExecutionError(
                "Multimodal run failed during miniscope sub-pipeline.",
                stage="run_miniscope_pipeline",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Check miniscope inputs and CNMF-E parameters before multimodal sync.",
            ) from e

        channel_object = self.ephys_pipeline.ephys_data_manager.get_channel(channel_name)
        frame_rate = self.miniscope_pipeline.miniscope_data_manager.fr
        ca_events_idx = self.miniscope_pipeline.miniscope_data_manager.ca_events_idx
        miniscope_phases = self.miniscope_pipeline.miniscope_data_manager.miniscope_phases

        try:
            t_ca_im, low_confidence_periods, channel_object, miniscope_dm = sync_neuralynx_miniscope_timestamps(
                channel_object,
                self.miniscope_pipeline.miniscope_data_manager,
                self.ephys_pipeline.ephys_data_manager,
                delete_TTLs=delete_TTLs,
                fix_TTL_gaps=fix_TTL_gaps,
                only_experiment_events=only_experiment_events,
            )
        except Exception as e:
            raise PipelineExecutionError(
                "Timestamp synchronization failed in multimodal pipeline.",
                stage="sync_timestamps",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Validate TTL events and ensure both pipelines produced aligned timing metadata.",
            ) from e

        print("\nSuccess! Setting changed variables.")
        self.miniscope_pipeline.miniscope_data_manager = miniscope_dm
        self.ephys_pipeline.ephys_data_manager.channels[channel_name] = channel_object

        self.t_ca_im = t_ca_im
        self.low_confidence_periods = low_confidence_periods

        try:
            ephys_idx_all_TTL_events, ephys_idx_ca_events = find_ephys_idx_of_TTL_events(
                t_ca_im,
                channel_object,
                frame_rate,
                all_TTL_events=all_TTL_events,
                ca_events_idx=ca_events_idx if ca_events else None,
            )
        except Exception as e:
            raise PipelineExecutionError(
                "Failed to map TTL events into ephys indices.",
                stage="map_ttl_to_ephys_indices",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Check frame-rate metadata and TTL event quality.",
            ) from e
        self.ephys_idx_all_TTL_events = ephys_idx_all_TTL_events
        self.ephys_idx_ca_events = ephys_idx_ca_events

        if ephys_idx_all_TTL_events is not None:
            self.ca_frame_num_of_ephys_idx = find_ca_movie_frame_num_of_ephys_idx(channel_object, ephys_idx_all_TTL_events)

        if ephys_idx_ca_events is not None:
            try:
                self.ca_events_phases_ephys = ephys_phase_ca_events(ephys_idx_ca_events, channel_object, neurons='all')
                self.ca_events_phases_miniscope = miniscope_phase_ca_events(ca_events_idx, miniscope_phases, neurons='all')
            except Exception as e:
                raise PipelineExecutionError(
                    "Failed to compute event-locked phases.",
                    stage="compute_phase_locked_events",
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    hint="Ensure phase arrays and calcium event indices are valid and non-empty.",
                ) from e

        hist1, bin_edges1 = None, None
        hist2, bin_edges2 = None, None

        if ephys_idx_ca_events is not None:
            if self.ca_events_phases_ephys is not None:
                res1 = phase_ca_events_histogram(self.ca_events_phases_ephys)
                hist1, bin_edges1 = res1[0], res1[1]

            if self.ca_events_phases_miniscope is not None:
                res2 = phase_ca_events_histogram(self.ca_events_phases_miniscope)
                hist2, bin_edges2 = res2[0], res2[1]

        self.phase_hist_ephys = hist1
        self.phase_bin_edges_ephys = bin_edges1
        self.phase_hist_miniscope = hist2
        self.phase_bin_edges_miniscope = bin_edges2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Multimodal Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with explicit project path
  python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project

  # Run in headless mode (no GUI) for batch processing
  python -m aceneurotools.pipelines.multimodal --line-num 97 --project-path /path/to/project --headless
"""
    )
    parser.add_argument('--line-num', type=int, required=True,
                        help="Experiment line number from experiments.csv")
    parser.add_argument('--project-path', type=str, required=True,
                        help="Path to project directory (containing experiments.csv)")
    parser.add_argument('--data-path', type=str,
                        help="Base path for raw experimental data")
    parser.add_argument('--headless', action='store_true',
                        help="Run in headless mode (no GUI)")

    args = parser.parse_args()

    # Default parameters
    defaults = {
        # ephys parameters
        'channel_name': 'PFCLFPvsCBEEG',
        'remove_artifacts': False,
        'filter_type': None,
        'filter_range': [0.5, 4],
        'plot_channel': False,
        'plot_spectrogram': False,
        'plot_phases': False,
        'logging_level': "CRITICAL",

        # miniscope parameters
        'miniscope_filenames': ['0.avi'],
        # preprocessing parameters
        'crop': True,
        'detrend_method': 'linear',
        'df_over_f': True,
        'secs_window': 5,
        'quantile_min': 8,
        'df_over_f_method': 'delta_f_over_sqrt_f',
        # processing parameters
        'parallel': False,
        'n_processes': 6,
        'apply_motion_correction': True,
        'inspect_motion_correction': True,
        'plot_params': False,
        'run_CNMFE': True,
        'save_estimates': False,
        'save_CNMFE_estimates_filename': 'estimates.hdf5',
        'save_CNMFE_params': False,
        # post-processing parameters
        'remove_components_with_gui': True,
        'find_calcium_events': True,
        'derivative_for_estimates': 'first',
        'event_height': 5,
        'compute_miniscope_phase': True,
        'filter_miniscope_data': True,
        'n': 2,
        'cut': [0.1, 1.5],
        'ftype': 'butter',
        'btype': 'bandpass',
        'inline': False,
        'compute_miniscope_spectrogram': False,
        'window_length': 30,
        'window_step': 3,
        'freq_lims': [0, 15],
        'time_bandwidth': 2,
        # multimodal parameters
        'delete_TTLs': True,
        'fix_TTL_gaps': True,
        'only_experiment_events': False,
        'all_TTL_events': True,
        'ca_events': True,
        'time_range': None
    }

    run_params = build_run_params(
        defaults=defaults,
        allowed_keys=run_allowed_keys(MultimodalPipeline.run),
        line_num=args.line_num,
        project_path=args.project_path,
        data_path=args.data_path,
        headless=args.headless,
        csv_loader=load_analysis_params,
    )
    apply_headless_policy(pipeline_name="multimodal", run_params=run_params)
    validate_run_params(pipeline_name="multimodal", run_params=run_params)

    api = MultimodalPipeline()
    try:
        api.run(**run_params)
    except (AceNeuroError, FileNotFoundError, ValueError) as e:
        print_cli_error(e, include_cause=args.headless)
        if args.headless:
            sys.exit(1)
        raise
