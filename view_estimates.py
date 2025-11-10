#!/usr/bin/env python3
"""
Quick script to visualize the saved CNMF-E estimates
"""
import caiman as cm
import matplotlib.pyplot as plt
import numpy as np

# Load the estimates
estimates_path = '/Users/jacefranco/Documents/MEL-LAB/experiment_analysis/movies/saved_movies/estimates.hdf5'
cnmf_obj = cm.source_extraction.cnmf.cnmf.load_CNMF(estimates_path)
estimates = cnmf_obj.estimates

print(f"Number of components found: {estimates.C.shape[0]}")
print(f"Number of frames: {estimates.C.shape[1]}")
print(f"Image dimensions: {cnmf_obj.dims}")

# Option 1: View contour plot of all cells
print("\nPlotting cell contours...")
estimates.plot_contours()
plt.title('Spatial Footprints of All Cells')
plt.show()

# Option 2: View temporal traces for first 10 cells
print("\nPlotting calcium traces...")
fig, axes = plt.subplots(min(10, estimates.C.shape[0]), 1, figsize=(12, 8), sharex=True)
if estimates.C.shape[0] == 1:
    axes = [axes]
    
for i in range(min(10, estimates.C.shape[0])):
    axes[i].plot(estimates.C[i], linewidth=0.5)
    axes[i].set_ylabel(f'Cell {i}')
    axes[i].spines['top'].set_visible(False)
    axes[i].spines['right'].set_visible(False)

axes[-1].set_xlabel('Frame Number')
fig.suptitle('Calcium Traces (Denoised)')
plt.tight_layout()
plt.show()

# Option 3: View individual cell components
print("\nPlotting first 6 cell components...")
try:
    # Try to use correlation image if available
    bg_img = cnmf_obj.estimates.Cn if hasattr(cnmf_obj.estimates, 'Cn') else None
    estimates.view_components(img=bg_img, idx=list(range(min(6, estimates.C.shape[0]))))
except Exception as e:
    print(f"Could not plot individual components: {e}")
    print("This is okay - the contours and traces above show your data!")

print("\nData available in estimates:")
print(f"  - C: Denoised calcium traces, shape {estimates.C.shape}")
print(f"  - S: Spike/event traces, shape {estimates.S.shape}")
print(f"  - A: Spatial components, shape {estimates.A.shape}")
print(f"  - b: Background spatial components")
print(f"  - f: Background temporal components")
print(f"  - Cn: Correlation image for background")

# Save summary statistics
print("\nSummary statistics:")
for i in range(min(5, estimates.C.shape[0])):
    mean_activity = np.mean(estimates.C[i])
    max_activity = np.max(estimates.C[i])
    print(f"  Cell {i}: Mean activity = {mean_activity:.2f}, Max activity = {max_activity:.2f}")

