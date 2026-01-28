import numpy as np
import matplotlib.pyplot as plt
import caiman as cm
import io
import base64
import sys
from src2.miniscope.projections import Projections
from PIL import Image
import FreeSimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.figure

def _create_contour_fig(sfootprints, background, estimates_obj, thr=None, thr_method='max', maxthr=0.2, nrgthr=0.9, display_numbers=True, max_number=None,
                         cmap=None, unselectcolor='w', selectcolor='r', coordinates=None,
                         contour_args={}, number_args={}, show_all_contours=True):

    if thr is None:
        try:
            thr = {'nrg': nrgthr, 'max': maxthr}[thr_method]
        except KeyError:
            thr = maxthr
    else:
        thr_method = 'nrg'

    h, w = np.shape(background)
    dpi = 100 # Keep dpi consistent, it affects the final pixel dimensions of the saved image relative to figsize

    # Create figure and axes
    # fig, ax = plt.subplots(1, 1, figsize=(w/dpi, h/dpi), dpi=dpi) # Original line

    # FIX: Explicitly set the axes position to cover the entire figure
    fig = plt.Figure(figsize=(w/dpi, h/dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]) # [left, bottom, width, height] in figure coordinates (0 to 1)

    ax.imshow(background, interpolation='nearest', cmap=cmap)
    ax.set_xlim(-0.5, w - 0.5)
    ax.set_ylim(h - 0.5, -0.5)
    ax.set_aspect('equal', adjustable='box') # Keep aspect ratio equal

    # Remove axis ticks, labels, and borders
    ax.set_axis_off()
    # No need for fig.tight_layout here, as we've explicitly set the axes to fill the figure

    if coordinates is None:
        coordinates = cm.utils.visualization.get_contours(sfootprints, np.shape(background), thr, thr_method, swap_dim=False)

    bad_components_0based_set = set(estimates_obj.idx_components_bad)

    for c_idx, c in enumerate(coordinates):
        v = c['coordinates']
        component_id_1based = c.get('neuron_id') # This is the 1-based ID from get_contours
        if component_id_1based is None:
            continue

        component_id_0based_for_check = component_id_1based - 1

        is_bad = component_id_0based_for_check in bad_components_0based_set

        # Always show selected (bad) components in red, otherwise only show if toggle is on
        if is_bad:
            ax.plot(*v.T, c=selectcolor, **contour_args) # Red for rejected (always shown)
        elif show_all_contours:
            ax.plot(*v.T, c=unselectcolor, **contour_args) # White for good (only if toggle is on)

    if display_numbers:
        d1, d2 = np.shape(background)
        d, nr = np.shape(sfootprints)
        comp = cm.base.rois.com(sfootprints, d1, d2)
        if max_number is None:
            max_number = sfootprints.shape[1]
        for i in range(np.minimum(nr, max_number)):
            # The 'i' here is already 0-based, corresponding to estimates.A columns
            is_bad = i in bad_components_0based_set
            # Always show numbers for selected (bad) components, otherwise only show if toggle is on
            if is_bad:
                ax.text(comp[i, 1], comp[i, 0], str(i + 1), color=selectcolor, **number_args)
            elif show_all_contours:
                ax.text(comp[i, 1], comp[i, 0], str(i + 1), color=unselectcolor, **number_args)

    return fig


def _draw_figure(canvas, figure):
    """Helper function to draw matplotlib figure on FreeSimpleGUI canvas"""
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg


def _delete_figure_agg(figure_agg):
    """Helper function to delete figure from canvas"""
    if figure_agg:
        figure_agg.get_tk_widget().forget()
        plt.close('all')


