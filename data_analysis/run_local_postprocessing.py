#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path
import caiman as cm
import matplotlib
import numpy as np
import tkinter

# Add the experiment_analysis root to python path
experiment_analysis_root = Path(__file__).resolve().parent
sys.path.append(str(experiment_analysis_root))

from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_postprocessor import MiniscopePostprocessor

# List of experiments to process
EXPERIMENTS = [95]

# Written under <calcium imaging directory>/saved_movies/
OUTPUT_CNMFE_FILENAME = "estimates_postprocessed.hdf5"
OUTPUT_NPZ_FILENAME = "postprocessed_local.npz"
OUTPUT_META_FILENAME = "postprocessed_local_meta.json"


def save_postprocessed_results(dm, line_num: int, saved_movies_dir: str) -> None:
    """Persist curated CNMF-E (HDF5) and numpy-side outputs (NPZ + small JSON sidecar)."""
    os.makedirs(saved_movies_dir, exist_ok=True)

    cnmfe_path = os.path.join(saved_movies_dir, OUTPUT_CNMFE_FILENAME)
    if dm.CNMFE_obj is not None:
        print(f"Saving curated CNMF-E object to {cnmfe_path}")
        dm.CNMFE_obj.save(cnmfe_path)
        dm.estimates_filepath = cnmfe_path

    npz_payload = {}
    if getattr(dm, "fr", None) is not None:
        npz_payload["frame_rate_hz"] = float(dm.fr)

    if dm.ca_events_idx:
        npz_payload["ca_events_neuron_keys"] = np.array(
            sorted(dm.ca_events_idx.keys()), dtype=int
        )
        for k, v in dm.ca_events_idx.items():
            npz_payload[f"ca_events_{k}"] = np.asarray(v)

    if dm.miniscope_phases is not None:
        npz_payload["miniscope_phases"] = np.asarray(dm.miniscope_phases)

    if dm.PSD_spect is not None:
        npz_payload["PSD_spect"] = dm.PSD_spect
        npz_payload["t_spect"] = np.asarray(dm.t_spect)
        npz_payload["freqs_spect"] = np.asarray(dm.freqs_spect)
        npz_payload["p_spect"] = dm.p_spect

    if dm.projections is not None and dm.projections.time is not None:
        npz_payload["mean_fluorescence_time"] = np.asarray(dm.projections.time)

    if dm.filter_object is not None:
        fo = dm.filter_object
        npz_payload["filtered_mean_fluorescence"] = np.asarray(fo.filtered_data)

    npz_path = os.path.join(saved_movies_dir, OUTPUT_NPZ_FILENAME)
    if npz_payload:
        print(f"Saving postprocessed arrays to {npz_path}")
        np.savez_compressed(npz_path, **npz_payload)
    else:
        print("Warning: No numpy arrays to save (unexpected).")

    meta = {
        "line_num": line_num,
        "frame_rate_hz": float(dm.fr) if getattr(dm, "fr", None) is not None else None,
        "outputs": {
            "cnmf_estimates": OUTPUT_CNMFE_FILENAME,
            "arrays": OUTPUT_NPZ_FILENAME,
        },
    }
    if dm.filter_object is not None:
        fo = dm.filter_object
        meta["filter"] = {
            "n": fo.n,
            "cut": list(fo.cut) if hasattr(fo.cut, "__iter__") and not isinstance(fo.cut, (str, bytes)) else fo.cut,
            "ftype": fo.ftype,
            "btype": fo.btype,
        }

    meta_path = os.path.join(saved_movies_dir, OUTPUT_META_FILENAME)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Wrote metadata to {meta_path}")


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
        dm = MiniscopeDataManager(line_num=line_num, filenames=[], auto_import_data=False)
        dm.import_metadata()
        
        # 2. Locate CNMF-E estimates from the headless supercomputer run (required inputs)
        saved_movies_dir = os.path.join(dm.metadata['calcium imaging directory'], "saved_movies")
        estimates_path = os.path.join(saved_movies_dir, 'please_work.hdf5')
        
        if not os.path.exists(estimates_path):
            print(f"Error: Estimates file not found at {estimates_path}")
            print("Did you run the supercomputer pipeline yet (e.g. MiniscopePipeline with --headless)?")
            continue
            
        # 3. Load the pre-computed CNMF-E estimates
        print(f"Loading CNMF-E estimates from {estimates_path}...")
        CNMFE_obj = cm.source_extraction.cnmf.cnmf.load_CNMF(estimates_path)
        dm.CNMFE_obj = CNMFE_obj
        # Frame rate was not loaded via load_attributes(); take it from the saved CNMF params (HPC run).
        if getattr(dm, "fr", None) is None:
            dm.fr = float(CNMFE_obj.params.get("data", "fr"))

        # 4. Load the memory-mapped movie used during processing
        mmap_filepath = CNMFE_obj.params.get('data', 'fnames')

        # bug here used AI to fix
        if isinstance(mmap_filepath, np.ndarray):
            mmap_filepath = mmap_filepath.flatten()[0]
        elif isinstance(mmap_filepath, (list, tuple)):
            mmap_filepath = mmap_filepath[0]

        # Handle bytes (common when path was saved on Linux HPC, loaded on Mac)
        if isinstance(mmap_filepath, bytes):
            mmap_filepath = mmap_filepath.decode('utf-8')
        else:
            mmap_filepath = str(mmap_filepath)
            
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

        # 6. Save all postprocessed results to disk
        save_postprocessed_results(dm, line_num, saved_movies_dir)
        
        print(f"\nFinished local post-processing for experiment {line_num}!")

if __name__ == '__main__':
    main()
