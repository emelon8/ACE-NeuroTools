import src2.shared.misc_functions as misc_functions
import caiman as cm
import numpy as np
import matplotlib.pyplot as plt
import os
from tqdm import tqdm
from src2.miniscope.projections import Projections
from scipy.signal import detrend, find_peaks, hilbert
from src2.miniscope.gui_utils import component_gui
from src2.shared.multitaper_spectrogram_python import multitaper_spectrogram
from src2.miniscope.filtered_miniscope_data import FilterMiniscopeData

#Methods for loading and manipulating components after CNMF-E is run
#The movie file path that is passed into this class should be the same movie that was passed into MiniscopeProcessor
class MiniscopePostprocessor:
    
    
    def __init__(self, movie_filepath, estimates_filepath, opts_caiman_filepath, dview=None):
        self.movie = cm.load(movie_filepath)
        self.estimates_filepath = estimates_filepath
        self.projections = self.compute_projections(self.movie)
        self.opts_caiman = cm.source_extraction.cnmf.params.CNMFParams(params_from_file=opts_caiman_filepath)
        self.CNMFE_obj = cm.source_extraction.cnmf.cnmf.load_CNMF(self.estimates_filepath)
        self.frame_rate = self.opts_caiman.get('data', 'fr')
        self.dview = dview
    
    
    def postprocess_calcium_movie(self, remove_components_with_gui=True, evaluate_components=False, find_calcium_events=True, compute_miniscope_spectrogram=True, compute_miniscope_phase=True, filter_miniscope_data=False):
        if remove_components_with_gui:
            self.CNMFE_obj.estimates.plot_contours()
            self.CNMFE_obj.estimates = component_gui(self.movie, self.CNMFE_obj.estimates, self.projections)
            print("These are the components")
            print(self.CNMFE_obj.estimates.idx_components)
            
        if find_calcium_events:
            ca_events_idx = self.find_calcium_events_with_deconvolution(self.CNMFE_obj.estimates, self.opts_caiman, dview=self.dview, dff_flag=False)
        
        if compute_miniscope_spectrogram:
            data = np.mean(self.CNMFE_obj.estimates.C, axis=0)  # Fallback to all components
            PSDSpectMiniscope, tSpect, freqsSpect, pSpectMiniscope = self.compute_miniscope_spectrogram(data, frame_rate=self.frame_rate)
            h, ax = misc_functions.spectrogram(tSpect/60, freqsSpect, pSpectMiniscope, xLabel='Time (min)')
            
        if compute_miniscope_phase:
            miniscope_phase = self.compute_miniscope_phase(self.projections.time)
            
        if filter_miniscope_data:
            filter_object = FilterMiniscopeData(self.projections, self.frame_rate)
            filter_object.filter_miniscope_data
            self.filtered_miniscope_data = filter_object.filtered_data
            


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


    def evaluate_components(self, estimates, opts_caiman, min_SNR=3, r_values_min=0.85):
        """""Computes the quality metrics for each component and stores the indices of the components that pass user specified thresholds."""
        #This line assumes processing has been performed, and a single memory mapped file exists on your computer under caiman/temp. The filepath should be stored in fnames in opts_caiman
        Yr, dims, T = cm.load_memmap(opts_caiman.get('data', 'fnames')[0])
        images = Yr.T.reshape((T,) + dims, order='F')

        opts_caiman.set('quality', {'min_SNR': min_SNR, 'rval_thr': r_values_min, 'use_cnn': False})
        estimates.evaluate_components(images, opts_caiman)
        return estimates, opts_caiman
    
    
    def find_calcium_events_with_deconvolution(self, estimates, opts_caiman, dview, dff_flag=False):
        ca_events_idx = {}
        #ensure deconvolution has not already been performed on estimates
        if not hasattr(estimates, 'S') or estimates.S is None:
            estimates.deconvolve(opts_caiman, dview=dview, dff_flag=dff_flag)
            
        for k in range(estimates.C.shape[0]):
            spike_train = estimates.S[k]  # Spike train for neuron k
            event_indices = np.where(spike_train > 0)[0]  # Indices of non-zero spikes
            ca_events_idx[k] = event_indices.astype(int)
        return ca_events_idx
    
      
    def find_calcium_events_with_derivatives(self, estimates, neuron='all', derivative='first', height=5):
        #I am not sure this function works as intended for first and second derivatives. I need to reseach the math better
        #This method looks for calcium events in self.estimates.C.
        #DERIVATIVE is the number of times to take the derivative before thresholding.
        #HEIGHT is the threshold above which to detect calcium events. The units depend on the DERIVATIVE used.
        print('Finding indices of calcium events...')
        n_components = estimates.C.shape[0]
        if neuron == 'all':
            neuron_indices = range(n_components)
        else:
            if isinstance(neuron, int):
                neuron = [neuron]
            if not isinstance(neuron, list) or not all(isinstance(i, int) for i in neuron):
                raise ValueError("neuron must be 'all', an integer, or a list of integers")
            if not all(0 <= i < n_components for i in neuron):
                raise ValueError(f"neuron indices must be between 0 and {n_components-1}")
            neuron_indices = neuron
        
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
                peaks, _ = find_peaks(data, height=height)
                ca_events_idx[k] = peaks.astype(int)  # Ensure integer indices
            else:
                ca_events_idx[k] = np.array([], dtype=int)  # Empty array for no peaks
        return ca_events_idx
    

# Signal processing methods for the mean fluorescence over time
    def compute_miniscope_spectrogram(self, data, frame_rate, window_length=30, window_step=3, freq_lims=[0,15], time_bandwidth=2):
        """Estimate (and plot) the multi-taper spectrogram (of the mean miniscope fluorescence). Developed with Mike Prerau's function."""
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
    
        return PSDSpectMiniscope, tSpect, freqsSpect, pSpectMiniscope


    def compute_miniscope_phase(self, data):
        analytic_signal_miniscope = hilbert(data)
        return np.angle(analytic_signal_miniscope)
    
    