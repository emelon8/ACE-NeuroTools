import base64
import io
import caiman as cm
import numpy as np
from src2.miniscope.projections import Projections
from src2.miniscope.crop_movie_gui import CropMovieGUI
import numpy as np
import matplotlib.pyplot as plt
import logging
from scipy.signal import detrend
from caiman import movie as cm_movie
from src2.shared.misc_functions import updateCSVCell, denoiseMovie, _prepAxes
import PySimpleGUI as sg
import numpy as np
from tqdm import tqdm
from src2.miniscope.movie_io import MovieIO
import os


class MiniscopePreprocessor():

    def __init__(self, movie:cm.movie):
        self.movie = movie

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
    

    def preprocess_calcium_movie(self, miniscope_dir_path, coords_dict=None, crop=False, denoise=False, detrend=False, df_over_f=False, crop_job_name_for_file=""):
        """Run preprocessing steps based on provided flags.
           coords_dict: is passed in and represents what you want the final coordinates for the movie to be in the form {'x0': A, 'y0': B, 'x1': C, 'y1': D}"""
        movie = self.movie
        steps_applied = ['preprocessed']
        coords_dict_final = coords_dict

        if crop:
            projections = self.computeProjections(movie)
            movie, coords_dict_final = self.crop_movie(coords_dict, projections, movie.shape[1], movie.shape[2])
            if crop_job_name_for_file:
                steps_applied.append(f'_{crop_job_name_for_file}')
            else:
                steps_applied.append('_cropped')

        if denoise:
            movie = self.denoise_movie(movie, miniscope_dir_path)
            steps_applied.append('_denoised')

        if detrend:
            movie = self.detrend_movie(movie)
            steps_applied.append('_detrended')

        if df_over_f:
            movie = self.compute_df_over_f(movie)
            steps_applied.append('_dFoverF')

        movie_file_name = ''.join(steps_applied)

        # save movie!
        movie_file_path = MovieIO.save_movie(movie, miniscope_dir_path, movie_file_name)
        return movie_file_path, coords_dict_final
    

    def crop_movie(self, coords_dict, projections, movie_height, movie_width):
        if coords_dict is None:
            gui = CropMovieGUI(coords_dict, projections, movie_height, movie_width)
            coords_dict = gui.coords_dict
        x0, x1 = sorted([coords_dict['x0'], coords_dict['x1']])
        y0, y1 = sorted([coords_dict['y0'], coords_dict['y1']])

        cropped_movie = self.movie[:, y0:y1, x0:x1]
        coords = f'({x0},{y0},{x1},{y1})'
        print(coords)
        print(cropped_movie.shape)
        return cropped_movie, coords
    

    def denoise_movie(self, movie, miniscope_dir_path, mode='save'):
        """The miscellaneous function denoiseMovie() takes in a directory, not a caiman movie, so I had to do some file handling to turn the passed in movie into a file. 
           Feel free to adjust the logic if it doesn't work on your machine. You can also directly call the miscellaneous fucntion denoiseMovie in your script to denoise a directory directly
           
           This method makes a temporary folder in your miniscope directory, converts the movie into a file in the temp folder, denoises the file,
           then converts the denoised file back into a caiman movie and deletes the temporary folder and anything in it. Returns the denoised movie
        """
        temp_movie_dir = os.path.join(miniscope_dir_path, 'temp')
        os.makedirs(temp_movie_dir, exist_ok=False)
        temp_movie_filepath = os.path.join(temp_movie_dir, '0.avi')
        movie.save(temp_movie_filepath, compress=0)
        denoiseMovie(temp_movie_dir, mode=mode)
        denoised_filepath = os.path.join(temp_movie_dir, 'Denoised', 'denoised0.avi')
        movie = cm.load(denoised_filepath)
        try:
            os.remove(denoised_filepath)
            os.rmdir(os.path.join(temp_movie_dir, 'Denoised'))
            os.remove(temp_movie_filepath)
            os.rmdir(temp_movie_dir)
        except:
            print("Error: Could not successfully delete the temp folder in your miniscope directory")
        return movie
        

    def detrend_movie(self, movie, method='median', plot_trend=False):
        try:    
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
        
        except Exception as e:
            print(f"[Error] Failed to detrend movie with method '{method}': {e}. Are all of the pixels positive in your cropped movie?")
            return None

    def compute_df_over_f(self, movie, secs_window=5, quantile_min=8,
                          method='delta_f_over_sqrt_f'):
        movie_positive = movie + 1  # Avoid zero values
        processed_movie, _ = cm_movie.computeDFF(movie_positive,
                                                 secs_window,
                                                 quantile_min,
                                                 method)
        return processed_movie

