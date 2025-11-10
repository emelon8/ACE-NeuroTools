#!/usr/bin/env python3
"""
Quick script to visualize the saved CNMF-E estimates and save plots to files
"""
import caiman as cm
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to save files
import matplotlib.pyplot as plt
import numpy as np
import os

# Load the estimates
estimates_path = '/Users/jacefranco/Documents/MEL-LAB/experiment_analysis/movies/saved_movies/estimates.hdf5'
output_dir = '/Users/jacefranco/Documents/MEL-LAB/experiment_analysis/movies/saved_movies/plots'
os.makedirs(output_dir, exist_ok=True)

print(f"Loading estimates from: {estimates_path}")
cnmf_obj = cm.source_extraction.cnmf.cnmf.load_CNMF(estimates_path)
estimates = cnmf_obj.estimates

print(f"\n{'='*60}")
print(f"ANALYSIS SUMMARY")
print(f"{'='*60}")
print(f"Number of components found: {estimates.C.shape[0]}")
print(f"Number of frames: {estimates.C.shape[1]}")
print(f"Image dimensions: {cnmf_obj.dims}")
print(f"{'='*60}\n")

# Plot 1: View contour plot of all cells
print("Creating cell contours plot...")
fig = plt.figure(figsize=(10, 10))
estimates.plot_contours()
plt.title(f'Spatial Footprints of All {estimates.C.shape[0]} Cells', fontsize=14)
contour_path = os.path.join(output_dir, 'cell_contours.png')
plt.savefig(contour_path, dpi=150, bbox_inches='tight')
print(f"  ✓ Saved: {contour_path}")
plt.close()

# Plot 2: View temporal traces for first 10 cells
print("Creating calcium traces plot...")
num_cells_to_plot = min(10, estimates.C.shape[0])
fig, axes = plt.subplots(num_cells_to_plot, 1, figsize=(14, 2*num_cells_to_plot), sharex=True)
if num_cells_to_plot == 1:
    axes = [axes]
    
for i in range(num_cells_to_plot):
    axes[i].plot(estimates.C[i], linewidth=0.8, color='steelblue')
    axes[i].set_ylabel(f'Cell {i}', fontsize=10)
    axes[i].spines['top'].set_visible(False)
    axes[i].spines['right'].set_visible(False)
    axes[i].grid(alpha=0.3)

axes[-1].set_xlabel('Frame Number', fontsize=12)
fig.suptitle(f'Calcium Traces (Denoised) - First {num_cells_to_plot} Cells', fontsize=14)
plt.tight_layout()
traces_path = os.path.join(output_dir, 'calcium_traces.png')
plt.savefig(traces_path, dpi=150, bbox_inches='tight')
print(f"  ✓ Saved: {traces_path}")
plt.close()

# Plot 3: All traces in one plot
print("Creating all traces overview plot...")
fig, ax = plt.subplots(figsize=(14, 8))
for i in range(estimates.C.shape[0]):
    # Normalize and offset each trace for visualization
    trace_norm = (estimates.C[i] - estimates.C[i].min()) / (estimates.C[i].max() - estimates.C[i].min() + 1e-10)
    ax.plot(trace_norm + i * 1.2, linewidth=0.5, alpha=0.8)
    
ax.set_xlabel('Frame Number', fontsize=12)
ax.set_ylabel('Cell Number (offset)', fontsize=12)
ax.set_title(f'All {estimates.C.shape[0]} Cell Traces (Normalized & Offset)', fontsize=14)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(alpha=0.3)
all_traces_path = os.path.join(output_dir, 'all_traces_overview.png')
plt.savefig(all_traces_path, dpi=150, bbox_inches='tight')
print(f"  ✓ Saved: {all_traces_path}")
plt.close()

# Plot 4: Activity heatmap
print("Creating activity heatmap...")
fig, ax = plt.subplots(figsize=(14, 8))
im = ax.imshow(estimates.C, aspect='auto', cmap='viridis', interpolation='nearest')
ax.set_xlabel('Frame Number', fontsize=12)
ax.set_ylabel('Cell Number', fontsize=12)
ax.set_title(f'Calcium Activity Heatmap - All {estimates.C.shape[0]} Cells', fontsize=14)
plt.colorbar(im, ax=ax, label='Fluorescence (a.u.)')
heatmap_path = os.path.join(output_dir, 'activity_heatmap.png')
plt.savefig(heatmap_path, dpi=150, bbox_inches='tight')
print(f"  ✓ Saved: {heatmap_path}")
plt.close()

# Print summary statistics
print(f"\n{'='*60}")
print("CELL ACTIVITY STATISTICS")
print(f"{'='*60}")
for i in range(min(10, estimates.C.shape[0])):
    mean_activity = np.mean(estimates.C[i])
    max_activity = np.max(estimates.C[i])
    std_activity = np.std(estimates.C[i])
    print(f"Cell {i:2d}: Mean={mean_activity:7.2f}, Max={max_activity:7.2f}, Std={std_activity:7.2f}")
    
if estimates.C.shape[0] > 10:
    print(f"... ({estimates.C.shape[0] - 10} more cells)")

print(f"\n{'='*60}")
print("DATA AVAILABLE IN ESTIMATES:")
print(f"{'='*60}")
print(f"  - C: Denoised calcium traces, shape {estimates.C.shape}")
print(f"  - S: Spike/event traces, shape {estimates.S.shape}")
print(f"  - A: Spatial components, shape {estimates.A.shape}")
print(f"  - b: Background spatial components")
print(f"  - f: Background temporal components")

print(f"\n{'='*60}")
print(f"ALL PLOTS SAVED TO:")
print(f"  {output_dir}")
print(f"{'='*60}")
print("\nGenerated files:")
print(f"  1. cell_contours.png - Shows where each cell is located")
print(f"  2. calcium_traces.png - Individual traces for first 10 cells")
print(f"  3. all_traces_overview.png - All cells at once")
print(f"  4. activity_heatmap.png - Color-coded activity matrix")
print("\nYou can open these image files to view your results!")



