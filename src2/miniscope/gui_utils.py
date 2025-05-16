import numpy as np
import PySimpleGUI as sg
import matplotlib.pyplot as plt
import caiman as cm
import io
import base64
import io
import sys
import base64
from src2.miniscope.projections import Projections


def component_gui(movie, estimates, projections):
    if estimates.idx_components_bad is None:
        estimates.idx_components = list(range(len(estimates.C)))
        estimates.idx_components_bad = []
    
    # define the window layout
    cmapOptions = ['viridis', 'jet', 'plasma', 'inferno', 'magma', 'cividis', 'Greys', 'Purples', 'Blues', 'Greens',
                   'Oranges', 'Reds',
                   'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
                   'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray',
                   'bone',
                   'pink', 'spring', 'summer', 'autumn', 'winter', 'cool',
                   'Wistia', 'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
                   'RdYlBu',
                   'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent',
                   'Dark2',
                   'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b',
                   'tab20c']

    layout = [[sg.Text('Components', key='-TITLE-')],
              [sg.Graph((movie.shape[2], movie.shape[1]), (0, 0), (movie.shape[1], movie.shape[2]), key='-GRAPH-', 
                        enable_events=True)],
              [sg.Text("Projection Type:"),
               sg.Combo(['Max', 'Min', 'Mean', 'Median', 'STD', "Range"], key='-OPTION-', default_value='Max',
                        readonly=True,
                        auto_size_text=True, enable_events=True)],
              [sg.Text("CMAP:"), sg.Combo(cmapOptions, key='-CMAP-', default_value='viridis', readonly=True,
                                          auto_size_text=True, enable_events=True)],
              [sg.Text("Select to reject: ")],
              [sg.Listbox(values=range(1, len(estimates.C)+1), default_values=estimates.idx_components_bad, size=(3, 3), key='-LISTCOMP-', select_mode='multiple', background_color="white", highlight_background_color="red", enable_events = True)],
              [sg.Button('Cancel', key="-CANCEL-"), sg.Button('Submit', key="-SUBMIT-")]]
    # create the form and show it without the plot
    window = sg.Window('Components', layout, finalize=True, resizable=True,
                       element_justification='center', font='Helvetica 18')

    # adds image to window
    graph = window['-GRAPH-']
    _component_image(estimates, projections, movie, graph, estimates.idx_components_bad, max=True)
    
    # calls view_components to view temporal data
    plt.figure(2)
    estimates.view_components(img = projections.range)
    plt.close(2)
    
    while True:
        # controls events to update window
        event, values = window.read(timeout=100)

        
        if event == sg.WINDOW_CLOSED or event in '-CANCEL-':
            break

        # Type of image options
        elif event in '-OPTION-':
            if values['-OPTION-'] == 'Max':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], max=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Min':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], min=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'STD':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], STD=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Mean':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], mean=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Median':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], median=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Range':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], range=True, cmap=values['-CMAP-'])

        # CMAP of image
        elif event in '-CMAP-':
            if values['-OPTION-'] == 'Max':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], max=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Min':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], min=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'STD':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], STD=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Mean':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], mean=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Median':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], median=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Range':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], range=True, cmap=values['-CMAP-'])

        #Update colors of selected components
        elif event in '-LISTCOMP-':
            if values['-OPTION-'] == 'Max':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], max=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Min':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], min=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'STD':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], STD=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Mean':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], mean=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Median':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], median=True, cmap=values['-CMAP-'])
            elif values['-OPTION-'] == 'Range':
                _component_image(estimates, projections, movie, graph, values['-LISTCOMP-'], range=True, cmap=values['-CMAP-'])

        elif event in '-SUBMIT-':
            selected = np.arange(0, len(estimates.C))
            selected = [idx for idx in selected if idx not in (np.array(values['-LISTCOMP-'], dtype=int) - np.ones(len(values['-LISTCOMP-']), dtype=int))]
            estimates = estimates.select_components(idx_components=selected)
            break
    
    plt.close()
    window.close()
    return estimates


