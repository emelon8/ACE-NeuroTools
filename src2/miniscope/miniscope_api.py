# Set the current working directory to this script's directory
import os
os.chdir('/Users/nathan/Desktop/Neuro/experiment_analysis/')
from src2.shared.paths import ANALYSIS_PARAMS
from src2.shared.misc_functions import updateCSVCell
from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from src2.miniscope.miniscope_processor import MiniscopeProcessor
from src2.ephys.visualizer import Visualizer
from typing import List
from src2.miniscope.movie_io import MovieIO


class MiniscopeAPI:
    """Main workflow class."""

    def __init__(self):
        pass
    
    def run(
            self, 
            line_num,
            
            #preprocessing parameters
            crop = False,
                #These should only be true/contain values if crop=True
                crop_square = False,
                crop_with_crop = False,
                crop_with_my_coords = None,
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
            save_CNMFE_estimates_filename = 'estimates.hdf5'
            ):
        
        # Create instance of EphysDataManager, process the block into channels
        self.data_manager = MiniscopeDataManager(line_num, auto_import_data=True)
        miniscope_dir_path = self.data_manager.metadata['calcium imaging directory']
        self.preprocessor = MiniscopePreprocessor(self.data_manager.movie)

        coords_dict = None
        if crop:
            if crop_square:
                coords = self.data_manager.analysis_params['crop_square']
                coords_dict = { 'x0': coords[0], 'y0': coords[1], 'x1': coords[2], 'y1': coords[3]}
                crop_job_name = '_square'
            elif crop_with_crop:
                coords = self.data_manager.analysis_params['crop']
                coords_dict = { 'x0': coords[0], 'y0': coords[1], 'x1': coords[2], 'y1': coords[3]}
                crop_job_name = '_crop'
            elif crop_with_my_coords:
                coords_dict = { 'x0': coords[0], 'y0': coords[1], 'x1': coords[2], 'y1': coords[3]}
                crop_job_name = '_cropped_with_my_coords'
            elif crop_with_gui:
                coords_dict = None
        
        filepath, movie_coords = self.preprocessor.preprocess_calcium_movie(miniscope_dir_path, coords_dict, crop=crop, denoise=denoise, detrend=detrend, df_over_f=df_over_f, crop_job_name_for_file=crop_job_name if crop else '')
        
        self.processor = MiniscopeProcessor(self.data_manager, filepath, jobID="")
        if run_CNMFE:
            estimates_filepath, self.data_manager, self.opts_caiman = self.processor.process_calcium_movies(parallel=parallel, n_processes=n_processes, apply_motion_correction=apply_motion_correction, 
                                                                                                            inspect_motion_correction=inspect_motion_correction, inspect_corr_PNR=inspect_corr_PNR, 
                                                                                                            downsample_for_corr_PNR=downsample_for_corr_PNR, run_CNMFE=run_CNMFE, 
                                                                                                            save_CNMFE_estimates_filename=save_CNMFE_estimates_filename, deconvolve=deconvolve)


if __name__ == "__main__":      
    # run the API
    api = MiniscopeAPI()
    api.run(
        97,
        
        #preprocessing parameters
        crop = False,
            #These should only be true/contain values if crop=True
            crop_square = False,
            crop_with_crop = False,
            crop_with_my_coords = None,
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
        save_CNMFE_estimates_filename = 'estimates.hdf5'
        )
        
    
    
    
    
    
    
    
    
    
    
    
    