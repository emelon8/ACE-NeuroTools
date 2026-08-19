import base64
import io
import json
import os
from datetime import datetime

import caiman as cm
import FreeSimpleGUI as sg
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image

from aceneurotools.miniscope.projections import Projections


def ensure_tk_alive() -> None:
    """Keep a hidden Tk root so a later FreeSimpleGUI window can open.

    Closing CropGUI (or destroying matplotlib's Tk windows) can kill Tk's
    default root. Creating a new ``sg.Window`` after that often SIGSEGVs.
    A withdrawn root keeps the Tcl interpreter alive between GUI stages.
    """
    import tkinter as tk

    root = getattr(tk, '_default_root', None)
    if root is not None:
        try:
            if root.winfo_exists():
                return
        except tk.TclError:
            pass
    root = tk.Tk()
    root.withdraw()



def _draw_figure(canvas, figure):
    """Draw a matplotlib figure onto a FreeSimpleGUI Canvas widget.

    Args:
        canvas: The Tk canvas widget from a FreeSimpleGUI Canvas element.
        figure: The matplotlib Figure to render.

    Returns:
        The FigureCanvasTkAgg wrapper, retained so it can be removed later.
    """
    figure_canvas_agg = FigureCanvasTkAgg(figure, canvas)
    figure_canvas_agg.draw()
    figure_canvas_agg.get_tk_widget().pack(side='top', fill='both', expand=1)
    return figure_canvas_agg


def _delete_figure_agg(figure_agg):
    """Remove a previously drawn figure from its canvas and close it.

    Args:
        figure_agg: The FigureCanvasTkAgg returned by :func:`_draw_figure`,
            or ``None`` if nothing has been drawn yet.
    """
    if figure_agg:
        figure_agg.get_tk_widget().forget()
        plt.close('all')


def _save_rejection_log(total_components, good_indices, rejected_indices, save_dir=None):
    """Write a JSON log recording which components were kept vs rejected.

    Provides a reproducible record of the GUI curation step so an analysis
    can be rerun and audited later.

    Args:
        total_components: Total number of components detected by CNMF-E.
        good_indices: Iterable of 0-based indices that were kept.
        rejected_indices: Iterable of 0-based indices that were rejected.
        save_dir: Directory to write ``rejection_log.json`` into. If ``None``,
            the log is printed to the console instead.
    """
    # Coerce to plain Python ints; indices often arrive as numpy int64,
    # which json.dump cannot serialize.
    good_indices = [int(x) for x in good_indices]
    rejected_indices = [int(x) for x in rejected_indices]
    rejection_log = {
        "pipeline_info": {
            "datetime": datetime.now().isoformat(),
        },
        "summary": {
            "total_components_detected": int(total_components),
            "components_kept": len(good_indices),
            "components_rejected": len(rejected_indices)
        },
        "kept_indices_0based": sorted(good_indices),
        "kept_indices_1based": sorted([x + 1 for x in good_indices]),
        "rejected_components": [
            {
                "index_0based": idx,
                "index_1based": idx + 1,
                "reason": ""
            }
            for idx in sorted(rejected_indices)
        ]
    }

    if save_dir is not None:
        os.makedirs(save_dir, exist_ok=True)
        log_path = os.path.join(save_dir, 'rejection_log.json')
        with open(log_path, 'w') as f:
            json.dump(rejection_log, f, indent=4)
        print(f"Saved rejection log to: {log_path}")
    else:
        print("No save_dir provided, printing rejection log to console:")
        print(json.dumps(rejection_log, indent=4))


