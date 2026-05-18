#!/usr/bin/env python3
"""
Standalone Neuron Selector Utility
----------------------------------
A portable, single-file GUI for culling neurons from CaImAn HDF5 outputs.
Displays spatial contours and temporal traces side-by-side.

Dependencies:
    - caiman
    - PySimpleGUI (or FreeSimpleGUI)
    - matplotlib
    - numpy
    - pandas
"""

import base64
import io
import os
import sys
from typing import Any

import FreeSimpleGUI as sg
import matplotlib.pyplot as plt
import numpy as np
from caiman.source_extraction.cnmf.cnmf import load_CNMF

# --- Self-Contained Helper Classes ---

class Projections:
    """Minimal projections container for the standalone GUI."""
    def __init__(self, background: np.ndarray):
        self.max = background
        self.mean = background
        self.std = background
        self.median = background
        self.min = background
        self.range = background

def get_contours(A, dims, thr=0.2):
    """Simplified contour extraction logic from CaImAn."""
    import caiman as cm
    return cm.utils.visualization.get_contours(A, dims, thr, 'max', swap_dim=False)

# --- GUI Drawing Functions ---

def create_combined_fig(estimates, active_idx, background, coordinates, dpi=100):
    """Creates a matplotlib figure with spatial contours and the active trace."""
    h, w = np.shape(background)
    
    # We create a figure with two subplots: Spatial (left) and Temporal (right)
    fig = plt.Figure(figsize=(12, 5), dpi=dpi)
    
    # --- Spatial Subplot ---
    ax_spatial = fig.add_subplot(1, 2, 1)
    ax_spatial.imshow(background, interpolation='nearest', cmap='viridis')
    ax_spatial.set_xlim(-0.5, w - 0.5)
    ax_spatial.set_ylim(h - 0.5, -0.5)
    ax_spatial.set_aspect('equal')
    ax_spatial.set_axis_off()
    ax_spatial.set_title("Spatial Contours")

    bad_set = set(estimates.idx_components_bad) if estimates.idx_components_bad else set()

    for i, c in enumerate(coordinates):
        v = c['coordinates']
        is_bad = i in bad_set
        is_active = (i == active_idx)
        
        color = 'cyan' if is_active else ('red' if is_bad else 'white')
        linewidth = 2 if is_active else 0.8
        alpha = 1.0 if (is_active or not is_bad) else 0.3
        
        ax_spatial.plot(*v.T, color=color, linewidth=linewidth, alpha=alpha)
        
        # Draw number for active one or if not too many
        if is_active or len(coordinates) < 50:
            com = v.mean(axis=0)
            ax_spatial.text(com[0], com[1], str(i + 1), color=color, fontsize=8)

    # --- Temporal Subplot ---
    ax_temporal = fig.add_subplot(1, 2, 2)
    if active_idx is not None and active_idx < len(estimates.C):
        trace = estimates.C[active_idx]
        ax_temporal.plot(trace, color='cyan')
        ax_temporal.set_title(f"Neuron {active_idx + 1} Trace (Denoised)")
        ax_temporal.set_xlabel("Frames")
        ax_temporal.set_ylabel("Fluorescence")
    else:
        ax_temporal.text(0.5, 0.5, "Select a neuron to see trace", ha='center')
    
    fig.tight_layout()
    return fig

def update_gui_image(window, estimates, active_idx, background, coordinates):
    """Renders the figure to the GUI Graph element."""
    graph = window['-GRAPH-']
    graph.erase()
    
    fig = create_combined_fig(estimates, active_idx, background, coordinates)
    
    pic_IObytes = io.BytesIO()
    fig.savefig(pic_IObytes, format='png', bbox_inches='tight')
    plt.close(fig)
    
    pic_IObytes.seek(0)
    pic_data = pic_IObytes.read()
    pic_hash = base64.b64encode(pic_data)
    
    # We use a large enough location to center it or just 0,0
    graph.draw_image(data=pic_hash, location=(0, 0))

# --- Main Logic ---

