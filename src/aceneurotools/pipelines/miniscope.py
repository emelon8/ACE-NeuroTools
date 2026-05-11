
import argparse
import sys
import tkinter
from pathlib import Path

from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
from aceneurotools.miniscope.miniscope_postprocessor import MiniscopePostprocessor
from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from aceneurotools.miniscope.miniscope_processor import MiniscopeProcessor
from aceneurotools.miniscope.pipeline_results import (
    PostprocessConfig,
    PostprocessingResult,
    PreprocessConfig,
    PreprocessingResult,
    ProcessConfig,
    ProcessingResult,
)
from aceneurotools.shared.cli_utils import (
    apply_headless_policy,
    build_run_params,
    run_allowed_keys,
    validate_run_params,
)
from aceneurotools.shared.exceptions import (
    AceNeuroError,
    DataNotFoundError,
    PipelineExecutionError,
    print_cli_error,
)
from aceneurotools.shared.misc_functions import get_coords_dict_from_analysis_params, update_csv_cell


class MiniscopePipeline:
    """High-level API for calcium imaging analysis workflows.
    
    Orchestrates the complete miniscope analysis pipeline from raw video
    through CNMF-E source extraction and post-processing. Designed for
    non-technical users with sensible defaults.
    
    Attributes:
        miniscope_data_manager: Data manager populated after run().
        preprocessor: MiniscopePreprocessor instance.
        processor: MiniscopeProcessor instance.
        postprocessor: MiniscopePostprocessor instance.
    """

    miniscope_data_manager: MiniscopeDataManager
    preprocessor: MiniscopePreprocessor
    processor: MiniscopeProcessor
    postprocessor: MiniscopePostprocessor

    # Structured result objects — set after each stage completes.
    preprocessing_result: PreprocessingResult
    processing_result: ProcessingResult
    postprocessing_result: PostprocessingResult

    def __init__(self) -> None:
        """Initialize the MiniscopePipeline."""
        pass

    def run(
        self,
        line_num: int,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        filenames: list[str] = [],

        # preprocessing parameters
        crop: bool = True,
        crop_coords: list[int] | tuple[int, int, int, int] | None = None,
        detrend_method: str | None = 'median',
        df_over_f: bool = False,
        # if df_over_f = True
        secs_window: float = 5,
        quantile_min: float = 8,
        df_over_f_method: str = 'delta_f_over_sqrt_f',

        # processing parameters
        parallel: bool = False,
        n_processes: int = 12,
        apply_motion_correction: bool = False,
        inspect_motion_correction: bool = False,
        plot_params: bool = False,
        run_CNMFE: bool = False,
        save_estimates: bool = True,
        save_CNMFE_estimates_filename: str = 'estimates.hdf5',
        save_CNMFE_params: bool = False,

        # post processing parameters
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
        headless: bool = False
    ) -> None:
        """Run the complete miniscope analysis pipeline.

        Executes preprocessing (crop, detrend, DF/F), processing (motion
        correction, CNMF-E), and post-processing (component selection,
        event detection, spectral analysis) in sequence.

        After this method returns, structured results are available as:
          - ``self.preprocessing_result`` (:class:`~aceneurotools.miniscope.pipeline_results.PreprocessingResult`)
          - ``self.processing_result``    (:class:`~aceneurotools.miniscope.pipeline_results.ProcessingResult`)
          - ``self.postprocessing_result`` (:class:`~aceneurotools.miniscope.pipeline_results.PostprocessingResult`)

        Note:
            For programmatic use, prefer :meth:`run_with_configs` which accepts
            :class:`~aceneurotools.miniscope.pipeline_results.PreprocessConfig`,
            :class:`~aceneurotools.miniscope.pipeline_results.ProcessConfig`, and
            :class:`~aceneurotools.miniscope.pipeline_results.PostprocessConfig`
            dataclasses instead of 30+ individual keyword arguments.

        Args:
            line_num: Experiment line number in experiments.csv.
            filenames: List of movie filenames to load (e.g., ['0.avi']).
            crop: If True, crop the movie.
            crop_coords: Crop coordinates as (x0, y0, x1, y1) tuple/list.
                If None, reads from analysis_parameters.csv or opens the GUI.
            detrend_method: 'median' or 'linear' for photobleaching correction.
            df_over_f: If True, compute DF/F normalization.
            secs_window: Window size for DF/F baseline estimation.
            quantile_min: Percentile for DF/F baseline.
            df_over_f_method: 'delta_f_over_sqrt_f' or 'delta_f_over_f'.
            parallel: If True, use multiprocessing.
            n_processes: Number of parallel processes.
            apply_motion_correction: If True, run motion correction.
            inspect_motion_correction: If True, show motion diagnostics.
            plot_params: If True, display CNMF-E parameter plots.
            run_CNMFE: If True, run CNMF-E source extraction.
            save_estimates: If True, save CNMF-E results to disk.
            save_CNMFE_estimates_filename: Filename for estimates.
            save_CNMFE_params: If True, save parameters to JSON.
            remove_components_with_gui: If True, open component curation GUI.
            find_calcium_events: If True, detect calcium transients.
            derivative_for_estimates: 'zeroth', 'first', or 'second'.
            event_height: Threshold for peak detection.
            compute_miniscope_phase: If True, compute Hilbert phase.
            filter_miniscope_data: If True, apply bandpass filter.
            n: Filter order.
            cut: [low, high] cutoff frequencies.
            ftype: Filter type ('butter').
            btype: Band type ('bandpass').
            inline: If True, replace data with filtered version.
            compute_miniscope_spectrogram: If True, compute spectrogram.
            window_length: Spectrogram window in seconds.
            window_step: Spectrogram step in seconds.
            freq_lims: [low, high] frequency range.
            time_bandwidth: Multitaper time-bandwidth product.
            headless: If True, disable all GUI interactions.
        """


        if headless:
            inspect_motion_correction = False
            remove_components_with_gui = False
            plot_params = False
            inline = False
            print("Running in HEADLESS mode. GUI steps disabled.", flush=True)

        try:
            self.miniscope_data_manager = MiniscopeDataManager.create(
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                filenames=filenames,
                auto_import_data=True,
            )
        except FileNotFoundError as e:
            raise DataNotFoundError(
                "Required miniscope input files were not found.",
                stage="create_data_manager",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Verify experiments.csv paths and ensure miniscope recordings exist under data_path.",
            ) from e
        except Exception as e:
            raise PipelineExecutionError(
                "Failed to initialize MiniscopeDataManager.",
                stage="create_data_manager",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Check metadata row values and input filenames.",
            ) from e



        #get cropping coordinates from crop_coords argument or from analysis_params
        if crop_coords is not None:
            coords_dict = {
                'x0': crop_coords[0], 'y0': crop_coords[1],
                'x1': crop_coords[2], 'y1': crop_coords[3]
            }
            crop_job_name = '_crop'
        else:
            coords_dict, crop_job_name = get_coords_dict_from_analysis_params(self.miniscope_data_manager)

        try:
            self.preprocessor = MiniscopePreprocessor(self.miniscope_data_manager)
            self.miniscope_data_manager = self.preprocessor.preprocess_calcium_movie(
                coords_dict,
                crop=crop,
                detrend_method=detrend_method,
                df_over_f=df_over_f,
                crop_job_name_for_file=crop_job_name,
                secs_window=secs_window,
                quantile_min=quantile_min,
                df_over_f_method=df_over_f_method,
                headless=headless,
            )
            self.preprocessing_result = self.preprocessor.result
        except Exception as e:
            raise PipelineExecutionError(
                "Miniscope preprocessing failed.",
                stage="preprocess_calcium_movie",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Inspect crop/detrend/df_over_f parameters for this experiment row.",
            ) from e

        if self.miniscope_data_manager.coords is not None:
            analysis_params_csv = self.miniscope_data_manager.project_path / "analysis_parameters.csv"
            print(f"updating {analysis_params_csv} with your cropping coordinates", flush=True)
            update_csv_cell(self.miniscope_data_manager.coords, 'crop_coords', line_num, analysis_params_csv)


        #Ensure self.miniscope.data_manager has 'movie' and 'preprocessed_movie_filepath' filled in with the movie that you want to process before you process

        try:
            self.processor = MiniscopeProcessor(self.miniscope_data_manager)
            self.miniscope_data_manager = self.processor.process_calcium_movie(
                parallel,
                n_processes,
                apply_motion_correction,
                inspect_motion_correction,
                plot_params,
                run_CNMFE,
                save_estimates,
                save_CNMFE_estimates_filename,
                save_CNMFE_params,
            )
            self.processing_result = self.processor.result
        except Exception as e:
            raise PipelineExecutionError(
                "Miniscope processing stage failed.",
                stage="process_calcium_movie",
                line_num=line_num,
                project_path=project_path,
                data_path=data_path,
                hint="Check CNMF-E and motion-correction parameters and data integrity.",
            ) from e



        if self.miniscope_data_manager.CNMFE_obj is not None:
            from aceneurotools.shared.plotting import set_backend
            set_backend(headless=headless)
            if not headless:
                if hasattr(tkinter, '_default_root') and tkinter._default_root:
                    tkinter._default_root.destroy()

            try:
                self.postprocessor = MiniscopePostprocessor(self.miniscope_data_manager)
                self.miniscope_data_manager = self.postprocessor.postprocess_calcium_movie(
                    remove_components_with_gui,
                    find_calcium_events,
                    derivative_for_estimates,
                    event_height,
                    compute_miniscope_phase,
                    filter_miniscope_data,
                    n,
                    cut,
                    ftype,
                    btype,
                    inline,
                    compute_miniscope_spectrogram,
                    window_length,
                    window_step,
                    freq_lims,
                    time_bandwidth,
                )
                self.postprocessing_result = self.postprocessor.result
            except Exception as e:
                raise PipelineExecutionError(
                    "Miniscope postprocessing failed.",
                    stage="postprocess_calcium_movie",
                    line_num=line_num,
                    project_path=project_path,
                    data_path=data_path,
                    hint="Check event detection/filter/spectrogram parameters and CNMF-E outputs.",
                ) from e


    def run_with_configs(
        self,
        line_num: int,
        preprocess: PreprocessConfig,
        process: ProcessConfig,
        postprocess: PostprocessConfig,
        project_path: str | Path | None = None,
        data_path: str | Path | None = None,
        filenames: list[str] = [],
        headless: bool = False,
    ) -> None:
        """Run the pipeline using structured config dataclasses.

        This is the preferred API for programmatic use.  The config objects
        group the 30+ parameters of :meth:`run` into three typed dataclasses
        — one per pipeline stage — which are validated at construction time
        and can be persisted, logged, or diffed as ordinary Python objects.

        Internally this method unpacks the configs and delegates to the
        unchanged :meth:`run` method, so all existing behaviour is preserved.

        Args:
            line_num: Experiment line number in experiments.csv.
            preprocess: Preprocessing stage configuration.
            process: Processing stage configuration.
            postprocess: Post-processing stage configuration.
            project_path: Path to the project directory.
            data_path: Base path for raw experimental data.
            filenames: Movie filenames to load (e.g. ``['0.avi']``).
            headless: If ``True``, disable all GUI interactions.
        """
        self.run(
            line_num=line_num,
            project_path=project_path,
            data_path=data_path,
            filenames=filenames,
            # preprocessing
            crop=preprocess.crop,
            crop_coords=preprocess.crop_coords,
            detrend_method=preprocess.detrend_method,
            df_over_f=preprocess.df_over_f,
            secs_window=preprocess.secs_window,
            quantile_min=preprocess.quantile_min,
            df_over_f_method=preprocess.df_over_f_method,
            # processing
            parallel=process.parallel,
            n_processes=process.n_processes,
            apply_motion_correction=process.apply_motion_correction,
            inspect_motion_correction=process.inspect_motion_correction,
            plot_params=process.plot_params,
            run_CNMFE=process.run_CNMFE,
            save_estimates=process.save_estimates,
            save_CNMFE_estimates_filename=process.save_CNMFE_estimates_filename,
            save_CNMFE_params=process.save_CNMFE_params,
            # postprocessing
            remove_components_with_gui=postprocess.remove_components_with_gui,
            find_calcium_events=postprocess.find_calcium_events,
            derivative_for_estimates=postprocess.derivative_for_estimates,
            event_height=postprocess.event_height,
            compute_miniscope_phase=postprocess.compute_miniscope_phase,
            filter_miniscope_data=postprocess.filter_miniscope_data,
            n=postprocess.n,
            cut=postprocess.cut,
            ftype=postprocess.ftype,
            btype=postprocess.btype,
            inline=postprocess.inline,
            compute_miniscope_spectrogram=postprocess.compute_miniscope_spectrogram,
            window_length=postprocess.window_length,
            window_step=postprocess.window_step,
            freq_lims=postprocess.freq_lims,
            time_bandwidth=postprocess.time_bandwidth,
            headless=headless,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Miniscope Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with explicit project path
  python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /path/to/project
  
  # Run in headless mode (no GUI) for batch processing
  python -m aceneurotools.pipelines.miniscope --line-num 96 --project-path /path/to/project --headless
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
        'filenames': ['0.avi'],
        # Preprocessing
        'crop': True,
        'detrend_method': None,
        'df_over_f': False,
        'secs_window': 5,
        'quantile_min': 8,
        'df_over_f_method': 'delta_f_over_sqrt_f',
        # Processing
        'parallel': True,
        'n_processes': 6,
        'apply_motion_correction': False,
        'inspect_motion_correction': True,
        'plot_params': False,
        'run_CNMFE': True,
        'save_estimates': True,
        'save_CNMFE_estimates_filename': 'estimates.hdf5',
        'save_CNMFE_params': True,
        # Post-processing
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
        'inline': True,
        'compute_miniscope_spectrogram': True,
        'window_length': 30,
        'window_step': 3,
        'freq_lims': [0, 15],
        'time_bandwidth': 2
    }

    from aceneurotools.shared.config_utils import load_analysis_params
    run_params = build_run_params(
        defaults=defaults,
        allowed_keys=run_allowed_keys(MiniscopePipeline.run),
        line_num=args.line_num,
        project_path=args.project_path,
        data_path=args.data_path,
        headless=args.headless,
        csv_loader=load_analysis_params,
    )
    apply_headless_policy(pipeline_name="miniscope", run_params=run_params)
    validate_run_params(pipeline_name="miniscope", run_params=run_params)

    api = MiniscopePipeline()
    try:
        api.run(**run_params)
    except (AceNeuroError, FileNotFoundError, ValueError) as e:
        print_cli_error(e, include_cause=args.headless)
        if args.headless:
            sys.exit(1)
        raise
