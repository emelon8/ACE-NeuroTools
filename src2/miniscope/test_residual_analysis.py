#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Residual Analysis Tool

Run this after you have processed data with CNMF-E.

Usage:
    conda activate caiman
    cd /Users/jacefranco/Documents/MEL-LAB/experiment_analysis
    python src2/miniscope/test_residual_analysis.py
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set CaImAn data directory
os.environ["CAIMAN_DATA"] = '/Users/jacefranco/Documents/MEL-LAB/experiment_analysis/movies'

from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.residual_analysis import ResidualAnalyzer, analyze_residuals
import caiman as cm


def test_with_existing_estimates():
    """
    Test using existing estimates file from a previous CNMF-E run.
    """
    print("=" * 60)
    print("RESIDUAL ANALYSIS TEST")
    print("=" * 60)
    
    # Change this to your experiment line number
    LINE_NUM = 97  # Same as in miniscope_api.py
    
    print(f"\n1. Loading data for line {LINE_NUM}...")
    
    try:
        # Load the data manager (don't auto-load movie yet)
        dm = MiniscopeDataManager(line_num=LINE_NUM, filenames=['0.avi'], auto_import_data=False)
        dm.import_metadata()
        dm.import_analysis_parameters()
        
        # Check if estimates exist
        estimates_path = os.path.join(
            dm.metadata['calcium imaging directory'], 
            'saved_movies', 
            'estimates.hdf5'
        )
        
        # Look for preprocessed movie that matches the estimates
        preprocessed_path = os.path.join(
            dm.metadata['calcium imaging directory'],
            'saved_movies'
        )
        
        # Find preprocessed movie files in saved_movies
        preprocessed_movie = None
        if os.path.exists(preprocessed_path):
            # Look for preprocessed movies in priority order
            for pattern in ['preprocessed_crop_square.avi', 'preprocessed_crop.avi', 
                           'preprocessed.avi', '*.tif', '*.mmap']:
                for f in os.listdir(preprocessed_path):
                    if pattern.startswith('*'):
                        if f.endswith(pattern[1:]):
                            preprocessed_movie = os.path.join(preprocessed_path, f)
                            break
                    elif f == pattern:
                        preprocessed_movie = os.path.join(preprocessed_path, f)
                        break
                if preprocessed_movie:
                    break
        
        if os.path.exists(estimates_path):
            print(f"   ✓ Found estimates at: {estimates_path}")
            
            # Load the CNMF-E object with estimates
            print("\n2. Loading CNMF-E estimates...")
            dm.CNMFE_obj = cm.source_extraction.cnmf.cnmf.load_CNMF(estimates_path)
            n_neurons = dm.CNMFE_obj.estimates.C.shape[0]
            n_pixels = dm.CNMFE_obj.estimates.A.shape[0]
            print(f"   ✓ Loaded {n_neurons} detected neurons")
            print(f"   ✓ Estimates computed on {n_pixels} pixels")
            
            # Calculate expected dimensions
            import numpy as np
            side = int(np.sqrt(n_pixels))
            print(f"   ✓ Expected movie dimensions: ~{side}x{side}")
            
            # Load the correct movie (preprocessed/cropped)
            print("\n3. Loading movie that matches estimates...")
            
            # First try mmap file from opts_caiman.json or CNMF object
            mmap_file = None
            opts_path = os.path.join(dm.metadata['calcium imaging directory'], 'saved_movies', 'opts_caiman.json')
            
            if os.path.exists(opts_path):
                import json
                with open(opts_path) as f:
                    opts = json.load(f)
                    if 'data' in opts and 'fnames' in opts['data']:
                        mmap_file = opts['data']['fnames'][0]
                        print(f"   Found mmap from opts: {mmap_file}")
            
            if mmap_file and os.path.exists(mmap_file):
                print(f"   Loading from mmap file...")
                Yr, dims, T = cm.load_memmap(mmap_file)
                dm.movie = Yr.T.reshape((T,) + dims, order='F')
            elif preprocessed_movie and os.path.exists(preprocessed_movie):
                print(f"   Loading preprocessed movie: {preprocessed_movie}")
                dm.movie = cm.load(preprocessed_movie)
            elif hasattr(dm.CNMFE_obj, 'mmap_file') and dm.CNMFE_obj.mmap_file:
                print(f"   Loading from CNMF mmap: {dm.CNMFE_obj.mmap_file}")
                Yr, dims, T = cm.load_memmap(dm.CNMFE_obj.mmap_file)
                dm.movie = Yr.T.reshape((T,) + dims, order='F')
            else:
                # Fall back to loading original and warn
                print("   ⚠ Could not find preprocessed movie, loading original...")
                dm.load_attributes(['0.avi'])
                print(f"   ⚠ Movie shape {dm.movie.shape} may not match estimates!")
            
            print(f"   ✓ Movie loaded with shape: {dm.movie.shape}")
            
            # Verify dimensions match
            movie_pixels = dm.movie.shape[1] * dm.movie.shape[2]
            if movie_pixels != n_pixels:
                print(f"\n   ⚠ WARNING: Movie pixels ({movie_pixels}) != estimate pixels ({n_pixels})")
                print("   The CNMF-E was run on a different (likely more cropped) movie.")
                print("   Will show max projection for visual comparison instead.")
                print("\n   To get proper residual analysis:")
                print("   - Find the exact movie used for CNMF-E processing")
                print("   - Or re-run CNMF-E on this movie")
            
            # Create projections
            print("\n4. Computing projections...")
            from src2.miniscope.projections import Projections
            
            movie_data = np.array(dm.movie)
            proj_max = np.max(movie_data, axis=0)
            proj_std = np.std(movie_data, axis=0)
            proj_min = np.min(movie_data, axis=0)
            proj_mean = np.mean(movie_data, axis=0)
            proj_median = np.median(movie_data, axis=0)
            proj_range = proj_max - proj_min
            proj_time = np.arange(movie_data.shape[0]) / 30.0  # Default frame rate
            
            dm.projections = Projections(
                max=proj_max, std=proj_std, min=proj_min, 
                mean=proj_mean, median=proj_median, 
                range=proj_range, time=proj_time
            )
            print("   ✓ Projections computed")
            
            # Run residual analysis
            print("\n5. Running residual analysis...")
            print("   (This may take a moment for large movies...)")
            
            analyzer = analyze_residuals(dm, batch_size=500, launch_gui=True)
            
            print("\n✓ Test complete!")
            
        else:
            print(f"\n   ✗ No estimates found at: {estimates_path}")
            print("\n   You need to run CNMF-E first. Run:")
            print("   python src2/miniscope/miniscope_api.py")
            print("\n   Or specify a different estimates file path.")
            
    except Exception as e:
        print(f"\n   ✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_visualization_only():
    """
    Test just the visualization with synthetic data (no real data needed).
    """
    import numpy as np
    import matplotlib.pyplot as plt
    
    print("=" * 60)
    print("VISUALIZATION TEST (Synthetic Data)")
    print("=" * 60)
    
    # Create synthetic residual data with some "missed neurons"
    dims = (200, 200)
    residual = np.random.randn(*dims) * 10
    
    # Add some bright spots (simulated missed neurons)
    for _ in range(5):
        x, y = np.random.randint(20, 180, 2)
        residual[y-5:y+5, x-5:x+5] += 100
    
    # Visualize
    plt.figure(figsize=(8, 8))
    vmin = np.percentile(residual, 1)
    vmax = np.percentile(residual, 99)
    plt.imshow(residual, cmap='hot', vmin=vmin, vmax=vmax)
    plt.title("Synthetic Residual Max Projection\n(Bright spots are simulated missed neurons)")
    plt.colorbar(label='Intensity')
    plt.show()
    
    print("✓ Visualization test complete!")


if __name__ == "__main__":
    print("\nWhich test would you like to run?")
    print("1. Full test with existing CNMF-E estimates (requires processed data)")
    print("2. Visualization test only (synthetic data, no requirements)")
    
    choice = input("\nEnter 1 or 2: ").strip()
    
    if choice == "1":
        test_with_existing_estimates()
    elif choice == "2":
        test_visualization_only()
    else:
        print("Running full test by default...")
        test_with_existing_estimates()