def _create_contour_fig(sfootprints, background, current_selected, thr=None, thr_method='max', maxthr=0.2, nrgthr=0.9, display_numbers=True, max_number=None,
                  cmap=None, unselectcolor='w', selectcolor='r', coordinates=None,
                  contour_args={}, number_args={}):
    """Plots contour of spatial components against a background image

     Args:
         A:   np.ndarray or sparse matrix
                   Matrix of Spatial components (d x K)
    
         Cn:  np.ndarray (2D)
                   Background image (e.g. mean, correlation)
    
         thr_method: [optional] string
                  Method of thresholding:
                      'max' sets to zero pixels that have value less than a fraction of the max value
                      'nrg' keeps the pixels that contribute up to a specified fraction of the energy
    
         maxthr: [optional] scalar
                    Threshold of max value
    
         nrgthr: [optional] scalar
                    Threshold of energy
    
         thr: scalar between 0 and 1
                   Energy threshold for computing contours (default 0.9)
                   Kept for backwards compatibility. If not None then thr_method = 'nrg', and nrgthr = thr
    
         display_number:     Boolean
                   Display number of ROIs if checked (default True)
    
         max_number:    int
                   Display the number for only the first max_number components (default None, display all numbers)
    
         cmap:     string
                   User specifies the colormap (default None, default colormap)
    """

    if thr is None:
        try:
            thr = {'nrg': nrgthr, 'max': maxthr}[thr_method]
        except KeyError:
            thr = maxthr
    else:
        thr_method = 'nrg'
    plt.figure(1)
    ax = plt.gca()
    fig = plt.imshow(background, interpolation=None, cmap=cmap)
    if coordinates is None:
        coordinates = cm.utils.visualization.get_contours(sfootprints, np.shape(background), thr, thr_method, swap_dim=False)
    for c in coordinates:
        v = c['coordinates']
        c['bbox'] = [np.floor(np.nanmin(v[:, 1])), np.ceil(np.nanmax(v[:, 1])),
                     np.floor(np.nanmin(v[:, 0])), np.ceil(np.nanmax(v[:, 0]))]
        if c['neuron_id'] in current_selected:
            plt.plot(*v.T, c=selectcolor, **contour_args)
        else:
            plt.plot(*v.T, c=unselectcolor, **contour_args)
    if display_numbers:
        d1, d2 = np.shape(background)
        d, nr = np.shape(sfootprints)
        comp = cm.base.rois.com(sfootprints, d1, d2)
        if max_number is None:
            max_number = sfootprints.shape[1]
        for i in range(np.minimum(nr, max_number)):
            ax.text(comp[i, 1], comp[i, 0], str(i + 1), color=unselectcolor, **number_args)
    plt.axis('off')
    return fig


def _component_image(estimates, projections, movie, graph, current_selected,  max=False, min=False, STD=False, mean=False, median=False, range=False,
                 cmap='viridis'):
    """Adds projection to GUI."""
    pic_IObytes = io.BytesIO()
    if max:
        _create_contour_fig(estimates.A, projections.max, current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
    elif min:
        _create_contour_fig(estimates.A, projections.min, current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
    elif STD:
        _create_contour_fig(estimates.A, projections.std, current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
    elif mean:
        _create_contour_fig(estimates.A, projections.mean, current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
    elif median:
        _create_contour_fig(estimates.A, projections.median, current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
    elif range:
        _create_contour_fig(estimates.A, projections.range, current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
    plt.close()
    pic_IObytes.seek(0)
    pic_hash = base64.b64encode(pic_IObytes.read())
    # Draw image in graph
    graph.draw_image(data=pic_hash, location=(0, movie.shape[1]))
    
    
    
    
    
    
def crop_gui(coords_dict, projections: Projections, movie_height, movie_width) -> dict:
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
    if coords_dict:
        box = graph.draw_rectangle((coords_dict['x0'], coords_dict['y0']),
                               (coords_dict['x1'], coords_dict['y1']),
                               line_color=colors[index])
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
    
    
    

        
        