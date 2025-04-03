import caiman as cm
import numpy as np
from miniscope.projections import Projections
import numpy as np
import matplotlib.pyplot as plt
import logging
from scipy.signal import detrend
from caiman import movie as cm_movie
from src2.shared.misc_functions import updateCSVCell, denoiseMovie, _prepAxes
import PySimpleGUI as sg

class MiniscopeProcessor():

    def computeProjections(movie: cm.movie):
        """Calculates the projections of self.movie and stores the result in self.projections."""
        
        max = np.amax(movie, axis=0)
        std = np.std(movie, axis=0)
        min = np.amin(movie, axis=0)
        mean = np.mean(movie, axis=0)
        median = np.median(movie, axis=0)
        range = max - min
        time = movie.mean(axis=(1,2))

        return Projections(max, std, min, mean, median, range, time)
    

    def preprocess_movie(self, movie, crop=False, square=False,
                         crop_gui=False, denoise=False, detrend=False,
                         df_over_f=False):
        """Run preprocessing steps based on provided flags."""
        steps_applied = []

        if crop:
            col = 'crop_square' if square else 'crop'
            movie = self.crop_movie(movie, col, gui=crop_gui)
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

        return movie, processing_step
    

    def crop_movie(self, movie, col, gui=False):
        coords = self._analysisParamsDict.get(col)
        if coords is None or gui:
            coords = self._crop_window(movie)

        x0, x1 = sorted([coords['x0'], coords['x1']])
        y0, y1 = sorted([coords['y0'], coords['y1']])

        cropped_movie = movie[:, y0:y1, x0:x1]

        updateCSVCell(
            data=f'({x0},{y0},{x1},{y1})',
            columnTitle=col,
            lineNum=self.lineNum,
            csvFile=self.analysisParamsFilename)

        return cropped_movie

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






















    def _crop_window(self):
        """GUI window for cropping movie."""
        layout = [
            [sg.Text('Select Crop Region')],
            [sg.Graph((self.movie.shape[2], self.movie.shape[1]), (0, 0),
                      (self.movie.shape[2], self.movie.shape[1]),
                      key='-GRAPH-', drag_submits=True)],
            [sg.Button('Submit'), sg.Button('Cancel')]
        ]

        window = sg.Window('Crop Movie', layout)
        graph = window['-GRAPH-']
        
        coords = {'x0': 0, 'y0': 0, 'x1': 0, 'y1': 0}
        
        rect_id = None
        
        while True:
            event, values = window.read()
            
            if event in (sg.WINDOW_CLOSED, 'Cancel'):
                break
            
            elif event == '-GRAPH-':
                x1, y1 = values['-GRAPH-']
                coords.update({'x1': int(x1), 'y1': int(y1)})
                if rect_id:
                    graph.delete_figure(rect_id)
                rect_id = graph.draw_rectangle((coords['x0'], coords['y0']),
                                               (coords['x1'], coords['y1']),
                                               line_color='red')
            
            elif event == 'Submit':
                break
        
        window.close()
        
        return coords