def _create_time_series_plot(estimates, eeg_data=None, eeg_timestamps=None, selected_cells_1based=None, frame_rate=30):
    """
    Create a time series plot showing calcium traces and optionally EEG data for selected cells.
    
    Parameters:
    -----------
    estimates : caiman estimates object
        Contains calcium trace data in estimates.C
    eeg_data : numpy array, optional
        EEG/ephys data synchronized with the calcium imaging frames
    eeg_timestamps : numpy array, optional
        Time stamps for the EEG data
    selected_cells_1based : list, optional
        List of selected cell indices (1-based)
    frame_rate : float
        Frame rate of calcium imaging in Hz
    """
    fig = matplotlib.figure.Figure(figsize=(5, 4), dpi=100)
    
    if selected_cells_1based is None or len(selected_cells_1based) == 0:
        # No cells selected, show empty plot with instruction
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'Select a cell to view its time series', 
                ha='center', va='center', fontsize=14, transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        return fig
    
    # Determine number of subplots needed
    num_plots = 1  # At least calcium trace
    if eeg_data is not None:
        num_plots = 2  # Calcium trace + EEG
    
    # Create time axis for calcium data
    num_frames = estimates.C.shape[1]
    time_calcium = np.arange(num_frames) / frame_rate
    
    # Plot calcium traces for all selected cells
    ax1 = fig.add_subplot(num_plots, 1, 1)
    
    for cell_idx_1based in selected_cells_1based:
        cell_idx_0based = cell_idx_1based - 1
        if cell_idx_0based < estimates.C.shape[0]:
            calcium_trace = estimates.C[cell_idx_0based, :]
            ax1.plot(time_calcium, calcium_trace, label=f'Cell {cell_idx_1based}', alpha=0.7, linewidth=1.5)
    
    ax1.set_xlabel('Time (s)', fontsize=10, labelpad=8)
    ax1.set_ylabel('Calcium Signal (a.u.)', fontsize=10, labelpad=8)
    ax1.set_title('Calcium Trace', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, alpha=0.3)
    if len(selected_cells_1based) <= 10:  # Only show legend if not too many cells
        ax1.legend(fontsize=8, loc='upper right')
    ax1.tick_params(labelsize=9)
    
    # Plot EEG data if available
    if eeg_data is not None and num_plots == 2:
        ax2 = fig.add_subplot(num_plots, 1, 2)
        
        if eeg_timestamps is not None:
            time_eeg = eeg_timestamps
        else:
            # Assume EEG data is synchronized frame-by-frame
            if len(eeg_data) == num_frames:
                time_eeg = time_calcium
            else:
                time_eeg = np.arange(len(eeg_data)) / frame_rate
        
        ax2.plot(time_eeg, eeg_data, color='darkblue', linewidth=1, alpha=0.8)
        ax2.set_xlabel('Time (s)', fontsize=10, labelpad=8)
        ax2.set_ylabel('EEG Signal (μV)', fontsize=10, labelpad=8)
        ax2.set_title('EEG Time Series', fontsize=12, fontweight='bold', pad=10)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(labelsize=9)
    
    fig.tight_layout(pad=2.0, h_pad=3.0, w_pad=2.0)
    return fig


def _component_image(estimates, projections, movie, graph, max=False, min=False, STD=False, mean=False, median=False, range=False, cmap='viridis', scale_factor=1.0, show_all_contours=True):
    graph.erase()

    pic_IObytes = io.BytesIO()
    background_to_display = None
    if max:
        background_to_display = projections.max
    elif min:
        background_to_display = projections.min
    elif STD:
        background_to_display = projections.std
    elif mean:
        background_to_display = projections.mean
    elif median:
        background_to_display = projections.median
    elif range:
        background_to_display = projections.range

    if background_to_display is not None:
        if cmap not in plt.colormaps():
            print(f"Invalid colormap {cmap}, using 'viridis'")
            cmap = 'viridis'

        fig = _create_contour_fig(estimates.A, background_to_display, estimates, cmap=cmap, show_all_contours=show_all_contours)
        fig.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches=0)
        plt.close(fig)

        pic_IObytes.seek(0)
        pic_data = pic_IObytes.read()
        if not pic_data:
            print("Error: No image data generated")
            return
        
        # Scale the image if scale_factor != 1.0
        if scale_factor != 1.0:
            img = Image.open(io.BytesIO(pic_data))
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Save resized image to bytes
            pic_IObytes_resized = io.BytesIO()
            img_resized.save(pic_IObytes_resized, format='PNG')
            pic_IObytes_resized.seek(0)
            pic_data = pic_IObytes_resized.read()
        
        pic_hash = base64.b64encode(pic_data)

        graph.draw_image(data=pic_hash, location=(0, 0))

    else:
        print("No background to display")