def _create_time_series_plot(estimates, eeg_data=None, eeg_timestamps=None, selected_cells_1based=None, frame_rate=30):
    """Build a matplotlib figure of calcium traces (and optional EEG) for selected cells.

    Args:
        estimates: CNMF-E estimates object holding calcium traces in ``estimates.C``.
        eeg_data: Optional 1D EEG/ephys signal synchronized with the calcium frames.
        eeg_timestamps: Optional timestamps (seconds) for ``eeg_data``. If omitted,
            the EEG is assumed to be frame-synchronized with the calcium data.
        selected_cells_1based: List of 1-based cell indices to plot. If empty or
            ``None``, an instructional placeholder is shown instead.
        frame_rate: Calcium imaging frame rate in Hz, used to build the time axis.

    Returns:
        A matplotlib Figure ready to be drawn on a canvas.
    """
    fig = matplotlib.figure.Figure(figsize=(5, 4), dpi=100)

    if selected_cells_1based is None or len(selected_cells_1based) == 0:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, 'Select a cell to view its time series',
                ha='center', va='center', fontsize=14, transform=ax.transAxes)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')
        return fig

    num_plots = 2 if eeg_data is not None else 1

    num_frames = estimates.C.shape[1]
    time_calcium = np.arange(num_frames) / frame_rate

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
    if len(selected_cells_1based) <= 10:
        ax1.legend(fontsize=8, loc='upper right')
    ax1.tick_params(labelsize=9)

    if eeg_data is not None and num_plots == 2:
        ax2 = fig.add_subplot(num_plots, 1, 2)
        if eeg_timestamps is not None:
            time_eeg = eeg_timestamps
        elif len(eeg_data) == num_frames:
            time_eeg = time_calcium
        else:
            time_eeg = np.arange(len(eeg_data)) / frame_rate

        ax2.plot(time_eeg, eeg_data, color='darkblue', linewidth=1, alpha=0.8)
        ax2.set_xlabel('Time (s)', fontsize=10, labelpad=8)
        ax2.set_ylabel('EEG Signal (uV)', fontsize=10, labelpad=8)
        ax2.set_title('EEG Time Series', fontsize=12, fontweight='bold', pad=10)
        ax2.grid(True, alpha=0.3)
        ax2.tick_params(labelsize=9)

    fig.tight_layout(pad=2.0, h_pad=3.0, w_pad=2.0)
    return fig


def _create_contour_fig(sfootprints, background, estimates_obj, thr=None, thr_method='max', maxthr=0.2, nrgthr=0.9, display_numbers=True, max_number=None,
                         cmap=None, unselectcolor='w', selectcolor='r', coordinates=None,
                         contour_args={}, number_args={}, show_all_contours=True):
    """Create a figure showing component contours overlaid on a background image.

    Generates a matplotlib figure with detected neuron contours, coloring
    rejected components differently from accepted ones.

    Args:
        sfootprints: Spatial footprints matrix (A) from CNMF-E.
        background: 2D array for background image.
        estimates_obj: CNMF-E estimates with idx_components_bad.
        thr: Threshold for contour detection.
        thr_method: 'max' or 'nrg' thresholding method.
        maxthr: Maximum threshold value for 'max' method.
        nrgthr: Energy threshold for 'nrg' method.
        display_numbers: If True, show component numbers.
        max_number: Maximum number of components to display.
        cmap: Colormap for background image.
        unselectcolor: Color for accepted components.
        selectcolor: Color for rejected components.
        coordinates: Pre-computed contour coordinates (optional).
        contour_args: Additional kwargs for contour plotting.
        number_args: Additional kwargs for text labels.
        show_all_contours: If True, draw contours/numbers for accepted
            components too. If False, only rejected components are shown
            (rejected components are always visible).

    Returns:
        Matplotlib Figure object.
    """

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
    ax = fig.add_axes((0, 0, 1, 1)) # [left, bottom, width, height] in figure coordinates (0 to 1)

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

        # Rejected components are always shown in red; accepted components
        # are only drawn when the show-all toggle is enabled.
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
            if is_bad:
                ax.text(comp[i, 1], comp[i, 0], str(i + 1), color=selectcolor, **number_args)
            elif show_all_contours:
                ax.text(comp[i, 1], comp[i, 0], str(i + 1), color=unselectcolor, **number_args)

    return fig


