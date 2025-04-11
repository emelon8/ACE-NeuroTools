import base64
import io
import caiman as cm
import numpy as np
from src2.miniscope.projections import Projections
import numpy as np
import matplotlib.pyplot as plt
import logging
from scipy.signal import detrend
from caiman import movie as cm_movie
from src2.shared.misc_functions import updateCSVCell, denoiseMovie, _prepAxes
import PySimpleGUI as sg
import numpy as np
from tqdm import tqdm


class MiniscopePreprocessor():

    def __init__(self, movie:cm.movie):
        self.movie = movie

    # def computeProjections(self, movie: cm.movie):
    #     """Calculates the projections of self.movie and returns."""
        
    #     max = np.amax(movie, axis=0)
    #     std = np.std(movie, axis=0)
    #     min = np.amin(movie, axis=0)
    #     mean = np.mean(movie, axis=0)
    #     median = np.median(movie, axis=0)
    #     range = max - min
    #     time = movie.mean(axis=(1,2))

    #     return Projections(max, std, min, mean, median, range, time)



    def computeProjections(self, movie: cm.movie=None):
        if movie is None:
            movie = self.movie
        """Calculates the projections of self.movie with progress bar."""
        print("\n\nComputing projections...\n")
        
        operations = {
            'max': lambda m: np.amax(m, axis=0),
            'std': lambda m: np.std(m, axis=0),
            'min': lambda m: np.amin(m, axis=0),
            'mean': lambda m: np.mean(m, axis=0),
            'median': lambda m: np.median(m, axis=0),
            'time': lambda m: m.mean(axis=(1,2)),
        }

        results = {}
        for name, op in tqdm(operations.items(), desc='Computing Projections'):
            results[name] = op(movie)

        results['range'] = results['max'] - results['min']

        return Projections(
            results['max'],
            results['std'],
            results['min'],
            results['mean'],
            results['median'],
            results['range'],
            results['time']
        )

    

    def preprocess_movie(self, coords_dict, crop=False, square=False, coords=None,
                         crop_gui=False, denoise=False, detrend=False,
                         df_over_f=False):
        """Run preprocessing steps based on provided flags."""
        movie = self.movie
        steps_applied = []

        if crop:
            col = 'crop_square' if square else 'crop'                           # TODO I eliminated this option deeper down, do I have to add it back?
            projections = self.computeProjections(movie)
            movie, coords = self.crop_movie(coords_dict, projections, movie.shape[1], movie.shape[2], gui=crop_gui, coords=coords)
            steps_applied.append('_croppedSquare' if square else '_cropped')

        if denoise:
            movie = self.denoise_movie(movie)
            steps_applied.append('_denoised')

        if detrend:
            movie = self.detrend_movie(movie)
            steps_applied.append('_detrended')

        if df_over_f:
            movie = self.compute_df_over_f(movie)
            steps_applied.append('_dFoverF')

        processing_step = ''.join(steps_applied)

        return movie, processing_step, coords
    

    def crop_movie(self, coords_dict, projections, movie_height, movie_width, gui=False, coords=None):
        if gui or coords is None:
            coords = self._crop_window(coords_dict, projections, movie_height, movie_width)

        x0, x1 = sorted([coords['x0'], coords['x1']])
        y0, y1 = sorted([coords['y0'], coords['y1']])

        cropped_movie = self.movie[:, y0:y1, x0:x1]
        coords = f'({x0},{y0},{x1},{y1})'

        return cropped_movie, coords

    def denoise_movie(self, movie):
        """Denoise the calcium imaging movie."""
        denoised_movie = denoiseMovie(movie)
        return denoised_movie

    def detrend_movie(self, movie, method='median', plot_trend=False):
        if plot_trend:
            fig, ax = _prepAxes(xLabel='Frames', yLabel='Mean Fluorescence')
            ax.plot(np.mean(movie, axis=(1, 2)), label='Original Data')

        if method == 'linear':
            detrended_movie = detrend(movie, axis=0)
        elif method == 'median':
            detrended_movie = movie.debleach()
        else:
            raise ValueError(f"Unsupported detrending method '{method}'.")

        if plot_trend:
            ax.plot(np.mean(detrended_movie, axis=(1, 2)), label='Detrended Data')
            ax.legend()
            plt.show()

        return detrended_movie

    def compute_df_over_f(self, movie, secs_window=5, quantile_min=8,
                          method='delta_f_over_sqrt_f'):
        movie_positive = movie + 1  # Avoid zero values
        processed_movie, _ = cm_movie.computeDFF(movie_positive,
                                                 secs_window,
                                                 quantile_min,
                                                 method)
        return processed_movie

    def denoise_movie(self, movie):
        # Implement actual denoising logic here
        denoised_movie = denoiseMovie(movie)
        return denoised_movie























    def _crop_window(self, coords_dict, projections: Projections, movie_height, movie_width) -> dict:
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
        self._updateImage(graph, movie_height, projections.max,)
        box = graph.draw_rectangle((coords_dict['x0'], coords_dict['y0']),
                                   (coords_dict['x1'], coords_dict['y1']),
                                   line_color=colors[index])

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
                    self._updateImage(graph, movie_height, projections.max, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Min':
                    self._updateImage(graph, movie_height, projections.min, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'STD':
                    self._updateImage(graph, movie_height, projections.std, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Mean':
                    self._updateImage(graph, movie_height, projections.mean, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Median':
                    self._updateImage(graph, movie_height, projections.median, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Range':
                    self._updateImage(graph, movie_height, projections.range, cmap=values['-CMAP-'])

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
                coords_dict = self._updateCoords(window, x0, y0, x1, y1, coords_dict)
                if box:
                    graph.delete_figure(box)
                if None not in (x0, y0, x1, y1):
                    box = graph.draw_rectangle((x0, y0), (x1, y1), line_color=colors[index])
                    index = not index
            elif event.endswith('+UP'):
                 x0, y0 = None, None

        window.close()

        return coords_dict


    def _updateImage(self, graph, movie_height, projection, cmap='viridis'):
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


    def _updateCoords(self, window, x0, y0, x1, y1, coords_dict) -> dict:
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