def component_gui(movie, estimates, projections, eeg_data=None, eeg_timestamps=None, frame_rate=30):
    """
    Interactive GUI for selecting cell components to reject/keep.
    
    This GUI displays calcium imaging cell components overlaid on projection images,
    and shows calcium traces (and optionally EEG/ephys data) for selected cells in
    real-time as you select them.
    
    Parameters:
    -----------
    movie : numpy array
        The calcium imaging movie
    estimates : caiman estimates object
        Contains component data and calcium traces
    projections : Projections object
        Contains various projection images (max, min, mean, etc.)
    eeg_data : numpy array, optional
        EEG/ephys data synchronized with calcium imaging. If provided, will display
        EEG time series alongside calcium traces when cells are selected.
        Shape should be (n_timepoints,) where n_timepoints matches the number of
        calcium imaging frames, OR can be different length if eeg_timestamps provided.
    eeg_timestamps : numpy array, optional
        Time stamps for the EEG data (in seconds). If not provided, assumes synchronized
        frame-by-frame with calcium data.
    frame_rate : float, optional
        Frame rate of calcium imaging in Hz (default: 30)
    
    Returns:
    --------
    estimates : caiman estimates object
        Updated estimates with selected components
        
    Examples:
    ---------
    # Example 1: Basic usage without EEG data (original behavior)
    >>> estimates = component_gui(movie, estimates, projections)
    
    # Example 2: With EEG data synchronized frame-by-frame
    >>> # Assuming you have eeg_data that's been downsampled to match calcium frame rate
    >>> estimates = component_gui(movie, estimates, projections, 
    ...                           eeg_data=eeg_downsampled, 
    ...                           frame_rate=30)
    
    # Example 3: With EEG data at original sampling rate with timestamps
    >>> # For miniscope-ephys experiments where EEG is synced via TTL events
    >>> from src.classes import miniscope_ephys
    >>> obj = miniscope_ephys.miniscopeEphys(lineNum=35)
    >>> obj.importEphysData(channels='PFCLFPvsCBEEG')
    >>> obj.syncNeuralynxMiniscopeTimestamps(channel='PFCLFPvsCBEEG')
    >>> obj.findEphysIdxOfTTLEvents(channel='PFCLFPvsCBEEG')
    >>> 
    >>> # Extract EEG at calcium imaging time points
    >>> eeg_synced = obj.ephys['PFCLFPvsCBEEG'][obj.ephysIdxAllTTLEvents]
    >>> eeg_times = obj.tEphys['PFCLFPvsCBEEG'][obj.ephysIdxAllTTLEvents]
    >>> 
    >>> estimates = component_gui(movie, estimates, projections,
    ...                           eeg_data=eeg_synced,
    ...                           eeg_timestamps=eeg_times,
    ...                           frame_rate=obj.experiment['frameRate'])
    
    # Example 4: Integration with MiniscopePostprocessor
    >>> # In miniscope_postprocessor.py, modify the call:
    >>> # self.data_manager.CNMFE_obj.estimates = component_gui(
    >>> #     self.data_manager.movie, 
    >>> #     self.data_manager.CNMFE_obj.estimates, 
    >>> #     self.data_manager.projections,
    >>> #     eeg_data=your_eeg_data,  # Add your EEG data here
    >>> #     frame_rate=self.frame_rate
    >>> # )
    
    Notes:
    ------
    - The GUI will show a time series plot at the bottom that updates as you 
      select/deselect cells in the listbox
    - Multiple cells can be selected simultaneously, and their traces will be 
      shown overlaid on the same plot
    - The EEG data (if provided) is shown in a separate subplot below the calcium traces
    - Selected cells are marked in red on the spatial image and in the list
    """
    if estimates.idx_components_bad is None:
        estimates.idx_components_bad = [] 

    print(f'This is the movie shape after processing: {movie.shape}')
    print(f'Initial estimates.idx_components_bad: {estimates.idx_components_bad}')
    if eeg_data is not None:
        print(f'EEG data shape: {eeg_data.shape}')
        print(f'EEG time series visualization enabled')
    
    cmapOptions = ['viridis', 'jet', 'plasma', 'inferno', 'magma', 'cividis', 'Greys', 'Purples', 'Blues', 'Greens',
                   'Oranges', 'Reds', 'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu','GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray','bone','pink', 'spring', 'summer', 'autumn', 'winter', 'cool','Wistia', 'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu','RdYlBu','RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent','Dark2','Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b','tab20c']

    initial_listbox_selections_1based = [idx + 1 for idx in estimates.idx_components_bad]

    # Toggle state for showing all cell contours and numbers
    show_all_contours = True
    
    # Scale up the image display (1.25x by default)
    img_scale = 1.25
    initial_img_scale = img_scale
    
    # Store scale factor for use in image rendering
    window_scale_factor = img_scale
    
    # Viewport size (fixed window showing part of the canvas)
    viewport_width = min(int(movie.shape[2] * 1.25) + 20, 550)  # Smaller to fit screen
    viewport_height = min(int(movie.shape[1] * 1.25) + 20, 400)
    
    # Canvas should initially be sized for the initial zoom level
    # It will be dynamically resized when zoom changes
    canvas_width = int(movie.shape[2] * img_scale)
    canvas_height = int(movie.shape[1] * img_scale)
    
    # Coordinate system should match the canvas size to ensure proper alignment
    coord_width = int(movie.shape[2] * img_scale)
    coord_height = int(movie.shape[1] * img_scale)
    
    # Left column: image and controls
    left_column = [
        [sg.Text('Components', key='-TITLE-', font='Helvetica 20 bold')],
        [sg.Column(
            [[sg.Graph((canvas_width, canvas_height), (0, coord_height), (coord_width, 0), 
                      key='-GRAPH-', enable_events=True, background_color='black', pad=(0, 0))]],
            scrollable=True,
            vertical_scroll_only=False,
            size=(viewport_width, viewport_height),
            key='-SCROLL_COLUMN-',
            pad=(0, 0)
        )],
        [sg.Text("Zoom:", font='Helvetica 14'),
         sg.Button('-', key='-ZOOM_OUT-', size=(3, 1), font='Helvetica 12'),
         sg.Text(f'{img_scale:.2f}x', key='-ZOOM_LABEL-', font='Helvetica 12', size=(6, 1), justification='center'),
         sg.Button('+', key='-ZOOM_IN-', size=(3, 1), font='Helvetica 12'),
         sg.Button('Reset', key='-ZOOM_RESET-', size=(6, 1), font='Helvetica 12')],
        [sg.Checkbox('Show All Cells', default=True, key='-TOGGLE_CONTOURS-', enable_events=True, 
                     font='Helvetica 14', tooltip='Toggle visibility of all cell outlines and numbers (selected cells always visible)')],
        [sg.Text("Projection Type:", font='Helvetica 14'),
         sg.Combo(['Max', 'Min', 'Mean', 'Median', 'STD', "Range"], key='-OPTION-', default_value='Max',
                  readonly=True, auto_size_text=True, enable_events=True, font='Helvetica 12')],
        [sg.Text("CMAP:", font='Helvetica 14'), 
         sg.Combo(cmapOptions, key='-CMAP-', default_value='viridis', readonly=True,
                  auto_size_text=True, enable_events=True, font='Helvetica 12')]
    ]
    
    # Middle column: selection list
    middle_column = [
        [sg.Text("Select components to reject:", font='Helvetica 14')],
        [sg.Listbox(values=[i + 1 for i in range(len(estimates.C))], 
                    default_values=initial_listbox_selections_1based, 
                    size=(8, 15), key='-LISTCOMP-', select_mode='multiple', 
                    background_color="white", highlight_background_color="red", enable_events=True, 
                    font='Helvetica 14')],
        [sg.Button('Clear All', key='-CLEAR_SELECTIONS-', size=(10, 1), font='Helvetica 12', 
                   button_color=('white', 'orange'), tooltip='Clear all selected cells')]
    ]
    
    # Right column: time series plot
    right_column = [
        [sg.Text('Time Series', font='Helvetica 16 bold')],
        [sg.Canvas(size=(500, 400), key='-CANVAS-', pad=(5,5))]
    ]
    
    # Build main content layout with three columns side by side
    content_layout = [
        [sg.Column(left_column, vertical_alignment='top'), 
         sg.Column(middle_column, vertical_alignment='top'),
         sg.Column(right_column, vertical_alignment='top')]
    ]
    
    # Add instruction text and buttons at the bottom
    content_layout.append([sg.HorizontalSeparator()])
    content_layout.append([sg.Text('Click Submit to save your selections and continue processing', 
                           font='Helvetica 12 italic', justification='center', pad=(5,10))])
    content_layout.append([sg.Button('Cancel', key="-CANCEL-", size=(15, 1), font='Helvetica 14 bold', 
                             button_color=('white', 'gray'), pad=(10,10)), 
                   sg.Button('Submit & Save', key="-SUBMIT-", size=(15, 1), font='Helvetica 14 bold', 
                             button_color=('white', 'green'), pad=(10,10))])
    
    # Use content_layout directly without wrapping in a scrollable column
    layout = content_layout
    
    window = sg.Window('Cell Component Selector', layout, finalize=True, resizable=True,
                       element_justification='center', font='Helvetica 14')

    graph = window['-GRAPH-']
    scroll_column = window['-SCROLL_COLUMN-']
    
    # Get canvas widget for time series plot
    canvas_elem = window['-CANVAS-'] if '-CANVAS-' in window.key_dict else None
    figure_agg = None
    
    def update_time_series_plot(selected_cells_1based):
        """Update the time series plot with currently selected cells"""
        nonlocal figure_agg
        
        if canvas_elem is None:
            return
            
        # Delete old figure if it exists
        _delete_figure_agg(figure_agg)
        
        # Create new figure
        fig = _create_time_series_plot(
            estimates, 
            eeg_data=eeg_data, 
            eeg_timestamps=eeg_timestamps,
            selected_cells_1based=selected_cells_1based,
            frame_rate=frame_rate
        )
        
        # Draw new figure on canvas
        figure_agg = _draw_figure(canvas_elem.TKCanvas, fig)
    
    def update_scroll_region(scale_factor):
        """Update the scroll region and graph size to match the current image size"""
        try:
            # Calculate the actual image size at current zoom
            img_width = int(movie.shape[2] * scale_factor)
            img_height = int(movie.shape[1] * scale_factor)
            
            # Update the Graph widget's underlying canvas size
            graph_canvas = graph.TKCanvas
            graph_canvas.configure(width=img_width, height=img_height)
            
            # Update the Graph widget's coordinate system to match the new canvas size
            # This ensures a 1:1 mapping between pixels and coordinates
            graph.BottomLeft = (0, img_height)
            graph.TopRight = (img_width, 0)
            
            # Update the scrollable column's canvas scroll region
            scroll_canvas = scroll_column.Widget.canvas
            scroll_canvas.configure(scrollregion=(0, 0, img_width, img_height))
            scroll_canvas.update_idletasks()
        except Exception as e:
            print(f"Failed to update scroll region: {e}")
            pass  # If scroll region update fails, continue anyway
    
    plt.close('all') 
    
    # Initial drawing of the image
    event, values = window.read(timeout=100) 
    _component_image(estimates, projections, movie, graph, max=True, cmap=values['-CMAP-'], scale_factor=window_scale_factor, show_all_contours=show_all_contours)
    update_scroll_region(window_scale_factor)
    
    # Initial drawing of time series plot (with initial selected cells if any)
    if canvas_elem is not None:
        update_time_series_plot(initial_listbox_selections_1based)
    
    while True:
        event, values = window.read() 
        

        if event == '-LISTCOMP-':
            selected_gui_values_to_reject = np.array(values['-LISTCOMP-'], dtype=int)
            estimates.idx_components_bad = sorted(list(selected_gui_values_to_reject - 1)) 
    
            window['-LISTCOMP-'].update(set_to_index=[x for x in estimates.idx_components_bad], 
                                        scroll_to_index=estimates.idx_components_bad[0] if estimates.idx_components_bad else 0)
            
            # Update time series plot with newly selected cells
            if canvas_elem is not None:
                update_time_series_plot(list(selected_gui_values_to_reject))
        
        if event == sg.WINDOW_CLOSED or event == '-CANCEL-':
            break
        
        # Handle clear all selections
        if event == '-CLEAR_SELECTIONS-':
            estimates.idx_components_bad = []
            window['-LISTCOMP-'].update(set_to_index=[])
            # Update time series plot to show no selection
            if canvas_elem is not None:
                update_time_series_plot([])
            print("✓ All cell selections cleared")
        
        # Handle toggle button for showing all contours
        if event == '-TOGGLE_CONTOURS-':
            show_all_contours = values['-TOGGLE_CONTOURS-']

        # Handle zoom controls (1.5x to 3.0x range)
        zoom_changed = False
        if event == '-ZOOM_IN-':
            window_scale_factor = min(window_scale_factor + 0.25, 3.0)  # Max 3.0x zoom
            window['-ZOOM_LABEL-'].update(f'{window_scale_factor:.2f}x')
            zoom_changed = True
            event = '-ZOOM_CHANGED-'  # Trigger redraw
        elif event == '-ZOOM_OUT-':
            window_scale_factor = max(window_scale_factor - 0.25, 1.5)  # Min 1.5x zoom (base size)
            window['-ZOOM_LABEL-'].update(f'{window_scale_factor:.2f}x')
            zoom_changed = True
            event = '-ZOOM_CHANGED-'  # Trigger redraw
        elif event == '-ZOOM_RESET-':
            window_scale_factor = initial_img_scale
            window['-ZOOM_LABEL-'].update(f'{window_scale_factor:.2f}x')
            zoom_changed = True
            event = '-ZOOM_CHANGED-'  # Trigger redraw

        proj_type_flags = {
            'max': False, 'min': False, 'std': False, 
            'mean': False, 'median': False, 'range': False
        }
        
        selected_proj = values['-OPTION-'].lower()
        
        if selected_proj in proj_type_flags:
            proj_type_flags[selected_proj] = True

        # Redraw the component image on any relevant event
        if event in ('-OPTION-', '-CMAP-', '-LISTCOMP-', '-ZOOM_CHANGED-', '-TOGGLE_CONTOURS-', '-CLEAR_SELECTIONS-'):
            _component_image(
                estimates, projections, movie, graph, 
                max=proj_type_flags['max'], min=proj_type_flags['min'], 
                STD=proj_type_flags['std'], mean=proj_type_flags['mean'], 
                median=proj_type_flags['median'], range=proj_type_flags['range'], 
                cmap=values['-CMAP-'],
                scale_factor=window_scale_factor,
                show_all_contours=show_all_contours
            )
            # Update scroll region when zoom changes
            if zoom_changed:
                update_scroll_region(window_scale_factor)

        elif event == '-SUBMIT-':
            print("\n" + "="*60)
            print("SUBMITTING COMPONENT SELECTIONS")
            print("="*60)
            selected_0_based_to_reject = set(estimates.idx_components_bad)
            all_indices_0_based = np.arange(len(estimates.C))
            good_components_indices = [idx for idx in all_indices_0_based if idx not in selected_0_based_to_reject]
            
            print(f"Total components detected: {len(estimates.C)}")
            print(f"Components marked for rejection: {len(selected_0_based_to_reject)}")
            print(f"Components to keep (good cells): {len(good_components_indices)}")
            if len(selected_0_based_to_reject) > 0:
                print(f"Rejected cell IDs (1-based): {sorted([x+1 for x in selected_0_based_to_reject])}")
            
            estimates = estimates.select_components(idx_components=good_components_indices)
            print("✓ Component filtering complete!")
            print("="*60 + "\n")
            break
            
    # Clean up matplotlib figures
    _delete_figure_agg(figure_agg)
    plt.close('all')
    window.close()
    return estimates

        


    
    
    
    
    
    