def _component_image(estimates, projections, movie, graph, max=False, min=False, STD=False, mean=False, median=False, range=False, cmap='viridis', scale_factor=1.0, show_all_contours=True):
    """Render component contours on a projection and display in GUI graph.

    Args:
        estimates: CNMF-E estimates object.
        projections: Projections object with summary images.
        movie: CaImAn movie (for dimensions).
        graph: FreeSimpleGUI Graph element to draw on.
        max/min/STD/mean/median/range: Booleans selecting projection type.
        cmap: Colormap name for background.
        scale_factor: Factor to scale the rendered image by (for zoom).
        show_all_contours: If True, draw accepted-component contours too.
    """
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

        # Scale the image if a non-unity zoom factor is requested.
        if scale_factor != 1.0:
            img = Image.open(io.BytesIO(pic_data))
            new_width = int(img.width * scale_factor)
            new_height = int(img.height * scale_factor)
            img_resized = img.resize((new_width, new_height), Image.LANCZOS)

            pic_IObytes_resized = io.BytesIO()
            img_resized.save(pic_IObytes_resized, format='PNG')
            pic_IObytes_resized.seek(0)
            pic_data = pic_IObytes_resized.read()

        pic_hash = base64.b64encode(pic_data)

        graph.draw_image(data=pic_hash, location=(0, 0))

    else:
        print("No background to display")


