# Set the current working directory to this script's directory
import os
os.chdir('/Users/nathan/Desktop/Neuro/experiment_analysis')
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src2.shared.paths import ANALYSIS_PARAMS
from src2.shared.misc_functions import updateCSVCell
from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from src2.miniscope.miniscope_processor import MiniscopeProcessor
from src2.miniscope.miniscope_postprocessor import MiniscopePostprocessor
from src2.ephys.visualizer import Visualizer
from typing import List
from src2.miniscope.movie_io import MovieIO


class MiniscopeAPI:
    """Main workflow class for non-technical users. Adjust the paramters at the bottom and press run."""

    def __init__(self):
        pass
    
    def run(
            self, 
            line_num: int,
            
            #preprocessing parameters
            crop = False,
              #These should only be true/contain values if crop=True
              crop_square = False,
              crop_with_crop = False,
              crop_with_gui = False,
            denoise = False,
            detrend = False,
            df_over_f = False,

            #processing parameters    
            parallel = False,
            n_processes = 12,
            apply_motion_correction = False,
            inspect_motion_correction = False,
            inspect_corr_PNR = False,
            downsample_for_corr_PNR = 1,
            run_CNMFE = False,
            deconvolve = False,
            save_CNMFE_estimates_filename = 'estimates.hdf5',
            
            #post processing parameters
            remove_components_with_gui=True, 
            evaluate_components=False, 
            find_calcium_events=True, 
            compute_miniscope_spectrogram=True, 
            compute_miniscope_phase=True, 
            filter_miniscope_data=False    
            ):
        
        # Create instance of EphysDataManager, process the block into channels
        self.data_manager = MiniscopeDataManager(line_num, auto_import_data=True)
        miniscope_dir_path = self.data_manager.metadata['calcium imaging directory']
        self.preprocessor = MiniscopePreprocessor(self.data_manager.movie, miniscope_dir_path)

        coords_dict = None
        crop_job_name = ''
        if crop:
            if crop_square:
                coords = self.data_manager.analysis_params['crop_square']
                coords_dict = { 'x0': coords[0], 'y0': coords[1], 'x1': coords[2], 'y1': coords[3]}
                crop_job_name = '_crop_square'
            elif crop_with_crop:
                coords = self.data_manager.analysis_params['crop']
                coords_dict = { 'x0': coords[0], 'y0': coords[1], 'x1': coords[2], 'y1': coords[3]}
                crop_job_name = '_crop'
            else:
                coords_dict = None
                crop_job_name = '_cropped'
        
        preprocessed_movie_filepath, movie_coords = self.preprocessor.preprocess_calcium_movie(coords_dict, crop=crop, denoise=denoise, detrend=detrend, df_over_f=df_over_f, crop_job_name_for_file=crop_job_name)
        
        self.processor = MiniscopeProcessor(self.data_manager, preprocessed_movie_filepath)
        estimates_filepath, opts_caiman_filepath, self.data_manager, dview = self.processor.process_calcium_movie(parallel=parallel, n_processes=n_processes, apply_motion_correction=apply_motion_correction, 
                                                                                                            inspect_motion_correction=inspect_motion_correction, inspect_corr_PNR=inspect_corr_PNR, 
                                                                                                            downsample_for_corr_PNR=downsample_for_corr_PNR, run_CNMFE=run_CNMFE, 
                                                                                                            save_CNMFE_estimates_filename=save_CNMFE_estimates_filename)
        if estimates_filepath:
            self.postprocessor = MiniscopePostprocessor(preprocessed_movie_filepath, estimates_filepath, opts_caiman_filepath, dview=dview)
            self.postprocessor.postprocess_calcium_movie(remove_components_with_gui=remove_components_with_gui, evaluate_components=evaluate_components, find_calcium_events=find_calcium_events, 
                                                     compute_miniscope_spectrogram=compute_miniscope_spectrogram, compute_miniscope_phase=compute_miniscope_phase, filter_miniscope_data=filter_miniscope_data)


if __name__ == "__main__":
    # run the API
    api = MiniscopeAPI()
    api.run(
        97, #line number of the experiment you are analyzing
        
        #preprocessing parameters
        crop = True,
            #These should only be true/contain values if crop=True
            crop_square = True,
            crop_with_crop = False,
            crop_with_gui = False,
        denoise = False,
        detrend = True,
        df_over_f = False,

        #processing parameters    
        parallel = True,
        n_processes = 12,
        apply_motion_correction = False,
        inspect_motion_correction = True,
        inspect_corr_PNR = False,
        downsample_for_corr_PNR = 1,
        run_CNMFE = True,
        deconvolve = True,
        save_CNMFE_estimates_filename = 'estimates.hdf5',
        
        #post-processing parameters
        remove_components_with_gui=True, 
        evaluate_components=False, 
        find_calcium_events=True, 
        compute_miniscope_spectrogram=True, 
        compute_miniscope_phase=True, 
        filter_miniscope_data=True
        )
        
    
    
    
    
    
    
    
    
    
    
    
    