def crop_gui(coords_dict, projections: Projections, movie_height, movie_width, previous_coords=None) -> dict:
    """
    Creates and handles all events for the pysimplegui cropping application.  Returns a dictionary of coordinates!
    """

    # The whole point of this function is to get the coordinates that will crop the movie

    # define the window layout
    cmapOptions = ['viridis', 'jet', 'plasma', 'inferno', 'magma', 'cividis', 'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
                  'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
                  'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray', 'bone',
                  'pink', 'spring', 'summer', 'autumn', 'winter', 'cool',
                  'Wistia', 'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu', 'RdYlBu',
                  'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent', 'Dark2',
                  'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b',
                  'tab20c']

    boxOptions = ['red/white', 'blue/white', 'red/yellow', 'blue/yellow', 'blue/green',
                  'green/yellow', 'red/green', 'green/white']

    layout = [[sg.Text('Max Projection', key='-TITLE-')],
              [sg.Graph((movie_width, movie_height), (0, 0), (movie_height, movie_width), key='-GRAPH-', drag_submits=True, enable_events=True)],
              [sg.Text("Start: None", key="-START-"), sg.Text("Stop: None", key="-STOP-"),
               sg.Text("Box: None", key="-BOX-")],
              [sg.Text("Projection Type:"), sg.Combo(['Max', 'Min', 'Mean', 'Median', 'STD', "Range"], key='-OPTION-', default_value='Max', readonly=True,
                        auto_size_text=True, enable_events=True)],
              [sg.Text("CMAP:"), sg.Combo(cmapOptions, key='-CMAP-', default_value='viridis', readonly=True,
                        auto_size_text=True, enable_events=True)],
              [sg.Text("Box Colors:"), sg.Combo(boxOptions, key='-COLORBOX-', default_value='red/white', readonly=True,
                                                auto_size_text=True, enable_events=True)],
              [sg.Button('Cancel', key="-CANCEL-"), sg.Button('Submit', key="-SUBMIT-")]]

    # create the form and show it without the plot
    window: sg.Window = sg.Window('CropGUI', layout, finalize=True, resizable=True,
                       element_justification='center', font='Helvetica 18')

    # add the plot to the window
    graph = window['-GRAPH-']
    x0, y0 = None, None
    colors = ['red', 'white']
    index = False
    box = None

    #adds image to window
    _update_image(graph, movie_height, projections.max,)
    if coords_dict is not None:
        try:
            #This code seems like we are changing the coords, but only temporarily so the rectangle is drawn correctly. This function correctly saves crop coords
            box = graph.draw_rectangle((coords_dict['x0'], coords_dict['y0']),
                                   (coords_dict['x1'], coords_dict['y1']),
                                   line_color=colors[index])
        except:
            print("Failed to draw intial box on GUI with the given coords")
    else:
        if coords_dict is None or not coords_dict:
            coords_dict = {
                'x0': 0,
                'y0': 0,
                'x1': movie_width,
                'y1': movie_height
            }

    while True:
        #controls events to update window
        event, values = window.read(timeout=100)

        if event == sg.WINDOW_CLOSED or event in '-CANCEL-':
            # Make sure that nothing gets cropped
            coords_dict['x0'] = 0
            coords_dict['y0'] = 0
            coords_dict['x1'] = 0
            coords_dict['y1'] = 0
            break

        #color of box options
        elif event in '-COLORBOX-':
            if values['-COLORBOX-'] == 'red/white':
                colors = ['red', 'white']
            elif values['-COLORBOX-'] == 'blue/white':
                colors = ['blue', 'white']
            elif values['-COLORBOX-'] == 'red/yellow':
                colors = ['red', 'yellow']
            elif values['-COLORBOX-'] == 'blue/yellow':
                colors = ['blue', 'yellow']
            elif values['-COLORBOX-'] == 'blue/green':
                colors = ['blue', 'green']
            elif values['-COLORBOX-'] == 'green/yellow':
                colors = ['green', 'yellow']
            elif values['-COLORBOX-'] == 'red/green':
                colors = ['red', 'green']
            elif values['-COLORBOX-'] == 'green/white':
                colors = ['green', 'white']
            # Redraw crop rectangle
            if box:
                graph.delete_figure(box)
            index = not index
            box = graph.draw_rectangle((coords_dict['x0'], coords_dict['y0']),
                                       (coords_dict['x1'], coords_dict['y1']),
                                       line_color=colors[index])

        #Type of image options
        elif event in '-OPTION-' or event in '-CMAP-':
            if event in '-OPTION-':
                window['-TITLE-'].update(values['-OPTION-'] + " Projection")

            if values['-OPTION-'] == 'Max':
                _update_image(graph, movie_height, projections.max, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Min':
                _update_image(graph, movie_height, projections.min, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'STD':
                _update_image(graph, movie_height, projections.std, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Mean':
                _update_image(graph, movie_height, projections.mean, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Median':
                _update_image(graph, movie_height, projections.median, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Range':
                _update_image(graph, movie_height, projections.range, cmap=values['-CMAP-'])

            # Redraw crop rectangle
            if box:
                graph.delete_figure(box)
            index = not index
            box = graph.draw_rectangle((coords_dict['x0'], coords_dict['y0']),
                                       (coords_dict['x1'], coords_dict['y1']),
                                       line_color=colors[index])

        elif event in '-SUBMIT-':
            break

        #drawing the box and getting x/y values
        elif event in '-GRAPH-':
            if (x0, y0) == (None, None):
                x0, y0 = values['-GRAPH-']
                if values['-GRAPH-'][0] < 0:
                    x0 = 0
                if values['-GRAPH-'][0] > movie_width:
                    x0 = movie_width
                if values['-GRAPH-'][1] < 0:
                    y0 = 0
                if values['-GRAPH-'][1] > movie_height:
                    y0 = movie_height
            x1, y1 = values['-GRAPH-']
            if values['-GRAPH-'][0] < 0:
                x1 = 0
            if values['-GRAPH-'][0] > movie_width:
                x1 = movie_width
            if values['-GRAPH-'][1] < 0:
                y1 = 0
            if values['-GRAPH-'][1] > movie_height:
                y1 = movie_height
            coords_dict = _update_coords(window, x0, y0, x1, y1, coords_dict)
            if box:
                graph.delete_figure(box)
            if None not in (x0, y0, x1, y1):
                box = graph.draw_rectangle((x0, y0), (x1, y1), line_color=colors[index])
                index = not index
        elif event.endswith('+UP'):
             x0, y0 = None, None
    
    plt.close()
    window.close()

    return coords_dict


def _update_image(graph, movie_height, projection, cmap='viridis'):
    """
    Redraws the desired projection(image) to the pysimplegui graph object
    """
    # adds projection to GUI
    pic_IObytes = io.BytesIO()
    plt.imsave(pic_IObytes, projection, format='png', cmap=cmap)
    plt.close()
    pic_IObytes.seek(0)
    pic_hash = base64.b64encode(pic_IObytes.read())

    # Draw image in graph
    graph.draw_image(data=pic_hash, location=(0, movie_height))


def _update_coords(window, x0, y0, x1, y1, coords_dict) -> dict:
    """
    Update cropping rectangle information
    """

    if x0 is not None:
        coords_dict['x0'] = x0
    if y0 is not None:
        coords_dict['y0'] = y0
    if x1 is not None:
        coords_dict['x1'] = x1
    if y1 is not None:
        coords_dict['y1'] = y1
    window['-START-'].update(f'Start: ({x0}, {y0})')
    window['-STOP-'].update(f'Stop: ({x1}, {y1})')
    window['-BOX-'].update(f'Box: ({abs(x1 - x0 + 1)}, {abs(y1 - y0 + 1)})')

    return coords_dict
    
    
    
    

        
        