def component_gui(movie, estimates, projections, eeg_data=None, eeg_timestamps=None, frame_rate: float = 30, save_dir: str | None = None):
    """Interactive GUI for selecting which CNMF-E components to reject.

    Displays component contours overlaid on projection images in a scrollable,
    zoomable viewer. As cells are selected, their calcium traces (and optional
    EEG signal) are plotted in real time. On submit, a JSON rejection log is
    written for reproducibility before rejected components are removed.

    Args:
        movie: CaImAn movie for dimensions.
        estimates: CNMF-E estimates object (modified in-place).
        projections: Projections object for background images.
        eeg_data: Optional 1D EEG/ephys signal synchronized with the calcium
            frames. When provided, it is plotted beneath the calcium traces.
        eeg_timestamps: Optional timestamps (seconds) for ``eeg_data``. If
            omitted, the EEG is assumed frame-synchronized with the calcium data.
        frame_rate: Calcium imaging frame rate in Hz, used for the trace axis.
        save_dir: Directory to write ``rejection_log.json`` into on submit. If
            ``None``, the log is printed to the console instead.

    Returns:
        Updated estimates object with rejected components removed.
    """
    ensure_tk_alive()
    if estimates.idx_components_bad is None:
        estimates.idx_components_bad = []

    print(f'This is the movie shape after processing: {movie.shape}')
    print(f'Initial estimates.idx_components_bad: {estimates.idx_components_bad}')
    if eeg_data is not None:
        print(f'EEG data shape: {eeg_data.shape}')
        print('EEG time series visualization enabled')

    cmapOptions = ['viridis', 'jet', 'plasma', 'inferno', 'magma', 'cividis', 'Greys', 'Purples', 'Blues', 'Greens',
                   'Oranges', 'Reds', 'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu','GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray','bone','pink', 'spring', 'summer', 'autumn', 'winter', 'cool','Wistia', 'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu','RdYlBu','RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent','Dark2','Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b','tab20c']

    initial_listbox_selections_1based = [idx + 1 for idx in estimates.idx_components_bad]

    # Toggle state for showing all cell contours and numbers.
    show_all_contours = True

    # Image display scale (zoom). 1.25x by default.
    img_scale = 1.25
    initial_img_scale = img_scale
    window_scale_factor = img_scale

    # Viewport size (fixed window showing part of the scaled canvas).
    viewport_width = min(int(movie.shape[2] * 1.25) + 20, 550)
    viewport_height = min(int(movie.shape[1] * 1.25) + 20, 400)

    # Canvas is sized for the initial zoom level; resized dynamically on zoom.
    canvas_width = int(movie.shape[2] * img_scale)
    canvas_height = int(movie.shape[1] * img_scale)
    coord_width = int(movie.shape[2] * img_scale)
    coord_height = int(movie.shape[1] * img_scale)

    # Left column: scrollable/zoomable image and controls.
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

    # Middle column: selection list.
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

    # Right column: time series plot.
    right_column = [
        [sg.Text('Time Series', font='Helvetica 16 bold')],
        [sg.Canvas(size=(500, 400), key='-CANVAS-', pad=(5, 5))]
    ]

    # Three columns side by side, with instructions and buttons below.
    content_layout = [
        [sg.Column(left_column, vertical_alignment='top'),
         sg.Column(middle_column, vertical_alignment='top'),
         sg.Column(right_column, vertical_alignment='top')]
    ]
    content_layout.append([sg.HorizontalSeparator()])
    content_layout.append([sg.Text('Click Submit to save your selections and continue processing',
                           font='Helvetica 12 italic', justification='center', pad=(5, 10))])
    content_layout.append([sg.Button('Cancel', key="-CANCEL-", size=(15, 1), font='Helvetica 14 bold',
                             button_color=('white', 'gray'), pad=(10, 10)),
                   sg.Button('Submit & Save', key="-SUBMIT-", size=(15, 1), font='Helvetica 14 bold',
                             button_color=('white', 'green'), pad=(10, 10))])

    layout = content_layout

    window = sg.Window('Cell Component Selector', layout, finalize=True, resizable=True,
                       element_justification='center', font='Helvetica 14')

    graph = window['-GRAPH-']
    scroll_column = window['-SCROLL_COLUMN-']
    canvas_elem = window['-CANVAS-'] if '-CANVAS-' in window.key_dict else None
    figure_agg = None

    def update_time_series_plot(selected_cells_1based):
        """Redraw the calcium/EEG time series plot for the given selection."""
        nonlocal figure_agg
        if canvas_elem is None:
            return
        _delete_figure_agg(figure_agg)
        fig = _create_time_series_plot(
            estimates,
            eeg_data=eeg_data,
            eeg_timestamps=eeg_timestamps,
            selected_cells_1based=selected_cells_1based,
            frame_rate=frame_rate
        )
        figure_agg = _draw_figure(canvas_elem.TKCanvas, fig)

    def update_scroll_region(scale_factor):
        """Resize the graph canvas and scroll region to match the current zoom."""
        try:
            img_width = int(movie.shape[2] * scale_factor)
            img_height = int(movie.shape[1] * scale_factor)

            graph_canvas = graph.TKCanvas
            graph_canvas.configure(width=img_width, height=img_height)

            # Keep a 1:1 mapping between graph coordinates and pixels.
            graph.BottomLeft = (0, img_height)
            graph.TopRight = (img_width, 0)

            scroll_canvas = scroll_column.Widget.canvas
            scroll_canvas.configure(scrollregion=(0, 0, img_width, img_height))
            scroll_canvas.update_idletasks()
        except Exception as e:
            print(f"Failed to update scroll region: {e}")

    plt.close('all')

    # Initial drawing of the image and the (possibly empty) time series plot.
    event, values = window.read(timeout=100)
    _component_image(estimates, projections, movie, graph, max=True, cmap=values['-CMAP-'],
                     scale_factor=window_scale_factor, show_all_contours=show_all_contours)
    update_scroll_region(window_scale_factor)
    if canvas_elem is not None:
        update_time_series_plot(initial_listbox_selections_1based)

    while True:
        event, values = window.read()

        if event == '-LISTCOMP-':
            selected_gui_values_to_reject = np.array(values['-LISTCOMP-'], dtype=int)
            estimates.idx_components_bad = sorted(list(selected_gui_values_to_reject - 1))

            window['-LISTCOMP-'].update(set_to_index=[x for x in estimates.idx_components_bad],
                                        scroll_to_index=estimates.idx_components_bad[0] if estimates.idx_components_bad else 0)

            if canvas_elem is not None:
                update_time_series_plot(list(selected_gui_values_to_reject))

        if event == sg.WINDOW_CLOSED or event == '-CANCEL-':
            break

        # Clear all selections.
        if event == '-CLEAR_SELECTIONS-':
            estimates.idx_components_bad = []
            window['-LISTCOMP-'].update(set_to_index=[])
            if canvas_elem is not None:
                update_time_series_plot([])
            print("All cell selections cleared")

        # Toggle contour visibility.
        if event == '-TOGGLE_CONTOURS-':
            show_all_contours = values['-TOGGLE_CONTOURS-']

        # Zoom controls (1.0x to 3.0x range).
        zoom_changed = False
        if event == '-ZOOM_IN-':
            window_scale_factor = min(window_scale_factor + 0.25, 3.0)
            window['-ZOOM_LABEL-'].update(f'{window_scale_factor:.2f}x')
            zoom_changed = True
            event = '-ZOOM_CHANGED-'
        elif event == '-ZOOM_OUT-':
            window_scale_factor = max(window_scale_factor - 0.25, 1.0)
            window['-ZOOM_LABEL-'].update(f'{window_scale_factor:.2f}x')
            zoom_changed = True
            event = '-ZOOM_CHANGED-'
        elif event == '-ZOOM_RESET-':
            window_scale_factor = initial_img_scale
            window['-ZOOM_LABEL-'].update(f'{window_scale_factor:.2f}x')
            zoom_changed = True
            event = '-ZOOM_CHANGED-'

        proj_type_flags = {
            'max': False, 'min': False, 'std': False,
            'mean': False, 'median': False, 'range': False
        }

        selected_proj = values['-OPTION-'].lower()

        if selected_proj in proj_type_flags:
            proj_type_flags[selected_proj] = True

        # Redraw the component image on any relevant event.
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
            if zoom_changed:
                update_scroll_region(window_scale_factor)

        elif event == '-SUBMIT-':
            print("\n" + "=" * 60)
            print("SUBMITTING COMPONENT SELECTIONS")
            print("=" * 60)
            selected_0_based_to_reject = set(estimates.idx_components_bad)
            all_indices_0_based = np.arange(len(estimates.C))
            good_components_indices = [idx for idx in all_indices_0_based if idx not in selected_0_based_to_reject]

            print(f"Total components detected: {len(estimates.C)}")
            print(f"Components marked for rejection: {len(selected_0_based_to_reject)}")
            print(f"Components to keep (good cells): {len(good_components_indices)}")
            if len(selected_0_based_to_reject) > 0:
                print(f"Rejected cell IDs (1-based): {sorted([x + 1 for x in selected_0_based_to_reject])}")

            _save_rejection_log(
                total_components=len(estimates.C),
                good_indices=good_components_indices,
                rejected_indices=selected_0_based_to_reject,
                save_dir=save_dir
            )

            # select_components operates in-place in some versions and returns None, or returns self in others.
            # We handle both by checking the return value.
            ret = estimates.select_components(idx_components=good_components_indices)
            if ret is not None:
                estimates = ret
            print("Component filtering complete!")
            print("=" * 60 + "\n")
            break

    _delete_figure_agg(figure_agg)
    plt.close('all')
    window.close()
    return estimates


def crop_gui(coords_dict, projections: Projections, movie_height, movie_width, previous_coords=None) -> dict:
    """
    Creates and handles all events for the freesimplegui cropping application.  Returns a dictionary of coordinates!
    """
    ensure_tk_alive()

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
        except Exception as e:
            print(f"Failed to draw intial box on GUI with the given coords: {e}")
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

    plt.close('all')
    window.close()
    ensure_tk_alive()

    return coords_dict


def _update_image(graph, movie_height, projection, cmap='viridis'):
    """
    Redraws the desired projection(image) to the freesimplegui graph object
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
