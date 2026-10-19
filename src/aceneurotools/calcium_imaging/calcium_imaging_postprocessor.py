from typing import TYPE_CHECKING, Any

import caiman as cm
import numpy as np
from scipy.signal import find_peaks, hilbert

import aceneurotools.shared.misc_functions as misc_functions
from aceneurotools.calcium_imaging.filtered_calcium_imaging_data import FilterCalciumImagingData
from aceneurotools.calcium_imaging.gui_utils import component_gui
from aceneurotools.calcium_imaging.pipeline_results import PostprocessingResult
from aceneurotools.calcium_imaging.projections import Projections
from aceneurotools.shared.calcium_imaging_names import LEGACY_OPTIONS, accept_legacy_keywords
from aceneurotools.shared.multitaper_spectrogram_python import multitaper_spectrogram

if TYPE_CHECKING:
    from caiman.source_extraction.cnmf.estimates import Estimates
    from caiman.source_extraction.cnmf.params import CNMFParams

    from aceneurotools.calcium_imaging.calcium_imaging_data_manager import CalciumImagingDataManager

#Methods for loading and manipulating components after CNMF-E is run
class CalciumImagingPostprocessor:
    """Post-processor for CNMF-E extracted calcium imaging components.

    Performs component refinement, calcium event detection, spectral analysis,
    and phase computation on processed calcium imaging data.

    Attributes:
        data_manager: CalciumImagingDataManager with CNMFE results.
        frame_rate: Recording frame rate from data_manager.
        dview: CaImAn distributed view for parallel processing.
    """

    data_manager: 'CalciumImagingDataManager'
    frame_rate: float
    dview: Any
    result: PostprocessingResult  # populated after postprocess_calcium_movie() returns

    def __init__(self, data_manager: 'CalciumImagingDataManager') -> None:
        """Initialize post-processor with data manager.

        Automatically computes movie projections on initialization.

        Args:
            data_manager: CalciumImagingDataManager with movie and CNMFE results.
        """
        self.data_manager = data_manager
        self.data_manager.projections = self.compute_projections(self.data_manager.movie)
        self.frame_rate = float(self.data_manager.fr)
        self.dview = self.data_manager.dview
        if not hasattr(self.data_manager, "calcium_imaging_phases"):
            self.data_manager.calcium_imaging_phases = getattr(self.data_manager, "miniscope_phases", None)


    @accept_legacy_keywords(**LEGACY_OPTIONS)
    def postprocess_calcium_movie(
        self,
        remove_components_with_gui: bool = True,
        find_calcium_events: bool = True,
        derivative_for_estimates: str = 'first',
        event_height: float = 5,
        compute_calcium_imaging_phase: bool = True,
        filter_calcium_imaging_data: bool = True,
        n: int = 2,
        cut: list[float] = [0.1, 1.5],
        ftype: str = 'butter',
        btype: str = 'bandpass',
        inline: bool = False,
        compute_calcium_imaging_spectrogram: bool = True,
        window_length: float = 30,
        window_step: float = 3,
        freq_lims: list[float] = [0, 15],
        time_bandwidth: float = 2
    ) -> 'CalciumImagingDataManager':
        """Run the complete post-processing pipeline on CNMF-E results.

        Performs component curation via GUI, calcium event detection, phase
        computation, filtering, and spectral analysis.

        Args:
            remove_components_with_gui: If True, open interactive GUI for component selection.
            find_calcium_events: If True, detect calcium transient events.
            derivative_for_estimates: Derivative order for event detection ('zeroth', 'first', 'second').
            event_height: Threshold height for peak detection.
            compute_calcium_imaging_phase: If True, compute instantaneous phase via Hilbert.
            filter_calcium_imaging_data: If True, apply bandpass filter to projections.
            n: Filter order.
            cut: [low, high] cutoff frequencies for bandpass.
            ftype: Filter type ('butter', 'fir').
            btype: Band type for filter.
            inline: If True, replace original data with filtered.
            compute_calcium_imaging_spectrogram: If True, compute multitaper spectrogram.
            window_length: Spectrogram window length in seconds.
            window_step: Spectrogram step size in seconds.
            freq_lims: [low, high] frequency limits for spectrogram.
            time_bandwidth: Time-bandwidth product for multitaper.

        Returns:
            Updated CalciumImagingDataManager with all post-processing results.
        """

        if remove_components_with_gui:
            if self.data_manager.CNMFE_obj is not None and self.data_manager.CNMFE_obj.estimates.A is not None and self.data_manager.CNMFE_obj.estimates.A.shape[0] > 0:
                if hasattr(self.data_manager, 'diag_logger') and self.data_manager.diag_logger is not None: self.data_manager.diag_logger.pause_timer()
                self.data_manager.CNMFE_obj.estimates.plot_contours()
                self.data_manager.CNMFE_obj.estimates = component_gui(self.data_manager.movie, self.data_manager.CNMFE_obj.estimates, self.data_manager.projections)
                if hasattr(self.data_manager, 'diag_logger') and self.data_manager.diag_logger is not None: self.data_manager.diag_logger.resume_timer()
            else:
                print("No components found or CNMF-E object is None. Skipping component GUI.")

        if find_calcium_events:
            if self.data_manager.CNMFE_obj is not None and self.data_manager.CNMFE_obj.estimates.C is not None:
                self.data_manager.ca_events_idx = self.find_calcium_events_with_derivatives(self.data_manager.CNMFE_obj.estimates, derivative_for_estimates, event_height)
            else:
                print("WARNING: No CNMF-E components found (estimates.C is None). Skipping calcium event detection.")
                self.data_manager.ca_events_idx = {}

        if compute_calcium_imaging_spectrogram:
            data = self.data_manager.projections.time
            psd_spect_calcium_imaging, tSpect, freqsSpect, p_spect_calcium_imaging = self.compute_calcium_imaging_spectrogram(data, frame_rate=self.frame_rate, window_length=window_length, window_step=window_step, freq_lims=freq_lims, time_bandwidth=time_bandwidth)
            h, ax = misc_functions.spectrogram(tSpect/60, freqsSpect, p_spect_calcium_imaging, xLabel='Time (min)')
            self.data_manager.PSD_spect, self.data_manager.t_spect, self.data_manager.freqs_spect, self.data_manager.p_spect = psd_spect_calcium_imaging, tSpect, freqsSpect, p_spect_calcium_imaging

        if compute_calcium_imaging_phase:
            self.data_manager.calcium_imaging_phases = self.compute_calcium_imaging_phase(self.data_manager.projections.time)
            self.data_manager.miniscope_phases = self.data_manager.calcium_imaging_phases

        if filter_calcium_imaging_data:
            filter_object = FilterCalciumImagingData(self.data_manager.projections, self.frame_rate, n=n, cut=cut, ftype=ftype, btype=btype)
            filter_object.filter_calcium_imaging_data()
            self.data_manager.filter_object = filter_object

            if inline == True:
                self.data_manager.projections.time = filter_object.filtered_data

        # Capture outputs in a structured result for callers that prefer the
        # dataclass API over interrogating data_manager directly.
        self.result = PostprocessingResult(
            projections=self.data_manager.projections,
            ca_events_idx=self.data_manager.ca_events_idx,
            PSD_spect=self.data_manager.PSD_spect,
            t_spect=self.data_manager.t_spect,
            freqs_spect=self.data_manager.freqs_spect,
            p_spect=self.data_manager.p_spect,
            calcium_imaging_phases=self.data_manager.calcium_imaging_phases,
            filter_object=self.data_manager.filter_object,
        )

        return self.data_manager



    def compute_projections(self, movie: cm.movie | None = None) -> Projections:
        """Compute spatial and temporal projections of the movie.

        Delegates to :func:`aceneurotools.calcium_imaging.projections.compute_projections`
        — the single canonical implementation shared with
        :class:`~aceneurotools.calcium_imaging.calcium_imaging_preprocessor.CalciumImagingPreprocessor`.

        Args:
            movie: CaImAn movie object to compute projections from.

        Returns:
            Projections object containing all computed projections.
        """
        from aceneurotools.calcium_imaging.projections import compute_projections as _compute

        return _compute(movie)


    def evaluate_components(
        self,
        estimates: 'Estimates',
        opts_caiman: 'CNMFParams',
        min_SNR: float = 3,
        r_values_min: float = 0.85
    ) -> tuple['Estimates', 'CNMFParams']:
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


    def find_calcium_events_with_deconvolution(
        self,
        estimates: 'Estimates',
        opts_caiman: 'CNMFParams',
        dview: Any,
        dff_flag: bool = False
    ) -> dict[int, np.ndarray]:
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


    @staticmethod
    def find_calcium_events_with_derivatives(
        estimates: 'Estimates',
        derivative: str = 'first',
        event_height: float = 5
    ) -> dict[int, np.ndarray]:
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
            data = np.array([])
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
    def compute_calcium_imaging_spectrogram(
        data: np.ndarray,
        frame_rate: float,
        window_length: float = 30,
        window_step: float = 3,
        freq_lims: list[float] = [0, 15],
        time_bandwidth: float = 2,
        plot_spectrogram: bool = True
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
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
        print('Computing spectrogram of average calcium imaging fluorescence...')
        # Set spectrogram params
        fs = int(frame_rate)
        num_tapers = int(time_bandwidth * 2 - 1)
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
        mt_result = multitaper_spectrogram(data, fs, freq_lims, time_bandwidth, num_tapers, window_params, minNfft, detrend_opt, multiprocess, n_jobs, weighting, plot_on, return_fig, clim_scale, verbose, xyflip)
        psd_spect_calcium_imaging, tSpect, freqsSpect = mt_result[:3]
        p_spect_calcium_imaging = 10 * np.log10(psd_spect_calcium_imaging)

        if plot_spectrogram:
            h, ax = misc_functions.spectrogram(tSpect/60, freqsSpect, p_spect_calcium_imaging, xLabel='Time (min)')

        return psd_spect_calcium_imaging, tSpect, freqsSpect, p_spect_calcium_imaging


    def compute_calcium_imaging_phase(self, data: np.ndarray) -> np.ndarray:
        """Compute instantaneous phase of fluorescence using Hilbert transform.

        Args:
            data: 1D array of fluorescence signal.

        Returns:
            1D array of instantaneous phase in radians (-pi to pi).
        """
        analytic_signal_calcium_imaging = hilbert(data)
        return np.angle(analytic_signal_calcium_imaging)


    def calculate_component_movie(self, dm: 'CalciumImagingDataManager') -> tuple[cm.movie, cm.movie]:
        """Create movies showing neural activity and background separately.

        Reconstructs the movie as A*C (neural) plus background model.

        Args:
            dm: CalciumImagingDataManager with CNMFE results.

        Returns:
            Tuple of (neural_movie, background_movie) as CaImAn movies.
        """
        Yr, dims, T = cm.load_memmap(dm.opts_caiman.get('data', 'fnames')[0])
        neural_activity = dm.CNMFE_obj.estimates.A @ dm.CNMFE_obj.estimates.C  # AC
        neural_movie = cm.movie(neural_activity).reshape(dims + (-1,), order='F').transpose([2, 0, 1])
        background_model = dm.CNMFE_obj.estimates.compute_background(Yr)  # build in function -- explore source code for details
        bg_movie = cm.movie(background_model).reshape(dims + (-1,), order='F').transpose([2, 0, 1])

        return neural_movie, bg_movie

    def calculate_black_component_movie(self, dm: 'CalciumImagingDataManager') -> cm.movie:
        """Create a movie with detected neuron regions blacked out.

        Useful for visualizing background activity without neural signals.

        Args:
            dm: CalciumImagingDataManager with CNMFE estimates.

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






CalciumImagingPostprocessor.compute_miniscope_phase = CalciumImagingPostprocessor.compute_calcium_imaging_phase
CalciumImagingPostprocessor.compute_miniscope_spectrogram = CalciumImagingPostprocessor.compute_calcium_imaging_spectrogram

# Compatibility for existing imports.
MiniscopePostprocessor = CalciumImagingPostprocessor
