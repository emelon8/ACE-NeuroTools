from src2.miniscope.miniscope_api import MiniscopeAPI
from src2.ephys.ephys_api import EphysAPI
from src2.multimodal.miniscope_ephys_alignment_utils import sync_neuralynx_miniscope_timestamps, find_ephys_idx_of_TTL_events, find_ca_movie_frame_num_of_ephys_idx, find_ca_movie_filenums
from src2.multimodal.calcium_ephys_visualizer import create_ca_ephys_movie
from src2.multimodal.phase_utils import ephys_phase_ca_events, miniscope_phase_ca_events, phase_ca_events_histogram
import argparse
import sys
import yaml
import traceback
from src2.shared.config_utils import load_config, parse_multimodal_config

class MultimodalAPI:
        
    
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
        
        
        
        ephys_api = EphysAPI()
        # Pass headless to ephys api
        ephys_api.run(line_num, channel_name, remove_artifacts, filter_type, filter_range, plot_channel, plot_spectrogram, plot_phases, logging_level, headless=headless)
        
        
        
        miniscope_api = MiniscopeAPI()
        # Pass headless to miniscope api
        miniscope_api.run(line_num, miniscope_filenames, crop, crop_square, crop_with_crop, detrend_method, df_over_f, secs_window, 
                          quantile_min, df_over_f_method, parallel, n_processes, apply_motion_correction, inspect_motion_correction, plot_params,
                          run_CNMFE, save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params, remove_components_with_gui, find_calcium_events, derivative_for_estimates, event_height,
                          compute_miniscope_phase, filter_miniscope_data, n, cut, ftype, btype, inline, compute_miniscope_spectrogram, window_length, window_step, freq_lims, time_bandwidth, headless=headless)
        



        
        #pull everything we need to run multi modal analysis:
        channel_object = ephys_api.ephys_data_manager.get_channel(channel_name)
        frame_rate = miniscope_api.miniscope_data_manager.fr
        ca_events_idx = miniscope_api.miniscope_data_manager.ca_events_idx
        miniscope_phases = miniscope_api.miniscope_data_manager.miniscope_phases
        
        
        
        tCaIm, low_confidence_periods, channel_object, miniscope_dm = sync_neuralynx_miniscope_timestamps(channel_object, miniscope_api.miniscope_data_manager, delete_TTLs=delete_TTLs, 
                                                                                                   fix_TTL_gaps=fix_TTL_gaps, only_experiment_events=only_experiment_events)
        

        
        # set changed variables
        print("\nSuccess! Setting changed variables.")
        miniscope_api.miniscope_data_manager = miniscope_dm
        ephys_api.ephys_data_manager.channels[channel_name] = channel_object
        
        
        ephys_idx_all_TTL_events, ephys_idx_ca_events = find_ephys_idx_of_TTL_events(tCaIm, channel_object, frame_rate, all_TTL_events=all_TTL_events, ca_events_idx=ca_events_idx if ca_events else None)
        ca_frame_num_of_ephys_idx = find_ca_movie_frame_num_of_ephys_idx(channel_object, ephys_idx_all_TTL_events)
        
        ca_events_phases_ephys = ephys_phase_ca_events(ephys_idx_ca_events, channel_object, neurons='all')
        ca_events_phases_miniscope = miniscope_phase_ca_events(ca_events_idx, miniscope_phases, neurons='all')
        
        
        hist1, bin_edges1 = phase_ca_events_histogram(ca_events_phases_ephys)
        
        
        hist2, bin_edges2 = phase_ca_events_histogram(ca_events_phases_miniscope)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Multimodal Analysis Pipeline")
    parser.add_argument('--config', type=str, help="Path to YAML configuration file")
    parser.add_argument('--headless', action='store_true', help="Run in headless mode (no GUI)")
    
    args = parser.parse_args()
    
    # Default parameters
    run_params = {
        'line_num': 97,
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
        'crop_with_crop': False,
        'crop_square': True,
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
    
    if args.config:
        print(f"Loading configuration from {args.config}...", flush=True)
        config = load_config(args.config)
        config_params = parse_multimodal_config(config)
        run_params.update(config_params)
        
    if args.headless:
        run_params['headless'] = True

    api = MultimodalAPI()
    try:
        api.run(**run_params)
    except Exception:
        if args.headless:
            traceback.print_exc()
            sys.exit(1)
        raise