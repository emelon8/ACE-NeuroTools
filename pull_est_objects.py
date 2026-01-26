#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 24 15:15:05 2025

@author: sandbox1
"""

'''
THIS IS FOR GETTING THE C MATRIX FOR ANALYSIS
import h5py
import numpy as np

h5_path = "/Users/sandbox1/Desktop/Research/experiment_analysis/avi_vids/R230706A/2023_09_04/15_06_16/saved_movies/estimates.hdf5"

with h5py.File(h5_path, "r") as f:
    # go straight to the estimates group
    est = f["estimates"]

    # C is a plain dataset 
    C = est["C"][:]   # (K, T) array
    print("C shape:", C.shape)
    print(C)
    np.savetxt("C_matrix.csv", C, delimiter=",")
    np.save("C_matrix.npy", C)
    '''
    
#SHOWS YOU ALL THE ESTIMATES AND PULLS A FEW FOR YOUR VIEWING

    
import h5py
import numpy as np
import caiman as cm
import tifffile
from PIL import Image

from scipy.sparse import csc_matrix

h5_path = "/Users/sandbox1/Desktop/Research/experiment_analysis/avi_vids/R230706A/2023_09_04/15_06_16/saved_movies/estimates.hdf5"
def pull_arrays():
    with h5py.File(h5_path, 'r') as f:
        print("Keys in file:", list(f.keys()))
        print("Keys in estimates:", list(f['estimates'].keys()))
    
    # For sparse matrix A, you need to access its components
        estimates = f['estimates']
    
        dims = f['dims'][()]
        print(f"Movie dimensions (height, width): {dims}")
    
    # Check if A is stored as a group (sparse matrix components)
        if isinstance(estimates['A'], h5py.Group):
        # Reconstruct sparse matrix from its components
            A_data = estimates['A']['data'][()]
            A_indices = estimates['A']['indices'][()]
            A_indptr = estimates['A']['indptr'][()]
            A_shape = estimates['A']['shape'][()]
            A = csc_matrix((A_data, A_indices, A_indptr), shape=A_shape)
            C = estimates['C'][()]
            # After reconstructing A and loading C, add these print statements:

            print(f"\nA shape: {A.shape}")
            print(f"C shape: {C.shape}")

# View beginning of A (sparse matrix)
            print("\nFirst few elements of A (as dense):")
            print(A[:10, :5].toarray())  # First 10 rows, 5 columns

# View beginning of C
            print("\nFirst few elements of C:")
            print(C[:5, :10])  # First 5 rows, 10 columns
            print(f"Number of components: {C.shape[0]}")
            
            return A, C, dims
        else:
                # If it's a regular dataset
            A = estimates['A'][()]
            
            # Temporal components (these are usually regular arrays)
            C = estimates['C'][()]
            
            # Background components
            b = estimates['b'][()]
            f_background = estimates['f'][()]
            
            print(f"\nA shape: {A.shape}")
            print(f"C shape: {C.shape}")
            print(f"Number of components: {C.shape[0]}")
                
    # Deconvolved spikes (if available)
        if 'S' in estimates:
            S = estimates['S'][()]
            
            # Accepted components
            if 'idx_components' in estimates:
                idx_components = estimates['idx_components'][()]
               
                
def movie(A, C, dims):
    video_flat = A @ C
    video = video_flat.T.reshape(1000, dims[0], dims[1])
# Create CaImAn movie object directly from the numpy array
    tifffile.imwrite('reconstructed_video.tif', video.astype(np.float32))
    vid = cm.load('reconstructed_video.tif')
    movie = cm.movie(video)
    vid.play(fr=30, q_max=99.5, q_min=0.5)
# Play it directly
    movie.play(fr=30, q_max=99.5, q_min=0.5)
    
def extract_YrA(h5_path, C):
    with h5py.File(h5_path, 'r') as f:
        estimates = f['estimates']
        dims = f['dims'][()]
        H, W = dims[0], dims[1]
        # Get YrA
        YrA = estimates['YrA'][()]
        
        
        print(f"YrA shape: {YrA.shape}")
        print('\nfirst few elements of YrA:')
        print(YrA[:10, :10])
        
        K, T = YrA.shape 
        residual_flat = A @ YrA              # (H*W, T)
        residual_video = residual_flat.T.reshape(T, H, W)   # (T, H, W)
        
        mn = residual_video.min()
        mx = residual_video.max()
        scale = 255.0 / (mx - mn) if mx != mn else 0.0

        normal_video = np.clip((residual_video - mn) * scale, 0, 255).astype(np.uint8)
# normal_video shape: (1000, 292, 334)
        
        tifffile.imwrite("residual_movie.tif", normal_video)  # multi-page TIFF
        
        # YrA is typically (components, timepoints), so we need to handle it differently
        # It's the residual for each component, not the full spatial movie
        
        # If you want to visualize it as a movie, you might need to multiply by A
        # But let's first check what we have
        if len(YrA.shape) == 2:
            print(f"YrA is 2D: {YrA.shape}")
            # This is residuals per component over time
            # To make a spatial movie, we'd need: A @ YrA
            

            C = C.T
            # Create spatial residual movie
            residual_flat = C @ YrA
            residual_video = residual_flat.T.reshape(-1)
            
            # Save as TIFF
            tifffile.imwrite('YrA_residual_movie.tif', residual_video.astype(np.float32))
            print(f"Saved YrA residual movie with shape: {residual_video.shape}")
            
            return residual_video
        
def extract_R():
    pass


if __name__ == "__main__":
    #A, C, dims = pull_arrays()
    #movie(A, C, dims)
    #h5_path = "/Users/sandbox1/Desktop/Research/experiment_analysis/avi_vids/R230706A/2023_09_04/15_06_16/saved_movies/estimates.hdf5"
    #extract_YrA(h5_path, C)
    pull_arrays()
    
    
    