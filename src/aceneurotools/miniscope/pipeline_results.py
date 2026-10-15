"""Structured result dataclasses and stage config dataclasses for the Miniscope pipeline.

Each pipeline stage (preprocessing, processing, postprocessing) produces a
frozen dataclass that captures its outputs.  Stage-specific config dataclasses
provide a compact alternative to calling ``MiniscopePipeline.run()`` with 30+
positional kwargs — use ``MiniscopePipeline.run_with_configs()`` instead.

No caiman or cv2 imports at module level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Stage result dataclasses (frozen — produced by each processor)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PreprocessingResult:
    """Outputs captured by :class:`~aceneurotools.miniscope.miniscope_preprocessor.MiniscopePreprocessor`.

    Attributes:
        preprocessed_movie_filepath: Absolute path to the saved preprocessed
            movie file (e.g. ``/data/.../preprocessed.tif``).  ``None`` if
            the movie was not saved.
        coords: Crop coordinates in GUI notation
            ``{'x0': int, 'y0': int, 'x1': int, 'y1': int}``, or ``None``
            if cropping was not applied.
    """

    preprocessed_movie_filepath: str | None
    coords: dict[str, int] | None


@dataclass(frozen=True)
class ProcessingResult:
    """Outputs captured by :class:`~aceneurotools.miniscope.miniscope_processor.MiniscopeProcessor`.

    Attributes:
        CNMFE_obj: CaImAn CNMF object (or ``None`` if CNMF-E was not run).
        estimates_filepath: Path to saved ``estimates.hdf5``, or ``None``.
        opts_caiman_filepath: Path to saved ``opts_caiman.json``, or ``None``.
        opts_caiman: CaImAn ``CNMFParams`` object used during processing.
        motion_corrected_movie_filepath: Path to the motion-corrected memory
            map, or ``None`` if motion correction was not applied.
    """

    CNMFE_obj: Any
    estimates_filepath: str | None
    opts_caiman_filepath: str | None
    opts_caiman: Any
    motion_corrected_movie_filepath: str | None


@dataclass(frozen=True)
class PostprocessingResult:
    """Outputs captured by :class:`~aceneurotools.miniscope.miniscope_postprocessor.MiniscopePostprocessor`.

    Attributes:
        projections: :class:`~aceneurotools.miniscope.projections.Projections` object
            with spatial and temporal projections.
        ca_events_idx: Dict mapping neuron index to event-frame index array.
        PSD_spect: Power spectral density matrix from multitaper spectrogram.
        t_spect: Time axis of the spectrogram (seconds).
        freqs_spect: Frequency axis of the spectrogram (Hz).
        p_spect: Spectrogram in decibels.
        miniscope_phases: Instantaneous phase from Hilbert transform (radians).
        filter_object: :class:`~aceneurotools.miniscope.filtered_miniscope_data.FilterMiniscopeData`
            instance, or ``None`` if filtering was skipped.
    """

    projections: Any
    ca_events_idx: Any
    PSD_spect: np.ndarray | None
    t_spect: np.ndarray | None
    freqs_spect: np.ndarray | None
    p_spect: np.ndarray | None
    miniscope_phases: np.ndarray | None
    filter_object: Any


# ---------------------------------------------------------------------------
# Stage config dataclasses (mutable — passed into run_with_configs)
# ---------------------------------------------------------------------------


@dataclass
class PreprocessConfig:
    """Configuration for the preprocessing stage of :class:`~aceneurotools.pipelines.miniscope.MiniscopePipeline`.

    Attributes:
        crop: If ``True``, crop the movie (opens GUI or uses ``crop_coords``).
        crop_coords: Explicit crop coordinates ``(x0, y0, x1, y1)``, or
            ``None`` to read from ``analysis_parameters.csv`` / open the GUI.
        detrend_method: ``'median'`` or ``'linear'`` for photobleaching
            correction, or ``None`` to skip detrending.
        df_over_f: If ``True``, compute DF/F normalisation.
        secs_window: Sliding-window size in seconds for DF/F baseline.
        quantile_min: Percentile (0–100) used as the DF/F baseline.
        df_over_f_method: ``'delta_f_over_sqrt_f'`` or ``'delta_f_over_f'``.
    """

    crop: bool = True
    crop_coords: Any | None = None
    detrend_method: str | None = "median"
    df_over_f: bool = False
    secs_window: float = 5
    quantile_min: float = 8
    df_over_f_method: str = "delta_f_over_sqrt_f"


@dataclass
class ProcessConfig:
    """Configuration for the processing stage of :class:`~aceneurotools.pipelines.miniscope.MiniscopePipeline`.

    Attributes:
        parallel: If ``True``, use CaImAn multiprocessing cluster.
        n_processes: Number of worker processes for CaImAn.
        apply_motion_correction: If ``True``, run piecewise-rigid motion correction.
        inspect_motion_correction: If ``True``, display diagnostic plots after
            motion correction (ignored in headless mode).
        plot_params: If ``True``, show correlation/PNR and patch plots to help
            tune CNMF-E parameters (ignored in headless mode).
        run_CNMFE: If ``True``, run CNMF-E source extraction.
        save_estimates: If ``True``, save CNMF-E estimates to HDF5.
        save_CNMFE_estimates_filename: Filename for the saved estimates file.
        save_CNMFE_params: If ``True``, save CaImAn parameters to JSON.
    """

    parallel: bool = False
    n_processes: int = 12
    apply_motion_correction: bool = False
    inspect_motion_correction: bool = False
    plot_params: bool = False
    run_CNMFE: bool = False
    save_estimates: bool = True
    save_CNMFE_estimates_filename: str = "estimates.hdf5"
    save_CNMFE_params: bool = False


@dataclass
class PostprocessConfig:
    """Configuration for the post-processing stage of :class:`~aceneurotools.pipelines.miniscope.MiniscopePipeline`.

    Attributes:
        remove_components_with_gui: If ``True``, open the component curation
            GUI (ignored in headless mode).
        find_calcium_events: If ``True``, detect calcium transient events.
        derivative_for_estimates: Derivative order for event detection:
            ``'zeroth'``, ``'first'``, or ``'second'``.
        event_height: Minimum peak height for event detection.
        compute_miniscope_phase: If ``True``, compute instantaneous phase via
            Hilbert transform.
        filter_miniscope_data: If ``True``, apply a bandpass filter to the
            mean-fluorescence projection.
        n: Butterworth / FIR filter order.
        cut: ``[low_hz, high_hz]`` cutoff frequencies for the bandpass filter.
        ftype: Filter family (``'butter'`` or ``'fir'``).
        btype: Band type (``'bandpass'``, ``'low'``, ``'high'``).
        inline: If ``True``, replace the projection data with the filtered
            version in-place.
        compute_miniscope_spectrogram: If ``True``, compute the multitaper
            spectrogram of the mean-fluorescence signal.
        window_length: Spectrogram window length in seconds.
        window_step: Spectrogram step size in seconds.
        freq_lims: ``[low_hz, high_hz]`` frequency range for the spectrogram.
        time_bandwidth: Time-bandwidth product for multitaper estimation.
    """

    remove_components_with_gui: bool = True
    find_calcium_events: bool = True
    derivative_for_estimates: str = "first"
    event_height: float = 5
    compute_miniscope_phase: bool = True
    filter_miniscope_data: bool = True
    n: int = 2
    cut: list[float] = field(default_factory=lambda: [0.1, 1.5])
    ftype: str = "butter"
    btype: str = "bandpass"
    inline: bool = False
    compute_miniscope_spectrogram: bool = True
    window_length: float = 30
    window_step: float = 3
    freq_lims: list[float] = field(default_factory=lambda: [0, 15])
    time_bandwidth: float = 2
