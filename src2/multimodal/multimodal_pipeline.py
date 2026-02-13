from src2.miniscope.miniscope_pipeline import MiniscopePipeline
from src2.ephys.ephys_pipeline import EphysPipeline
from src2.multimodal.miniscope_ephys_alignment_utils import sync_neuralynx_miniscope_timestamps, find_ephys_idx_of_TTL_events, find_ca_movie_frame_num_of_ephys_idx, find_ca_movie_filenums
from src2.multimodal.calcium_ephys_visualizer import create_ca_ephys_movie
from src2.multimodal.phase_utils import ephys_phase_ca_events, miniscope_phase_ca_events, phase_ca_events_histogram
import argparse
import sys
import traceback
from src2.shared.config_utils import load_analysis_params

class MultimodalPipeline:
    """High-level API for combined ephys and calcium imaging analysis.
    
    Orchestrates synchronized analysis of Neuralynx electrophysiology and
    miniscope calcium imaging data, including timestamp alignment and
    phase-based event analysis.
    
    Attributes:
        ephys_data_manager: EphysDataManager (via ephys_pipeline).
        miniscope_data_manager: MiniscopeDataManager (via miniscope_pipeline).
    """
        
    
    def run(self,
            line_num,
            #ephys parameters
            channel_name = 'PFCLFPvsCBEEG',
            remove_artifacts = False,
            filter_type = None,
            filter_range = [0.5, 4],
            plot_channel = False,
            plot_spectrogram = False,
            plot_phases = False,
            logging_level = "CRITICAL",
            
            #miniscope parameters
            miniscope_filenames = [],
            #preprocessing parameters
            crop = True,
            crop_coords = None,
            detrend_method = 'median',
            df_over_f = False,
              #if df_over_f = True
              secs_window=5,                     
              quantile_min=8,
              df_over_f_method='delta_f_over_sqrt_f',

            #processing parameters    
            parallel = False,
            n_processes = 6,
            apply_motion_correction = True,
            inspect_motion_correction = True,
            plot_params = False,
            run_CNMFE = True,
            save_estimates=True,
              save_CNMFE_estimates_filename = 'estimates.hdf5',
            save_CNMFE_params = False,
            
            #post-processing parameters
            remove_components_with_gui=True,  
            find_calcium_events=True,
              derivative_for_estimates='first', 
              event_height = 5, 
            compute_miniscope_phase=True, 
            filter_miniscope_data=True,
              n=2, 
              cut=[0.1,1.5], 
              ftype='butter', 
              btype='bandpass', 
              inline=False,
            compute_miniscope_spectrogram=True,
              window_length = 30, 
              window_step = 3, 
              freq_lims = [0,15], 
              time_bandwidth = 2,
        
            #multimodal parameters
            delete_TTLs=True, 
            fix_TTL_gaps=False, 
            only_experiment_events=True,
            all_TTL_events=True, 
            ca_events=False,
            time_range=None,
            headless=False
            ):
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
        
        
        
        ephys_pipeline = EphysPipeline()
        # Pass headless to ephys api
        ephys_pipeline.run(line_num, channel_name, remove_artifacts, filter_type, filter_range, plot_channel, plot_spectrogram, plot_phases, logging_level, headless=headless)
        
        
        
        miniscope_pipeline = MiniscopePipeline()
        # Pass headless to miniscope api
        miniscope_pipeline.run(line_num, miniscope_filenames, crop, crop_coords, detrend_method, df_over_f, secs_window, 
                          quantile_min, df_over_f_method, parallel, n_processes, apply_motion_correction, inspect_motion_correction, plot_params,
                          run_CNMFE, save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params, remove_components_with_gui, find_calcium_events, derivative_for_estimates, event_height,
                          compute_miniscope_phase, filter_miniscope_data, n, cut, ftype, btype, inline, compute_miniscope_spectrogram, window_length, window_step, freq_lims, time_bandwidth, headless=headless)
        



        
        #pull everything we need to run multi modal analysis:
        channel_object = ephys_pipeline.ephys_data_manager.get_channel(channel_name)
        frame_rate = miniscope_pipeline.miniscope_data_manager.fr
        ca_events_idx = miniscope_pipeline.miniscope_data_manager.ca_events_idx
        miniscope_phases = miniscope_pipeline.miniscope_data_manager.miniscope_phases
        
        
        
        tCaIm, low_confidence_periods, channel_object, miniscope_dm = sync_neuralynx_miniscope_timestamps(channel_object, miniscope_pipeline.miniscope_data_manager, delete_TTLs=delete_TTLs, 
                                                                                                   fix_TTL_gaps=fix_TTL_gaps, only_experiment_events=only_experiment_events)
        

        
        # set changed variables
        print("\nSuccess! Setting changed variables.")
        miniscope_pipeline.miniscope_data_manager = miniscope_dm
        ephys_pipeline.ephys_data_manager.channels[channel_name] = channel_object
        
        
        ephys_idx_all_TTL_events, ephys_idx_ca_events = find_ephys_idx_of_TTL_events(tCaIm, channel_object, frame_rate, all_TTL_events=all_TTL_events, ca_events_idx=ca_events_idx if ca_events else None)
        ca_frame_num_of_ephys_idx = find_ca_movie_frame_num_of_ephys_idx(channel_object, ephys_idx_all_TTL_events)
        
        ca_events_phases_ephys = ephys_phase_ca_events(ephys_idx_ca_events, channel_object, neurons='all')
        ca_events_phases_miniscope = miniscope_phase_ca_events(ca_events_idx, miniscope_phases, neurons='all')
        
        
        hist1, bin_edges1 = phase_ca_events_histogram(ca_events_phases_ephys)
        
        
        hist2, bin_edges2 = phase_ca_events_histogram(ca_events_phases_miniscope)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run Multimodal Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run using analysis_parameters.csv from PROJECT_REPO (set in .env)
  python multimodal_pipeline.py --line-num 97
  
  # Run in headless mode (no GUI) for batch processing
  python multimodal_pipeline.py --line-num 97 --headless
"""
    )
    parser.add_argument('--line-num', type=int, required=True,
                        help="Experiment line number from experiments.csv")
    parser.add_argument('--headless', action='store_true',
                        help="Run in headless mode (no GUI)")
    
    args = parser.parse_args()
    
    # Default parameters
    run_params = {
        'line_num': args.line_num,
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
    
    # Override defaults with parameters from analysis_parameters.csv
    try:
        csv_params = load_analysis_params(args.line_num)
        run_params.update(csv_params)
    except FileNotFoundError:
        print("No analysis_parameters.csv found. Using default parameters.", flush=True)
        
    if args.headless:
        run_params['headless'] = True

    api = MultimodalPipeline()
    try:
        api.run(**run_params)
    except Exception:
        if args.headless:
            traceback.print_exc()
            sys.exit(1)
        raise