def standalone_selector():
    sg.theme('DarkGrey5')
    
    # --- Step 1: File Selection ---
    file_layout = [
        [sg.Text("Select CaImAn HDF5 Results File:")],
        [sg.Input(key="-HDF5-"), sg.FileBrowse(file_types=(("HDF5 Files", "*.hdf5"),))],
        [sg.Text("Select Background Movie (Optional, .mmap or .avi):")],
        [sg.Input(key="-MOVIE-"), sg.FileBrowse(file_types=(("Memory Map", "*.mmap"), ("AVI Video", "*.avi"), ("All Files", "*.*")))],
        [sg.Button("Load Data"), sg.Button("Exit")]
    ]
    
    launcher = sg.Window("Neuron Selector Launcher", file_layout)
    
    cnmf_obj = None
    estimates = None
    background = None
    hdf5_path = ""
    
    while True:
        event, values = launcher.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            launcher.close()
            return
        
        if event == "Load Data":
            hdf5_path = values["-HDF5-"]
            movie_path = values["-MOVIE-"]
            
            if not os.path.exists(hdf5_path):
                sg.popup_error("HDF5 file not found!")
                continue
            
            try:
                print(f"Loading results from {hdf5_path}...")
                cnmf_obj = load_CNMF(hdf5_path)
                estimates = cnmf_obj.estimates
                
                # Try to find a background
                if movie_path and os.path.exists(movie_path):
                    import caiman as cm
                    print(f"Loading movie for background from {movie_path}...")
                    m = cm.load(movie_path)
                    background = np.array(np.std(m, axis=0)) # Use STD as a good default
                elif hasattr(estimates, 'Cn') and estimates.Cn is not None:
                    print("Using correlation image from HDF5 as background.")
                    background = estimates.Cn
                elif hasattr(estimates, 'A') and estimates.A is not None:
                    print("No background found, using mean spatial footprint as proxy.")
                    # Fallback: sum of all spatial footprints
                    background = np.array(estimates.A.sum(axis=1).reshape(estimates.dims, order='F'))
                else:
                    print("Warning: No spatial footprints (A) or background found.")
                    # Last resort: solid black background
                    if hasattr(estimates, 'dims') and estimates.dims is not None:
                        background = np.zeros(estimates.dims)
                    else:
                        background = np.zeros((100, 100)) # Placeholder
                
                launcher.close()
                break
            except Exception as e:
                import traceback
                traceback.print_exc()
                sg.popup_error(f"Failed to load data: {e}")
                continue

    # --- Step 2: Main GUI ---
    if estimates is None or estimates.A is None or estimates.C is None:
        sg.popup_error("Critical Error: The loaded HDF5 file is missing spatial (A) or temporal (C) components.\n\n"
                       "This usually means the file is corrupted, incomplete, or saved in an incompatible format.")
        return

    if estimates.idx_components_bad is None:
        estimates.idx_components_bad = []
    
    # Pre-calculate contours once for speed
    print("Calculating contours...")
    coordinates = get_contours(estimates.A, estimates.dims)
    active_idx = 0
    
    # Listbox values (1-based for users)
    neuron_list = [f"Neuron {i+1}" for i in range(len(estimates.C))]
    initial_bad = [neuron_list[i] for i in estimates.idx_components_bad]

    main_layout = [
        [sg.Text(f"Editing: {os.path.basename(hdf5_path)}", font=("Helvetica", 14))],
        [sg.Graph((1000, 500), (0, 500), (1000, 0), key='-GRAPH-', background_color='black')],
        [
            sg.Column([
                [sg.Text("Selection List (Select to Reject):")],
                [sg.Listbox(values=neuron_list, default_values=initial_bad, 
                            size=(20, 15), key='-LIST-', select_mode='multiple', 
                            enable_events=True, font=("Courier", 12))]
            ]),
            sg.Column([
                [sg.Button("<< Previous", key="-PREV-"), sg.Button("Next >>", key="-NEXT-")],
                [sg.Text("_" * 30)],
                [sg.Text("Keyboard Shortcuts:\n- Use arrows to navigate list\n- Hold Ctrl to multi-select")],
                [sg.VerticalSeparator()],
                [sg.Button("Cancel", button_color='red'), sg.Button("Submit & Save", button_color='green')]
            ])
        ]
    ]

    window = sg.Window("Standalone Neuron Selector", main_layout, finalize=True)
    
    # Initial Draw
    update_gui_image(window, estimates, active_idx, background, coordinates)

    while True:
        event, values = window.read()
        
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
            
        if event == '-LIST-':
            # Update the active index to the last clicked item
            selected_strings = values['-LIST-']
            if selected_strings:
                # We find the one that was most recently interacted with
                # For simplicity, we just take the first one in the selection for the trace
                new_active = int(selected_strings[0].split()[1]) - 1
                if new_active != active_idx:
                    active_idx = new_active
                    update_gui_image(window, estimates, active_idx, background, coordinates)

        if event == "-NEXT-":
            active_idx = (active_idx + 1) % len(estimates.C)
            window['-LIST-'].set_value([neuron_list[active_idx]]) # Auto-scrolls?
            update_gui_image(window, estimates, active_idx, background, coordinates)

        if event == "-PREV-":
            active_idx = (active_idx - 1) % len(estimates.C)
            update_gui_image(window, estimates, active_idx, background, coordinates)

        if event == "Submit & Save":
            # Convert GUI strings back to 0-based indices
            rejected_names = values['-LIST-']
            rejected_indices = sorted([int(name.split()[1]) - 1 for name in rejected_names])
            
            # Confirm with user
            num_keep = len(estimates.C) - len(rejected_indices)
            if sg.popup_yes_no(f"Accept {num_keep} neurons and reject {len(rejected_indices)}?\nThis will create a NEW HDF5 file.") == "Yes":
                save_path = sg.popup_get_file("Save culled estimates as...", save_as=True, 
                                             default_path=hdf5_path.replace(".hdf5", "_culled.hdf5"),
                                             file_types=(("HDF5 Files", "*.hdf5"),))
                if save_path:
                    # Perform the culling
                    good_indices = [i for i in range(len(estimates.C)) if i not in rejected_indices]
                    estimates.select_components(idx_components=good_indices)
                    cnmf_obj.save(save_path)
                    sg.popup(f"Successfully saved to:\n{save_path}")
                    break

    window.close()

if __name__ == "__main__":
    standalone_selector()
