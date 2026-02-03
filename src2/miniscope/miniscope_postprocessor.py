import src2.shared.misc_functions as misc_functions
import caiman as cm
import numpy as np
from tqdm import tqdm
from src2.miniscope.projections import Projections
from scipy.signal import find_peaks, hilbert
from src2.miniscope.gui_utils import component_gui
from src2.shared.multitaper_spectrogram_python import multitaper_spectrogram
from src2.miniscope.filtered_miniscope_data import FilterMiniscopeData
import cv2
import time
import matplotlib.pyplot as plt
from src2.miniscope.movie_io import MovieIO

#Methods for loading and manipulating components after CNMF-E is run
class MiniscopePostprocessor:
    """Post-processor for CNMF-E extracted calcium imaging components.
    
    Performs component refinement, calcium event detection, spectral analysis,
    and phase computation on processed miniscope data.
    
    Attributes:
        data_manager: MiniscopeDataManager with CNMFE results.
        frame_rate: Recording frame rate from data_manager.
        dview: CaImAn distributed view for parallel processing.
    """
    
    def __init__(self, data_manager):
        """Initialize post-processor with data manager.
        
        Automatically computes movie projections on initialization.
        
        Args:
            data_manager: MiniscopeDataManager with movie and CNMFE results.
        """
        self.data_manager = data_manager
        self.data_manager.projections = self.compute_projections(self.data_manager.movie)
        self.frame_rate = self.data_manager.fr
        self.dview = self.data_manager.dview
    
    
    def postprocess_calcium_movie(self, remove_components_with_gui=True,  
                                        find_calcium_events=True,
                                          derivative_for_estimates='first', 
                                          event_height = 5, 
                                        compute_miniscope_phase=True, 
                                        filter_miniscope_data=True,
                                          n=2, 
                                          cut=[0.1,1.5], 
                                          ftype='butter', 
                                          btype='bandpass', 
                                          inline=False,
                                        compute_miniscope_spectrogram=True,
                                          window_length = 30, 
                                          window_step = 3, 
                                          freq_lims = [0,15], 
                                          time_bandwidth = 2):
        """Run the complete post-processing pipeline on CNMF-E results.
        
        Performs component curation via GUI, calcium event detection, phase
        computation, filtering, and spectral analysis.
        
        Args:
            remove_components_with_gui: If True, open interactive GUI for component selection.
            find_calcium_events: If True, detect calcium transient events.
            derivative_for_estimates: Derivative order for event detection ('zeroth', 'first', 'second').
            event_height: Threshold height for peak detection.
            compute_miniscope_phase: If True, compute instantaneous phase via Hilbert.
            filter_miniscope_data: If True, apply bandpass filter to projections.
            n: Filter order.
            cut: [low, high] cutoff frequencies for bandpass.
            ftype: Filter type ('butter', 'fir').
            btype: Band type for filter.
            inline: If True, replace original data with filtered.
            compute_miniscope_spectrogram: If True, compute multitaper spectrogram.
            window_length: Spectrogram window length in seconds.
            window_step: Spectrogram step size in seconds.
            freq_lims: [low, high] frequency limits for spectrogram.
            time_bandwidth: Time-bandwidth product for multitaper.
            
        Returns:
            Updated MiniscopeDataManager with all post-processing results.
        """
        
        if remove_components_with_gui:
            if self.data_manager.CNMFE_obj is not None and self.data_manager.CNMFE_obj.estimates.A is not None and self.data_manager.CNMFE_obj.estimates.A.shape[0] > 0:
                self.data_manager.CNMFE_obj.estimates.plot_contours()
                self.data_manager.CNMFE_obj.estimates = component_gui(self.data_manager.movie, self.data_manager.CNMFE_obj.estimates, self.data_manager.projections)
            else:
                print("No components found or CNMF-E object is None. Skipping component GUI.")
            
        if find_calcium_events:
            self.data_manager.ca_events_idx = self.find_calcium_events_with_derivatives(self.data_manager.CNMFE_obj.estimates, derivative_for_estimates, event_height)
        
        if compute_miniscope_spectrogram:
            data = self.data_manager.projections.time
            PSDSpectMiniscope, tSpect, freqsSpect, pSpectMiniscope = self.compute_miniscope_spectrogram(data, frame_rate=self.frame_rate, window_length=window_length, window_step=window_step, freq_lims=freq_lims, time_bandwidth=time_bandwidth)
            h, ax = misc_functions.spectrogram(tSpect/60, freqsSpect, pSpectMiniscope, xLabel='Time (min)')
            self.data_manager.PSD_spect, self.data_manager.t_spect, self.data_manager.freqs_spect, self.data_manager.p_spect = PSDSpectMiniscope, tSpect, freqsSpect, pSpectMiniscope
            
        if compute_miniscope_phase:
            self.data_manager.miniscope_phases = self.compute_miniscope_phase(self.data_manager.projections.time)
            
        if filter_miniscope_data:
            filter_object = FilterMiniscopeData(self.data_manager.projections, self.frame_rate, n=n, cut=cut, ftype=ftype, btype=btype)
            filter_object.filter_miniscope_data
            self.data_manager.filter_object = filter_object
            
            if inline == True:
                self.data_manager.projections.time = filter_object.filtered_data
        
        return self.data_manager
            


    def compute_projections(self, movie: cm.movie=None):
        """Compute spatial and temporal projections of the movie.
        
        Calculates max, min, mean, median, std, range projections and
        mean fluorescence time series.
        
        Args:
            movie: CaImAn movie object to compute projections from.
            
        Returns:
            Projections object containing all computed projections.
        """
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


    def evaluate_components(self, estimates, opts_caiman, min_SNR=3, r_values_min=0.85):
        """Compute quality metrics for CNMF-E components.
        
        Evaluates each component's SNR and spatial correlation, storing
        indices of components that pass the specified thresholds.
        
        Args:
            estimates: CNMF-E estimates object with extracted components.
            opts_caiman: CaImAn parameters object.
            min_SNR: Minimum signal-to-noise ratio threshold.
            r_values_min: Minimum spatial correlation threshold.
            
        Returns:
            Tuple of (estimates, opts_caiman) with quality metrics added.
        """
        #This line assumes processing has been performed, and a single memory mapped file exists on your computer under caiman/temp. The filepath should be stored in fnames in opts_caiman
        Yr, dims, T = cm.load_memmap(opts_caiman.get('data', 'fnames')[0])
        images = Yr.T.reshape((T,) + dims, order='F')

        opts_caiman.set('quality', {'min_SNR': min_SNR, 'rval_thr': r_values_min, 'use_cnn': False})
        estimates.evaluate_components(images, opts_caiman)
        return estimates, opts_caiman
    
    
    def find_calcium_events_with_deconvolution(self, estimates, opts_caiman, dview, dff_flag=False):
        """Detect calcium events using deconvolution-based spike inference.
        
        Uses CaImAn's deconvolution to extract spike trains from calcium
        traces and identifies event indices.
        
        Args:
            estimates: CNMF-E estimates with calcium traces.
            opts_caiman: CaImAn parameters for deconvolution.
            dview: Distributed view for parallel processing.
            dff_flag: If True, use DF/F traces.
            
        Returns:
            Dict mapping neuron indices to arrays of event frame indices.
        """
        ca_events_idx = {}
        #ensure deconvolution has not already been performed on estimates
        if not hasattr(estimates, 'S') or estimates.S is None:
            estimates.deconvolve(opts_caiman, dview=dview, dff_flag=dff_flag)
            
        for k in range(estimates.C.shape[0]):
            spike_train = estimates.S[k]  # Spike train for neuron k
            event_indices = np.where(spike_train > 0)[0]  # Indices of non-zero spikes
            ca_events_idx[k] = event_indices.astype(int)
        return ca_events_idx
    
      
    def find_calcium_events_with_derivatives(self, estimates, derivative='first', event_height=5):
        """Detect calcium events using derivative-based peak detection.
        
        Computes the specified derivative of calcium traces and finds
        peaks above the threshold height.
        
        Args:
            estimates: CNMF-E estimates with calcium traces (C matrix).
            derivative: Order of derivative ('zeroth', 'first', 'second').
            event_height: Minimum peak height threshold.
            
        Returns:
            Dict mapping neuron indices to arrays of event frame indices.
        """
        print('Finding indices of calcium events...')
        n_components = estimates.C.shape[0]
        neuron_indices = range(n_components)

        if derivative not in ['zeroth', 'first', 'second']:
            raise ValueError("derivative must be 'zeroth', 'first', or 'second'")
            
        ca_events_idx = {}
        for k in neuron_indices:
            trace = estimates.C[k]
            if derivative == 'zeroth':
                data = trace
            elif derivative == 'first':
                data = np.diff(trace)
            elif derivative == 'second':
                data = np.diff(trace, n=2)
            # Ensure data is at least 1D and has enough points for find_peaks
            if data.size > 0:
                peaks, _ = find_peaks(data, height=event_height)
                ca_events_idx[k] = peaks.astype(int)  # Ensure integer indices
            else:
                ca_events_idx[k] = np.array([], dtype=int)  # Empty array for no peaks
        return ca_events_idx
    
    
    @staticmethod
    def compute_miniscope_spectrogram(data, frame_rate, window_length=30, window_step=3, freq_lims=[0,15], time_bandwidth=2, plot_spectrogram=True):
        """Compute multitaper spectrogram of mean fluorescence signal.
        
        Uses the multitaper method for robust spectral estimation with
        reduced variance compared to standard periodograms.
        
        Args:
            data: 1D array of mean fluorescence over time.
            frame_rate: Recording frame rate in Hz.
            window_length: Window length in seconds.
            window_step: Step size between windows in seconds.
            freq_lims: [low, high] frequency range to compute.
            time_bandwidth: Time-bandwidth product (higher = smoother).
            plot_spectrogram: If True, display the spectrogram plot.
            
        Returns:
            Tuple of (PSD matrix, time points, frequencies, PSD in dB).
        """
        print('Computing spectrogram of average miniscope fluorescence...')
        # Set spectrogram params
        fs = int(frame_rate)
        num_tapers = time_bandwidth * 2 - 1
        window_params = [window_length, window_step]
        minNfft = 0  # No minimum nfft
        detrend_opt = 'constant'  # detrend each window by subtracting the average
        multiprocess = False  # use multiprocessing
        n_jobs = 3  # use 3 cores in multiprocessing
        weighting = 'unity'  # weight each taper at 1
        plot_on = False  # plot spectrogram using multitaper_spectrogram()
        return_fig = False  # do not return plotted spectrogram
        clim_scale = False # do not auto-scale colormap
        verbose = True  # print extra info
        xyflip = False  # do not transpose spect output matrix
        
        # Compute the multitaper spectrogram and convert the output to decibels
        PSDSpectMiniscope, tSpect, freqsSpect = multitaper_spectrogram(data, fs, freq_lims, time_bandwidth, num_tapers, window_params, minNfft, detrend_opt, multiprocess, n_jobs, weighting, plot_on, return_fig, clim_scale, verbose, xyflip)
        pSpectMiniscope = 10 * np.log10(PSDSpectMiniscope)
        
        if plot_spectrogram:
            h, ax = misc_functions.spectrogram(tSpect/60, freqsSpect, pSpectMiniscope, xLabel='Time (min)')        
    
        return PSDSpectMiniscope, tSpect, freqsSpect, pSpectMiniscope


    def compute_miniscope_phase(self, data):
        """Compute instantaneous phase of fluorescence using Hilbert transform.
        
        Args:
            data: 1D array of fluorescence signal.
            
        Returns:
            1D array of instantaneous phase in radians (-pi to pi).
        """
        analytic_signal_miniscope = hilbert(data)
        return np.angle(analytic_signal_miniscope)
    
    
    def calculate_component_movie(self, dm):
        """Create movies showing neural activity and background separately.
        
        Reconstructs the movie as A*C (neural) plus background model.
        
        Args:
            dm: MiniscopeDataManager with CNMFE results.
            
        Returns:
            Tuple of (neural_movie, background_movie) as CaImAn movies.
        """
        Yr, dims, T = cm.load_memmap(dm.opts_caiman.get('data', 'fnames')[0])
        neural_activity = dm.CNMFE_obj.estimates.A @ dm.CNMFE_obj.estimates.C  # AC
        neural_movie = cm.movie(neural_activity).reshape(dims + (-1,), order='F').transpose([2, 0, 1])
        background_model = dm.CNMFE_obj.estimates.compute_background(Yr);  # build in function -- explore source code for details
        bg_movie = cm.movie(background_model).reshape(dims + (-1,), order='F').transpose([2, 0, 1])
        
        return neural_movie, bg_movie
    
    def calculate_black_component_movie(self, dm):
        """Create a movie with detected neuron regions blacked out.
        
        Useful for visualizing background activity without neural signals.
        
        Args:
            dm: MiniscopeDataManager with CNMFE estimates.
            
        Returns:
            CaImAn movie with neuron ROI pixels set to zero.
        """
        estimates = dm.CNMFE_obj.estimates
        num_frames, movie_height, movie_width = dm.movie.shape
        neuron_mask = np.sum(estimates.A.toarray(), axis=1) > 0  # True where any neuron has non-zero value
        neuron_mask = neuron_mask.reshape(movie_height, movie_width, order='F')  # Reshape to 2D
        movie_without_neurons = dm.movie.copy()
        for frame in range(num_frames):
            movie_without_neurons[frame][neuron_mask] = 0
        
        print("Calculations complete. Attempting to play movie...", flush=True)
        return movie_without_neurons
    
    

    
    