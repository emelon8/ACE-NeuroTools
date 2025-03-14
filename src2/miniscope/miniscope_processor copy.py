import numpy as np
import matplotlib.pyplot as plt
import io
import base64
import logging
from scipy.signal import detrend
from caiman import movie as cm_movie
from src2.shared.misc_functions import updateCSVCell, denoiseMovie, _prepAxes
import PySimpleGUI as sg

logging.basicConfig(level=logging.INFO)

class CaMovieProcessor:


    def preprocess_movie(self, save_movie=False, crop=False, square=False,
                         crop_gui=False, denoise=False, detrend=False,
                         df_over_f=False):
        """Run preprocessing steps based on provided flags."""

        steps_applied = []

        if crop:
            col = 'crop_square' if square else 'crop'
            self.crop_movie(col, gui=crop_gui)
            steps_applied.append('_croppedSquare' if square else '_cropped')

        if denoise:
            self.denoise_movie()
            steps_applied.append('_denoised')

        if detrend:
            self.detrend_movie()
            steps_applied.append('_detrended')

        if df_over_f:
            self.compute_df_over_f()
            steps_applied.append('_dFoverF')

        if save_movie:
            processing_step = ''.join(steps_applied)
            self.save_ca_movie(processing_step=processing_step)
    

    def crop_movie(self, col, gui=False):
        """Crop movie using saved coordinates or GUI."""
        self.compute_projections()

        coords = self._analysisParamsDict.get(col)
        if coords is None or gui:
            coords = self._crop_window()

        x0, x1 = sorted([coords['x0'], coords['x1']])
        y0, y1 = sorted([coords['y0'], coords['y1']])

        self.movie = self.movie[:, y0:y1, x0:x1]

        updateCSVCell(
            data=f'({x0},{y0},{x1},{y1})',
            columnTitle=col,
            lineNum=self.lineNum,
            csvFile=self.analysisParamsFilename)

    def denoise_movie(self):
        """Denoise the calcium imaging movie."""
        denoiseMovie(self.experiment['calcium imaging directory'], mode='display', jobID=self.jobID)

    def detrend_movie(self, method='median', plot_trend=False):
        """Detrend fluorescence data from the movie."""
        if plot_trend:
            fig, ax = _prepAxes(xLabel='Frames', yLabel='Mean Fluorescence')
            ax.plot(np.mean(self.movie, axis=(1, 2)), label='Original Data')

        if method == 'linear':
            detrend(self.movie, axis=0, overwrite_data=True)
        elif method == 'median':
            self.movie.debleach()
        else:
            raise ValueError(f"Unsupported detrending method '{method}'.")

        if plot_trend:
            ax.plot(np.mean(self.movie, axis=(1, 2)), label='Detrended Data')
            ax.legend()
            plt.show()

    def compute_df_over_f(self, secs_window=5, quantile_min=8,
                          method='delta_f_over_sqrt_f'):
        """Compute delta F over F or delta F over sqrt(F)."""
        movie_positive = self.movie + 1  # Avoid zero values
        self.movie, _ = cm_movie.computeDFF(movie_positive,
                                            secs_window,
                                            quantile_min,
                                            method)

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

    def compute_projections(self):
        """Compute projections for visualization."""
        projections = {
            'max': np.max(self.movie, axis=0),
            'min': np.min(self.movie, axis=0),
            'mean': np.mean(self.movie, axis=0),
            'std': np.std(self.movie, axis=0),
            'median': np.median(self.movie, axis=0),
            'range': np.ptp(self.movie, axis=0)
        }
        
        self.projections = projections

    def save_ca_movie(self, processing_step=''):
        """Save processed calcium imaging movie."""
        filename = f"{self.experiment['movie filename']}{processing_step}.tif"
        
        # Placeholder for actual saving logic
        logging.info(f'Saving movie to {filename}')
    
    def import_ca_movies(self):
        """Placeholder method to import movie data."""
        # Implement actual importing logic here
        pass
