#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Nov 24 15:15:05 2025

@author: sandbox1
"""


    
#SHOWS YOU ALL THE ESTIMATES AND PULLS A FEW FOR YOUR VIEWING

    
import h5py
import numpy as np
h5_path = "/Users/sandbox1/Desktop/Research/experiment_analysis/avi_vids/R230706A/2023_09_04/15_06_16/saved_movies/estimates.hdf5"

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
                
                



if __name__ == "__main__":
    pull_arrays()

    
    
    