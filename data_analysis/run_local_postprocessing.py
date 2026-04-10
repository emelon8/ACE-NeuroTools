#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import caiman as cm
import matplotlib
import tkinter

# Add the experiment_analysis root to python path
experiment_analysis_root = Path('/home/reed/lab/experiment_analysis')
sys.path.append(str(experiment_analysis_root))

from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.ucla_v4_miniscope_data_manager import UCLAV4MiniscopeDataManager
from src2.miniscope.v3_miniscope_data_manager import V3MiniscopeDataManager
from src2.miniscope.miniscope_postprocessor import MiniscopePostprocessor

# List of experiments to process
EXPERIMENTS = [96]
estimates_path = '/Users/josieallred/Research/experiment_analysis/data/downloaded_data/estimates_345.hdf5'
new_file_name = 'estimates_trimmed345.hdf5'
def main():
    # Make sure we're using a GUI backend for interactive plots
    if tkinter._default_root:
        tkinter._default_root.destroy()
    
    # Needs to be Qt5Agg to allow interactive component evaluation
    try:
         matplotlib.use('Qt5Agg')
    except Exception as e:
         print(f"Warning: Failed to set Qt5Agg backend: {e}")

    for line_num in EXPERIMENTS:
        print(f"\n{'='*50}")
        print(f"Local Post-Processing for experiment {line_num}")
        print('='*50)
        
        # 1. Load the data manager to get the directory paths
        print("Initializing MiniscopeDataManager...")
        dm = MiniscopeDataManager.create(line_num=line_num, filenames=[], auto_import_data=False)
        dm.import_metadata()
        
        # 2. Locate the CNMF-E estimates from the supercomputer run
        saved_movies_dir = os.path.join(dm.metadata['calcium imaging directory'], "saved_movies")
        estimates_path = os.path.join(saved_movies_dir, new_file_name)
        
        if not os.path.exists(estimates_path):
            print(f"Error: Estimates file not found at {estimates_path}")
            print("Did you run the supercomputer pipeline yet (e.g. MiniscopePipeline with --headless)?")
            continue
            
        # 3. Load the pre-computed CNMF-E estimates
        print(f"Loading CNMF-E estimates from {estimates_path}...")
        CNMFE_obj = cm.source_extraction.cnmf.cnmf.load_CNMF(estimates_path)
        dm.CNMFE_obj = CNMFE_obj
        
        # 4. Load the memory-mapped movie used during processing
        # The postprocessor needs dm.movie populated to compute spatial/temporal projections.
        # It references the motion-corrected movie memory map created during Stage 1.
        mmap_filepath = CNMFE_obj.params.get('data', 'fnames')
        if isinstance(mmap_filepath, list):
            mmap_filepath = mmap_filepath[0]
            
        print(f"Loading memory-mapped movie: {Path(mmap_filepath).name}")
        Yr, dims, T = cm.load_memmap(mmap_filepath)
        images = Yr.T.reshape((T,) + dims, order='F')
        
        # Store as a CaImAn movie block for projections
        dm.movie = cm.movie(images, fr=dm.fr)
        
        # 5. Run the Local Post-Processing Pipeline
        print("\nStarting local post-processing... (GUI windows will pop up)")
        postprocessor = MiniscopePostprocessor(dm)
        
        dm = postprocessor.postprocess_calcium_movie(
            remove_components_with_gui=True, 
            find_calcium_events=True, 
            derivative_for_estimates='first', 
            event_height=5, 
            compute_miniscope_phase=True, 
            filter_miniscope_data=True,
            n=2, 
            cut=[0.1, 1.5], 
            ftype='butter', 
            btype='bandpass', 
            inline=False, 
            compute_miniscope_spectrogram=True, 
            window_length=30, 
            window_step=3, 
            freq_lims=[0, 15], 
            time_bandwidth=2
        )
        
        print(f"\nFinished local post-processing for experiment {line_num}!")

if __name__ == '__main__':
    main()
