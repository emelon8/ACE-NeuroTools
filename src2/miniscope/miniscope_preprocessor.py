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
import src2.shared.misc_functions as misc_functions
import PySimpleGUI as sg
import numpy as np
from tqdm import tqdm
from src2.miniscope.movie_io import MovieIO
import os
from src2.miniscope.gui_utils import crop_gui


class MiniscopePreprocessor:

    def __init__(self, movie, miniscope_dir_path):
        self.movie = movie
        self.miniscope_dir_path = miniscope_dir_path
    

    def preprocess_calcium_movie(self, coords_dict=None, crop=False, detrend=False, df_over_f=False, crop_job_name_for_file="_cropped"):
        """Run preprocessing steps based on provided flags.
           coords_dict: is passed in and represents what you want the final coordinates for the movie to be in the form {'x0': A, 'y0': B, 'x1': C, 'y1': D}"""
        
        miniscope_dir_path = self.miniscope_dir_path
        movie = self.movie
        steps_applied = ['preprocessed']
        
        if crop:
            projections = self.compute_projections(movie)
            movie, coords_dict = self.crop_movie(movie, coords_dict, projections, movie.shape[1], movie.shape[2])
            steps_applied.append(f'_{crop_job_name_for_file}')

        if detrend:
            movie = self.detrend_movie(movie)
            steps_applied.append('_detrended')

        if df_over_f:
            movie = self.compute_df_over_f(movie)
            steps_applied.append('_dFoverF')

        movie_file_name = ''.join(steps_applied)

        # save movie!
        movie_filepath = MovieIO.save_movie(movie, miniscope_dir_path, movie_file_name)
        return movie_filepath, coords_dict
    
    
    
    
    
    def compute_projections(self, movie: cm.movie=None):
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
    

    def crop_movie(self, movie, coords_dict, projections, movie_height, movie_width):
        if coords_dict is None:
            coords_dict = crop_gui(coords_dict, projections, movie_height, movie_width)
        x0, x1 = sorted([coords_dict['x0'], coords_dict['x1']])
        y0, y1 = sorted([coords_dict['y0'], coords_dict['y1']])

        cropped_movie = movie[:, y0:y1, x0:x1]
        coords = f'({x0},{y0},{x1},{y1})'
        print(coords)
        print(cropped_movie.shape)
        return cropped_movie, coords
        

    def detrend_movie(self, movie, method='median', plot_trend=True):
        try:                    
            if method == 'linear':
                detrended_movie = detrend(movie, axis=0)
            elif method == 'median':
                detrended_movie = movie.debleach()
            else:
                raise ValueError(f"Unsupported detrending method '{method}'.")
                return movie
        except:
            print("Detrending failed, returning original movie")
            return movie
        
        if plot_trend and detrended_movie is not None:
            fig, ax = plt.subplots()
            ax.set_xlabel('Frames')
            ax.set_ylabel('Mean Fluorescence')
            
            # Plot original data
            original_mean = np.mean(movie, axis=(1, 2))
            ax.plot(original_mean, label='Original Data', color='blue')
            
            # Plot detrended data
            detrended_mean = np.mean(detrended_movie, axis=(1, 2))
            ax.plot(detrended_mean, label='Detrended Data', color='red', linestyle='--')
            
            ax.legend()
            ax.grid(True)
            plt.tight_layout()
            plt.show()
            
        return detrended_movie
        

    def compute_df_over_f(self, movie, secs_window=5, quantile_min=8, method='delta_f_over_sqrt_f'):
        try:
            #ensure all pixels are positive
            if np.min(movie) < 0:
                movie = movie - np.min(movie)
            if np.min(movie) == 0:
                movie = movie + 1
            processed_movie, _ = cm_movie.computeDFF(movie, secs_window, quantile_min, method)
            return processed_movie
        except:
            raise ValueError("Your movie has pixels with non-positive brightness as a result of another preprocessing step, computing df over f failed")
            return movie

