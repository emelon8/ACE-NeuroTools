#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Residual Analysis Tool for Finding Missed Neurons (False Negatives)

This module provides tools to analyze CNMF-E residuals and identify potential
neurons that were missed during cell detection. The main strategy is to compute
the Max Projection of Residuals - if a neuron was missed, it will flash 
occasionally in the residual data, and a max projection captures these flashes
as bright spots.

Usage:
------
    from src2.miniscope.residual_analysis import ResidualAnalyzer
    
    # After running CNMF-E processing:
    analyzer = ResidualAnalyzer(data_manager)
    analyzer.compute_residual_max_projection()
    analyzer.visualize_comparison()
    
    # Or use the interactive GUI:
    analyzer.launch_gui()

Created on: 2025
Author: MEL-LAB
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import FreeSimpleGUI as sg
import caiman as cm
from typing import Optional, Tuple
import os


class ResidualAnalyzer:
    """
    Analyzes CNMF-E residuals to find potential missed neurons (false negatives).
    
    The residual is calculated as: E = Y - AC - B
    Where:
        Y = raw data
        AC = detected neural activity (spatial footprints * temporal traces)
        B = background model
    
    If a neuron was missed, its activity will appear in the residual E.
    A max projection of E over time reveals these missed neurons as bright spots.
    """
    
    def __init__(self, data_manager=None, cnmfe_obj=None, mmap_file=None):
        """
        Initialize the ResidualAnalyzer.
        
        Parameters:
        -----------
        data_manager : MiniscopeDataManager, optional
            Data manager containing CNMFE_obj and movie data
        cnmfe_obj : CNMF object, optional
            CaImAn CNMF object (alternative to data_manager)
        mmap_file : str, optional
            Path to memory-mapped file (if not using data_manager)
        """
        self.data_manager = data_manager
        
        if data_manager is not None:
            self.cnmfe_obj = data_manager.CNMFE_obj
            self.projections = data_manager.projections
            self.movie = data_manager.movie
        else:
            self.cnmfe_obj = cnmfe_obj
            self.projections = None
            self.movie = None
            
        self.mmap_file = mmap_file
        self.max_proj_residual = None
        self.dims = None
        self.T = None
        
    def compute_residual_max_projection(self, batch_size: int = 1000, 
                                         use_movie: bool = True,
                                         verbose: bool = True) -> np.ndarray:
        """
        Compute the max projection of residuals to find missed neurons.
        
        This processes the movie in chunks to save RAM. For each chunk:
        1. Load raw data
        2. Reconstruct signal (AC) and background (B)
        3. Calculate residual: E = Y - AC - B
        4. Update the running max projection
        
        Parameters:
        -----------
        batch_size : int
            Number of frames to process at a time (default: 1000)
        use_movie : bool
            If True, use self.movie directly. If False, load from mmap file.
        verbose : bool
            Print progress updates
            
        Returns:
        --------
        max_proj_residual : np.ndarray
            2D array of the max projection of residuals
        """
        if self.cnmfe_obj is None:
            raise ValueError("No CNMF-E object available. Run CNMF-E first or provide cnmfe_obj.")
        
        estimates = self.cnmfe_obj.estimates
        
        # Get movie dimensions and data
        if use_movie and self.movie is not None:
            # Use movie directly from data_manager
            T = self.movie.shape[0]
            dims = (self.movie.shape[1], self.movie.shape[2])
            self.dims = dims
            self.T = T
            
            if verbose:
                print(f"Computing residual max projection from movie...")
                print(f"Movie shape: {self.movie.shape}, Processing in batches of {batch_size}")
            
            # Initialize max projection
            max_proj_residual = np.zeros(np.prod(dims))
            
            # Check if movie dimensions match estimates (A matrix)
            movie_pixels = dims[0] * dims[1]
            estimate_pixels = estimates.A.shape[0]
            
            if movie_pixels != estimate_pixels:
                if verbose:
                    print(f"\n  ⚠ Dimension mismatch: movie has {movie_pixels} pixels, estimates have {estimate_pixels}")
                    print(f"  → Using simplified residual (max projection - reconstructed activity)")
                
                # Use simplified approach: just show max projection highlighting potential missed areas
                max_proj_raw = np.max(np.array(self.movie), axis=0)
                self.max_proj_residual = max_proj_raw
                self.dims = dims
                self._dimension_mismatch = True
                
                if verbose:
                    print(f"\n  ✓ Computed max projection (compare visually with detected neurons)")
                
                return self.max_proj_residual
            
            self._dimension_mismatch = False
            
            # Check background model dimensions (W matrix might be downsampled)
            skip_background = False
            ssub_B = 1  # Background spatial subsampling factor
            
            if hasattr(estimates, 'W') and estimates.W is not None:
                W_pixels = estimates.W.shape[1]
                if W_pixels != movie_pixels:
                    # Calculate downsampling factor
                    ratio = movie_pixels / W_pixels
                    ssub_B = int(np.sqrt(ratio) + 0.5)  # Round to nearest int
                    expected_downsampled = (dims[0] // ssub_B) * (dims[1] // ssub_B)
                    
                    if abs(expected_downsampled - W_pixels) < 100:  # Allow some tolerance
                        if verbose:
                            print(f"  Background model W uses {ssub_B}x downsampling ({W_pixels} pixels)")
                            print(f"  → Will downsample Y, apply W, then upsample for background subtraction")
                    else:
                        if verbose:
                            print(f"  Note: Cannot determine background downsampling factor")
                            print(f"  → Will use b0 (mean background) only")
                        skip_background = True
            
            # Process in chunks
            for i in range(0, T, batch_size):
                end_idx = min(i + batch_size, T)
                
                if verbose:
                    print(f"  Processing frames {i} to {end_idx} of {T}...", end='\r')
                
                # Get chunk of raw data and reshape to (pixels, frames)
                Y_chunk = self.movie[i:end_idx, :, :].reshape(-1, end_idx - i, order='F').T
                Y_chunk = Y_chunk.T  # Now (pixels, frames)
                
                # Reconstruct Signal: AC = A @ C
                AC_chunk = estimates.A.dot(estimates.C[:, i:end_idx])
                
                # Reconstruct Background - with dimension checking and downsampling
                B_chunk = np.zeros_like(AC_chunk)
                if not skip_background:
                    try:
                        if hasattr(estimates, 'W') and estimates.W is not None and ssub_B > 1:
                            # Downsample Y_chunk, apply ring model W, then upsample
                            from scipy.ndimage import zoom
                            n_frames = Y_chunk.shape[1]
                            dims_ds = (self.dims[0] // ssub_B, self.dims[1] // ssub_B)
                            
                            # Reshape to 2D images for downsampling
                            Y_2d = Y_chunk.reshape(self.dims + (n_frames,), order='F')
                            
                            # Downsample spatially
                            Y_down = zoom(Y_2d, (1/ssub_B, 1/ssub_B, 1), order=1)
                            Y_down_flat = Y_down.reshape(-1, n_frames, order='F')
                            
                            # Apply W (ring model): B_ds = W @ Y_ds
                            B_down = estimates.W.dot(Y_down_flat)
                            
                            # Reshape and upsample
                            B_down_2d = B_down.reshape(dims_ds + (n_frames,), order='F')
                            B_up = zoom(B_down_2d, (ssub_B, ssub_B, 1), order=1)
                            
                            # Handle any size mismatch from rounding
                            B_up = B_up[:self.dims[0], :self.dims[1], :]
                            B_chunk = B_up.reshape(-1, n_frames, order='F')
                            
                            # Add mean background b0
                            if hasattr(estimates, 'b0') and estimates.b0 is not None:
                                B_chunk = B_chunk + estimates.b0[:, None]
                                
                        elif hasattr(estimates, 'W') and estimates.W is not None:
                            # No downsampling needed
                            B_chunk = estimates.W.dot(Y_chunk) + estimates.b0[:, None]
                        elif hasattr(estimates, 'b') and estimates.b is not None:
                            if hasattr(estimates, 'f') and estimates.f is not None:
                                B_chunk = estimates.b.dot(estimates.f[:, i:end_idx])
                        elif hasattr(estimates, 'b0') and estimates.b0 is not None:
                            # Use just mean background
                            B_chunk = estimates.b0[:, None] * np.ones((1, Y_chunk.shape[1]))
                    except Exception as e:
                        if verbose and i == 0:
                            print(f"\n  ⚠ Background computation error: {e}")
                            import traceback
                            traceback.print_exc()
                            print(f"  → Using mean background (b0) only")
                        # Fall back to mean background
                        if hasattr(estimates, 'b0') and estimates.b0 is not None:
                            B_chunk = estimates.b0[:, None] * np.ones((1, Y_chunk.shape[1]))
                        else:
                            B_chunk = np.zeros_like(AC_chunk)
                
                # Calculate Residual: E = Y - AC - B
                E_chunk = Y_chunk - AC_chunk - B_chunk
                
                # Update global max projection (max across time axis)
                chunk_max = np.max(E_chunk, axis=1)
                max_proj_residual = np.maximum(max_proj_residual, chunk_max)
            
        else:
            # Load from memory-mapped file
            if self.mmap_file is None and hasattr(self.cnmfe_obj, 'mmap_file'):
                self.mmap_file = self.cnmfe_obj.mmap_file
                
            if self.mmap_file is None:
                raise ValueError("No mmap_file available. Provide mmap_file or use movie.")
            
            if verbose:
                print(f"Computing residual max projection from mmap file...")
                
            Yr, dims, T = cm.load_memmap(self.mmap_file)
            self.dims = dims
            self.T = T
            
            if verbose:
                print(f"Dims: {dims}, Frames: {T}, Processing in batches of {batch_size}")
            
            # Initialize max projection
            max_proj_residual = np.zeros(np.prod(dims))
            
            # Process in chunks
            for i in range(0, T, batch_size):
                idx = slice(i, min(i + batch_size, T))
                
                if verbose:
                    print(f"  Processing frames {i} to {min(i + batch_size, T)} of {T}...", end='\r')
                
                # Load chunk of raw data
                Y_chunk = np.array(Yr[:, idx])
                
                # Reconstruct Signal: AC = A @ C
                AC_chunk = estimates.A.dot(estimates.C[:, idx])
                
                # Reconstruct Background
                if hasattr(estimates, 'W') and estimates.W is not None:
                    B_chunk = estimates.W.dot(Y_chunk) + estimates.b0[:, None]
                elif hasattr(estimates, 'b') and estimates.b is not None:
                    if hasattr(estimates, 'f') and estimates.f is not None:
                        B_chunk = estimates.b.dot(estimates.f[:, idx])
                    else:
                        B_chunk = np.zeros_like(Y_chunk)
                else:
                    B_chunk = np.zeros_like(Y_chunk)
                
                # Calculate Residual: E = Y - AC - B
                E_chunk = Y_chunk - AC_chunk - B_chunk
                
                # Update global max projection
                chunk_max = np.max(E_chunk, axis=1)
                max_proj_residual = np.maximum(max_proj_residual, chunk_max)
        
        if verbose:
            print("\n✓ Residual max projection computed successfully!")
        
        self.max_proj_residual = max_proj_residual.reshape(self.dims, order='F')
        return self.max_proj_residual
    
    def visualize_comparison(self, figsize: Tuple[int, int] = (16, 5),
                             save_path: Optional[str] = None,
                             show_contours: bool = True) -> plt.Figure:
        """
        Create a side-by-side comparison visualization.
        
        Shows:
        1. Max projection of raw movie (for reference)
        2. Max projection of residuals (bright spots = potential missed neurons)
        3. Detected neurons overlaid on residuals
        
        Parameters:
        -----------
        figsize : tuple
            Figure size (width, height)
        save_path : str, optional
            Path to save the figure
        show_contours : bool
            Whether to show detected neuron contours
            
        Returns:
        --------
        fig : matplotlib.Figure
        """
        if self.max_proj_residual is None:
            print("Computing residual max projection first...")
            self.compute_residual_max_projection()
        
        fig, axes = plt.subplots(1, 3, figsize=figsize)
        
        # 1. Max projection of raw movie
        if self.projections is not None and hasattr(self.projections, 'max'):
            max_proj_raw = self.projections.max
        elif self.movie is not None:
            max_proj_raw = np.max(np.array(self.movie), axis=0)
        else:
            max_proj_raw = np.zeros(self.dims)
            
        ax1 = axes[0]
        im1 = ax1.imshow(max_proj_raw, cmap='gray')
        ax1.set_title('Max Projection (Raw Movie)', fontsize=12, fontweight='bold')
        ax1.axis('off')
        plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
        
        # 2. Max projection of residuals
        ax2 = axes[1]
        vmin = np.percentile(self.max_proj_residual, 1)
        vmax = np.percentile(self.max_proj_residual, 99)
        im2 = ax2.imshow(self.max_proj_residual, cmap='hot', vmin=vmin, vmax=vmax)
        
        if hasattr(self, '_dimension_mismatch') and self._dimension_mismatch:
            ax2.set_title('Max Projection (Raw)\n⚠ Dimensions mismatch - compare visually', 
                          fontsize=12, fontweight='bold')
        else:
            ax2.set_title('Max Projection of Residuals\n(Bright spots = potential missed neurons)', 
                          fontsize=12, fontweight='bold')
        ax2.axis('off')
        plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
        
        # 3. Residuals with detected neuron contours overlaid
        ax3 = axes[2]
        im3 = ax3.imshow(self.max_proj_residual, cmap='hot', vmin=vmin, vmax=vmax)
        ax3.set_title('Residuals with Detected Neurons\n(Red = detected, check for bright spots outside)', 
                      fontsize=12, fontweight='bold')
        ax3.axis('off')
        plt.colorbar(im3, ax=ax3, fraction=0.046, pad=0.04)
        
        # Overlay detected neuron contours
        if show_contours and self.cnmfe_obj is not None:
            estimates = self.cnmfe_obj.estimates
            coordinates = cm.utils.visualization.get_contours(
                estimates.A, self.dims, thr_method='max', thr=0.2, swap_dim=False
            )
            for c in coordinates:
                v = c['coordinates']
                ax3.plot(*v.T, c='cyan', linewidth=1, alpha=0.7)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"✓ Figure saved to {save_path}")
        
        plt.show()
        return fig
    
    def launch_gui(self):
        """
        Launch an interactive GUI for exploring residuals and finding missed neurons.
        
        The GUI shows:
        - Left: Max projection with detected neurons
        - Right: Max projection of residuals
        - Controls for adjusting visualization
        """
        if self.max_proj_residual is None:
            print("Computing residual max projection first...")
            self.compute_residual_max_projection()
        
        # Get max projection for comparison
        if self.projections is not None and hasattr(self.projections, 'max'):
            max_proj_raw = self.projections.max
        elif self.movie is not None:
            max_proj_raw = np.max(np.array(self.movie), axis=0)
        else:
            max_proj_raw = np.zeros(self.dims)
        
        # GUI Layout
        layout = [
            [sg.Text('Residual Analysis - Find Missed Neurons', font='Helvetica 18 bold')],
            [sg.Text('Bright spots in the residual image that are NOT circled may be missed neurons', 
                     font='Helvetica 12 italic')],
            [sg.HorizontalSeparator()],
            [
                sg.Column([
                    [sg.Text('Max Projection with Detected Neurons', font='Helvetica 14 bold')],
                    [sg.Canvas(size=(450, 400), key='-CANVAS_RAW-', pad=(5,5))]
                ]),
                sg.Column([
                    [sg.Text('Max Projection of Residuals', font='Helvetica 14 bold')],
                    [sg.Canvas(size=(450, 400), key='-CANVAS_RESIDUAL-', pad=(5,5))]
                ])
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Text('Residual Colormap:', font='Helvetica 12'),
                sg.Combo(['hot', 'viridis', 'plasma', 'inferno', 'magma', 'jet', 'coolwarm'], 
                         default_value='hot', key='-CMAP-', enable_events=True, readonly=True),
                sg.Text('Contrast (percentile):', font='Helvetica 12'),
                sg.Slider(range=(90, 100), default_value=99, orientation='h', size=(15, 15), 
                          key='-CONTRAST-', enable_events=True),
                sg.Checkbox('Show Contours', default=True, key='-SHOW_CONTOURS-', enable_events=True)
            ],
            [sg.HorizontalSeparator()],
            [
                sg.Button('Recompute Residuals', key='-RECOMPUTE-', size=(18, 1)),
                sg.Button('Save Figure', key='-SAVE-', size=(12, 1)),
                sg.Button('Close', key='-CLOSE-', size=(10, 1))
            ]
        ]
        
        window = sg.Window('Residual Analysis - Find Missed Neurons', layout, 
                           finalize=True, resizable=True, element_justification='center')
        
        # Get canvas elements
        canvas_raw = window['-CANVAS_RAW-'].TKCanvas
        canvas_residual = window['-CANVAS_RESIDUAL-'].TKCanvas
        
        figure_agg_raw = None
        figure_agg_residual = None
        
        def draw_figures(cmap='hot', contrast=99, show_contours=True):
            nonlocal figure_agg_raw, figure_agg_residual
            
            # Clear old figures
            if figure_agg_raw:
                figure_agg_raw.get_tk_widget().forget()
            if figure_agg_residual:
                figure_agg_residual.get_tk_widget().forget()
            plt.close('all')
            
            # Create raw projection figure with contours
            fig_raw = matplotlib.figure.Figure(figsize=(4.5, 4), dpi=100)
            ax_raw = fig_raw.add_subplot(111)
            ax_raw.imshow(max_proj_raw, cmap='gray')
            ax_raw.set_title('Detected Neurons', fontsize=10)
            ax_raw.axis('off')
            
            # Draw contours
            if show_contours and self.cnmfe_obj is not None:
                estimates = self.cnmfe_obj.estimates
                coordinates = cm.utils.visualization.get_contours(
                    estimates.A, self.dims, thr_method='max', thr=0.2, swap_dim=False
                )
                for c in coordinates:
                    v = c['coordinates']
                    ax_raw.plot(*v.T, c='red', linewidth=1.5)
            
            fig_raw.tight_layout()
            figure_agg_raw = FigureCanvasTkAgg(fig_raw, canvas_raw)
            figure_agg_raw.draw()
            figure_agg_raw.get_tk_widget().pack(side='top', fill='both', expand=1)
            
            # Create residual figure
            fig_residual = matplotlib.figure.Figure(figsize=(4.5, 4), dpi=100)
            ax_residual = fig_residual.add_subplot(111)
            vmin = np.percentile(self.max_proj_residual, 100 - contrast)
            vmax = np.percentile(self.max_proj_residual, contrast)
            ax_residual.imshow(self.max_proj_residual, cmap=cmap, vmin=vmin, vmax=vmax)
            ax_residual.set_title('Residuals (bright = potential missed)', fontsize=10)
            ax_residual.axis('off')
            
            # Draw contours on residual too
            if show_contours and self.cnmfe_obj is not None:
                for c in coordinates:
                    v = c['coordinates']
                    ax_residual.plot(*v.T, c='cyan', linewidth=1.5, alpha=0.7)
            
            fig_residual.tight_layout()
            figure_agg_residual = FigureCanvasTkAgg(fig_residual, canvas_residual)
            figure_agg_residual.draw()
            figure_agg_residual.get_tk_widget().pack(side='top', fill='both', expand=1)
        
        # Initial draw
        draw_figures()
        
        # Event loop
        while True:
            event, values = window.read()
            
            if event in (sg.WINDOW_CLOSED, '-CLOSE-'):
                break
            
            if event in ('-CMAP-', '-CONTRAST-', '-SHOW_CONTOURS-'):
                draw_figures(
                    cmap=values['-CMAP-'],
                    contrast=values['-CONTRAST-'],
                    show_contours=values['-SHOW_CONTOURS-']
                )
            
            if event == '-RECOMPUTE-':
                print("Recomputing residuals...")
                self.compute_residual_max_projection()
                draw_figures(
                    cmap=values['-CMAP-'],
                    contrast=values['-CONTRAST-'],
                    show_contours=values['-SHOW_CONTOURS-']
                )
            
            if event == '-SAVE-':
                # Save comparison figure
                if self.data_manager is not None:
                    save_dir = os.path.join(
                        self.data_manager.metadata['calcium imaging directory'], 
                        'saved_movies'
                    )
                else:
                    save_dir = '.'
                os.makedirs(save_dir, exist_ok=True)
                save_path = os.path.join(save_dir, 'residual_analysis.png')
                self.visualize_comparison(save_path=save_path, show_contours=values['-SHOW_CONTOURS-'])
                sg.popup(f'Figure saved to:\n{save_path}', title='Saved')
        
        plt.close('all')
        window.close()


def analyze_residuals(data_manager, batch_size: int = 1000, launch_gui: bool = True):
    """
    Convenience function to analyze residuals for missed neurons.
    
    Parameters:
    -----------
    data_manager : MiniscopeDataManager
        Data manager with CNMFE_obj populated
    batch_size : int
        Frames to process at a time
    launch_gui : bool
        Whether to launch the interactive GUI
        
    Returns:
    --------
    analyzer : ResidualAnalyzer
        The analyzer object with computed residuals
        
    Example:
    --------
    >>> from src2.miniscope.residual_analysis import analyze_residuals
    >>> analyzer = analyze_residuals(miniscope_data_manager)
    """
    analyzer = ResidualAnalyzer(data_manager)
    analyzer.compute_residual_max_projection(batch_size=batch_size)
    
    if launch_gui:
        analyzer.launch_gui()
    else:
        analyzer.visualize_comparison()
    
    return analyzer


if __name__ == "__main__":
    print("=" * 60)
    print("RESIDUAL ANALYSIS TOOL - Find Missed Neurons")
    print("=" * 60)
    print("""
    This tool helps identify false negatives (missed neurons) in your
    CNMF-E results by analyzing the residuals.
    
    Usage:
    ------
    1. Run your normal miniscope processing pipeline
    2. After CNMF-E completes, run:
    
        from src2.miniscope.residual_analysis import analyze_residuals
        analyzer = analyze_residuals(your_data_manager)
    
    What to look for:
    -----------------
    - Bright circular spots in the residual image
    - Spots that do NOT have a cyan/red contour around them
    - These are potential missed neurons!
    
    If you find many missed neurons, consider:
    - Lowering the minimum SNR threshold in CNMF-E parameters
    - Adjusting the spatial constraints
    - Using different initialization methods
    """)
