import base64
import io
import caiman as cm
import numpy as np
from src2.miniscope.projections import Projections
from src2.miniscope.cropMovieGUI import cropMovieGUI
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
            gui = cropMovieGUI(coords_dict, projections, movie_height, movie_width)
            coords = gui.coords_dict

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
