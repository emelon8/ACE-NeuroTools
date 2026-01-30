import yaml

def load_config(config_path):
    """Loads YAML config file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def parse_miniscope_config(config):
    """Maps nested YAML config to flat MiniscopeAPI arguments."""
    args = {}
    
    # Experiment
    exp = config.get('experiment', {})
    if 'line_num' in exp: args['line_num'] = exp['line_num']
    if 'filenames' in exp: args['filenames'] = exp['filenames']
    
    # Preprocessing
    pre = config.get('miniscope_preprocessing', config.get('preprocessing', {})) # Forward compat with unified config
    if 'crop' in pre: args['crop'] = pre['crop']
    if 'detrend_method' in pre: args['detrend_method'] = pre['detrend_method']
    if 'df_over_f' in pre: args['df_over_f'] = pre['df_over_f']
    
    crop_params = pre.get('crop_params', {})
    if 'crop_with_crop' in crop_params: args['crop_with_crop'] = crop_params['crop_with_crop']
    if 'crop_square' in crop_params: args['crop_square'] = crop_params['crop_square']
    
    df_params = pre.get('df_over_f_params', {})
    if 'secs_window' in df_params: args['secs_window'] = df_params['secs_window']
    if 'quantile_min' in df_params: args['quantile_min'] = df_params['quantile_min']
    if 'method' in df_params: args['df_over_f_method'] = df_params['method']
    
    # Processing
    proc = config.get('miniscope_processing', config.get('processing', {}))
    for key in ['parallel', 'n_processes', 'apply_motion_correction', 'inspect_motion_correction',
                'plot_params', 'run_CNMFE', 'save_estimates', 'save_CNMFE_params']:
        if key in proc: args[key] = proc[key]
    
    if 'save_CNMFE_estimates_filename' in proc: 
        args['save_CNMFE_estimates_filename'] = proc['save_CNMFE_estimates_filename']

    # Postprocessing
    post = config.get('miniscope_postprocessing', config.get('postprocessing', {}))
    if 'remove_components_with_gui' in post: args['remove_components_with_gui'] = post['remove_components_with_gui']
    if 'find_calcium_events' in post: args['find_calcium_events'] = post['find_calcium_events']
    if 'compute_miniscope_phase' in post: args['compute_miniscope_phase'] = post['compute_miniscope_phase']
    if 'filter_data' in post: args['filter_miniscope_data'] = post['filter_data'] 
    if 'spectrogram' in post: args['compute_miniscope_spectrogram'] = post['spectrogram'] 
    
    for key in ['derivative_for_estimates', 'event_height', 'n', 'cut', 'ftype', 'btype', 'inline',
                'window_length', 'window_step', 'freq_lims', 'time_bandwidth']:
        if key in post: args[key] = post[key]
        
    return args

def parse_ephys_config(config):
    """Maps nested YAML config to flat EphysAPI arguments."""
    args = {}
    
    # Experiment (Shared)
    exp = config.get('experiment', {})
    if 'line_num' in exp: args['line_num'] = exp['line_num']

    # Ephys
    ephys = config.get('ephys', {})
    if 'channel_name' in ephys: args['channel_name'] = ephys['channel_name']
    if 'remove_artifacts' in ephys: args['remove_artifacts'] = ephys['remove_artifacts']
    if 'filter_type' in ephys: args['filter_type'] = ephys['filter_type']
    if 'filter_range' in ephys: args['filter_range'] = ephys['filter_range']
    
    # Visualization
    viz = ephys.get('visualization', {})
    if 'plot_channel' in viz: args['plot_channel'] = viz['plot_channel']
    if 'plot_spectrogram' in viz: args['plot_spectrogram'] = viz['plot_spectrogram']
    if 'plot_phases' in viz: args['plot_phases'] = viz['plot_phases']
    
    # Logging
    if 'logging_level' in config: args['logging_level'] = config['logging_level']
    elif 'logging_level' in ephys: args['logging_level'] = ephys['logging_level']

    return args

def parse_multimodal_config(config):
    """Maps nested YAML config to flat MultimodalAPI arguments."""
    # Multimodal runs everything, so it needs params for both + alignment
    args = {}
    
    # 1. Get Ephys params (they share keys in run(), so we can just merge)
    ephys_args = parse_ephys_config(config)
    
    # 2. Get Miniscope params 
    # NOTE: MultimodalAPI.run() has specific names for miniscope args. 
    # Most match MiniscopeAPI.run(), but 'filenames' is 'miniscope_filenames'
    miniscope_args = parse_miniscope_config(config)
    if 'filenames' in miniscope_args:
        args['miniscope_filenames'] = miniscope_args.pop('filenames')
    
    # 3. Multimodal specific
    multi = config.get('multimodal', {})
    for key in ['delete_TTLs', 'fix_TTL_gaps', 'only_experiment_events', 
                'all_TTL_events', 'ca_events', 'time_range']:
        if key in multi: args[key] = multi[key]
        
    # Merge all
    # Ephys args map directly (e.g. channel_name, filter_type)
    args.update(ephys_args)
    # Miniscope args map directly (e.g. crop, parallel), except filenames handled above
    args.update(miniscope_args)
    
    return args
