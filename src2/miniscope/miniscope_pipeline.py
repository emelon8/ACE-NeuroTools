from src2.shared.misc_functions import updateCSVCell
from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from src2.miniscope.miniscope_processor import MiniscopeProcessor
from src2.miniscope.miniscope_postprocessor import MiniscopePostprocessor
from src2.shared.paths import ANALYSIS_PARAMS, BASE_FILE_PATH
import caiman as cm
from src2.shared.misc_functions import get_coords_dict_from_analysis_params
from src2.miniscope.movie_io import MovieIO
import matplotlib
import tkinter
import os
import yaml
import argparse
import sys
from src2.shared.config_utils import load_config, parse_miniscope_config

# Adjust the path below to where you would like Caiman to store temporary files that it uses during the miniscope pipeline
os.environ["CAIMAN_DATA"] = f'{BASE_FILE_PATH}/K99/miniscope_data/ketamine/R230706B/2023_09_01/15_04_11/saved_movies'



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

    def __init__(self):
        """Initialize the MiniscopePipeline."""
    
    def run(
            self, 
            line_num: int,
            filenames = [],
            
            #preprocessing parameters
            crop = True,
              #These should only be true if crop=True, and only one should be True or niether
              crop_with_crop = False,
              crop_square = False,
            detrend_method = 'median',
            df_over_f = False,
              #if df_over_f = True
              secs_window=5,                     
              quantile_min=8,
              df_over_f_method='delta_f_over_sqrt_f',

            #processing parameters    
            parallel = False,
            n_processes = 12,
            apply_motion_correction = False,
            inspect_motion_correction = False,
            plot_params = False,
            run_CNMFE = False,
            save_estimates=True,
              save_CNMFE_estimates_filename = 'estimates.hdf5',
            save_CNMFE_params = False,
            
            #post processing parameters
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
              headless = False
            ):
        """Run the complete miniscope analysis pipeline.
        
        Executes preprocessing (crop, detrend, DF/F), processing (motion
        correction, CNMF-E), and post-processing (component selection,
        event detection, spectral analysis) in sequence.
        
        Args:
            line_num: Experiment line number in experiments.csv.
            filenames: List of movie filenames to load (e.g., ['0.avi']).
            crop: If True, apply interactive cropping.
            crop_with_crop: Use 'crop' column from analysis params.
            crop_square: Use 'crop_square' column from analysis params.
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

        self.miniscope_data_manager = MiniscopeDataManager(line_num, filenames, auto_import_data=True)
        
        
        #get previous cropping coordinates from analysis_params in case we want to use our last crop
        coords_dict, crop_job_name = get_coords_dict_from_analysis_params(self.miniscope_data_manager, crop_with_crop, crop_square)
        
        self.preprocessor = MiniscopePreprocessor(self.miniscope_data_manager)
        self.miniscope_data_manager = self.preprocessor.preprocess_calcium_movie(coords_dict, crop=crop, detrend_method=detrend_method, df_over_f=df_over_f, 
                                                                                 crop_job_name_for_file=crop_job_name, secs_window=secs_window, 
                                                                                 quantile_min=quantile_min, df_over_f_method=df_over_f_method)
        
        print(f"updating {ANALYSIS_PARAMS} with your cropping coordinates", flush=True)
        updateCSVCell(self.miniscope_data_manager.coords, 'crop' if crop_with_crop else 'crop_square', line_num, ANALYSIS_PARAMS)
        
        
        #Ensure self.miniscope.data_manager has 'movie' and 'preprocessed_movie_filepath' filled in with the movie that you want to process before you process
        
        self.processor = MiniscopeProcessor(self.miniscope_data_manager)
        self.miniscope_data_manager = self.processor.process_calcium_movie(parallel, n_processes, apply_motion_correction, 
                                   inspect_motion_correction, plot_params, run_CNMFE,
                                   save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params)
        
        
        
        if self.miniscope_data_manager.CNMFE_obj is not None:
            if not headless:
                if tkinter._default_root:  # Check if Tkinter root exists
                    tkinter._default_root.destroy()  # Force close any Tkinter root
                matplotlib.use('Qt5Agg')  # Switch to Qt backend so that we can use interactive plotting during estimate evaluation
            else:
                matplotlib.use('Agg')
            
            self.postprocessor = MiniscopePostprocessor(self.miniscope_data_manager)
            self.miniscope_data_manager = self.postprocessor.postprocess_calcium_movie(remove_components_with_gui, find_calcium_events, derivative_for_estimates, 
                                                                                       event_height, compute_miniscope_phase, filter_miniscope_data,n, cut, ftype, 
                                                                                       btype, inline, compute_miniscope_spectrogram, window_length, window_step, 
                                                                                       freq_lims, time_bandwidth)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Miniscope Analysis Pipeline")
    parser.add_argument('--config', type=str, help="Path to YAML configuration file")
    parser.add_argument('--headless', action='store_true', help="Run in headless mode (no GUI)")
    
    args = parser.parse_args()
    
    # Default parameters (legacy hardcoded values)
    run_params = {
        'line_num': 96,
        'filenames': ['0.avi'],
        # Preprocessing
        'crop': True,
        'crop_with_crop': False,
        'crop_square': True,
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
    
    if args.config:
        print(f"Loading configuration from {args.config}...", flush=True)
        config = load_config(args.config)
        config_params = parse_miniscope_config(config)
        run_params.update(config_params)
        
    if args.headless:
        run_params['headless'] = True
        
    api = MiniscopePipeline()
    try:
        api.run(**run_params)
    except Exception as e:
        print(f"Error occurred during execution: {e}", file=sys.stderr)
        if args.headless:
            # In headless mode, ensure we exit with non-zero code on error
            sys.exit(1)
        raise