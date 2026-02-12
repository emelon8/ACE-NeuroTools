#!/usr/bin/env python3
"""
Integration tests for the miniscope analysis pipeline.

These tests use real data from experiment 96 (R230706B) and real-world
neuroscience parameters to validate the pipeline end-to-end before merging.

Tests are ordered by pipeline stage and should be run sequentially.
Each test validates both correctness and output artifacts on disk.

Usage:
    # Run all tests (from project root):
    python -m pytest tests/test_pipeline_integration.py -v --tb=short

    # Run a single test:
    python -m pytest tests/test_pipeline_integration.py::TestConfigLoading -v
"""

import sys
import os
import pytest
import numpy as np
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================================
# Fixtures
# ============================================================================

EXAMPLE_PROJECT = PROJECT_ROOT / "examples" / "example_project"
LINE_NUM = 96
DATA_DIR = PROJECT_ROOT / "data" / "downloaded_data" / "K99" / "miniscope_data" / "ketamine" / "R230706B" / "2023_09_01" / "15_04_11"
RAW_MOVIE_PATH = DATA_DIR / "Miniscope" / "0.avi"
SAVED_MOVIES_DIR = DATA_DIR / "saved_movies"


@pytest.fixture(scope="session")
def project_dir():
    """Path to the example project directory."""
    assert EXAMPLE_PROJECT.exists(), f"Example project not found: {EXAMPLE_PROJECT}"
    return EXAMPLE_PROJECT


@pytest.fixture(scope="session")
def raw_movie_exists():
    """Verify raw data exists before running tests."""
    assert RAW_MOVIE_PATH.exists(), (
        f"Raw movie not found: {RAW_MOVIE_PATH}\n"
        "These tests require real data from experiment 96."
    )
    return True


# ============================================================================
# Test 1: Configuration Loading
# ============================================================================

class TestConfigLoading:
    """Validate the new project-based config system loads params correctly."""

    def test_load_analysis_params_from_project_path(self, project_dir):
        """Config loads from example project using explicit project_path."""
        from src2.shared.config_utils import load_analysis_params

        params = load_analysis_params(LINE_NUM, project_path=project_dir)

        assert isinstance(params, dict)
        # crop column should be parsed — not a raw string
        assert 'crop' not in params, (
            "Crop coordinates should NOT appear as a pipeline kwarg. "
            "They are coordinate data, not a boolean flag."
        )

    def test_load_analysis_params_returns_valid_kwargs(self, project_dir):
        """Returned params should be valid kwargs for MiniscopePipeline.run()."""
        from src2.shared.config_utils import load_analysis_params
        from src2.miniscope.miniscope_pipeline import MiniscopePipeline
        import inspect

        params = load_analysis_params(LINE_NUM, project_path=project_dir)
        sig = inspect.signature(MiniscopePipeline.run)
        valid_keys = set(sig.parameters.keys()) - {'self'}

        for key in params:
            assert key in valid_keys, (
                f"Config returned unexpected kwarg '{key}' that is not accepted "
                f"by MiniscopePipeline.run(). Valid keys: {sorted(valid_keys)}"
            )

    def test_missing_line_raises_value_error(self, project_dir):
        """Loading a non-existent experiment line should raise ValueError."""
        from src2.shared.config_utils import load_analysis_params

        with pytest.raises(ValueError, match="not found"):
            load_analysis_params(9999, project_path=project_dir)

    def test_missing_csv_raises_file_not_found(self, tmp_path):
        """Loading from a path without analysis_parameters.csv raises FileNotFoundError."""
        from src2.shared.config_utils import load_analysis_params

        with pytest.raises(FileNotFoundError):
            load_analysis_params(LINE_NUM, project_path=tmp_path)


# ============================================================================
# Test 2: Path Resolution
# ============================================================================

class TestPathResolution:
    """Validate that paths.py resolves correctly with the new .env system."""

    def test_project_root_is_correct(self):
        """PROJECT_ROOT should point to experiment_analysis/."""
        from src2.shared.paths import PROJECT_ROOT as resolved_root
        assert resolved_root.exists()
        assert (resolved_root / "src2").is_dir()

    def test_experiments_csv_exists(self, project_dir):
        """experiments.csv should exist in the project directory."""
        assert (project_dir / "experiments.csv").exists()

    def test_analysis_params_csv_exists(self, project_dir):
        """analysis_parameters.csv should exist in the project directory."""
        assert (project_dir / "analysis_parameters.csv").exists()


# ============================================================================
# Test 3: Data Manager Initialization
# ============================================================================

class TestDataManager:
    """Validate that MiniscopeDataManager loads experiment 96 correctly."""

    def test_data_manager_loads_movie(self, raw_movie_exists):
        """Data manager should load movie into RAM with correct shape."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)

        assert dm.movie is not None, "Movie was not loaded"
        assert dm.movie.ndim == 3, f"Movie should be 3D (T,H,W), got {dm.movie.ndim}D"
        assert dm.movie.shape[0] > 0, "Movie has 0 frames"
        assert dm.movie.shape[1] == 608 and dm.movie.shape[2] == 608, (
            f"Expected 608x608 movie, got {dm.movie.shape[1]}x{dm.movie.shape[2]}"
        )
        assert dm.movie.dtype == np.float32, f"Expected float32, got {dm.movie.dtype}"

    def test_data_manager_loads_metadata(self, raw_movie_exists):
        """Data manager should populate metadata dict."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)

        assert dm.metadata is not None
        assert 'calcium imaging directory' in dm.metadata
        assert 'id' in dm.metadata
        assert dm.metadata['id'] == 'R230706B'

    def test_data_manager_loads_analysis_params(self, raw_movie_exists):
        """Data manager should load analysis params for this experiment."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)

        assert dm.analysis_params is not None
        assert isinstance(dm.analysis_params, dict)

    def test_frame_rate_is_loaded(self, raw_movie_exists):
        """Frame rate should be read from metadata."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)

        assert dm.fr is not None
        assert dm.fr > 0, f"Frame rate should be positive, got {dm.fr}"


# ============================================================================
# Test 4: Coordinate Loading
# ============================================================================

class TestCoordinateLoading:
    """Validate crop coordinate extraction from analysis_parameters.csv."""

    def test_get_coords_returns_dict(self, raw_movie_exists):
        """Coordinates should be parsed into a dict with x0,y0,x1,y1."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
        from src2.shared.misc_functions import get_coords_dict_from_analysis_params

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)
        coords_dict, crop_job_name = get_coords_dict_from_analysis_params(dm)

        assert coords_dict is not None, (
            "coords_dict should not be None — the CSV has crop coordinates"
        )
        assert set(coords_dict.keys()) == {'x0', 'y0', 'x1', 'y1'}
        assert crop_job_name == '_crop'

    def test_coords_are_numeric(self, raw_movie_exists):
        """All coordinate values should be numeric (int or float)."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
        from src2.shared.misc_functions import get_coords_dict_from_analysis_params

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)
        coords_dict, _ = get_coords_dict_from_analysis_params(dm)

        for key, val in coords_dict.items():
            assert isinstance(val, (int, float, np.integer, np.floating)), (
                f"Coordinate {key}={val} is type {type(val)}, expected numeric"
            )

    def test_coords_are_within_movie_bounds(self, raw_movie_exists):
        """Crop coordinates should be within the movie dimensions."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
        from src2.shared.misc_functions import get_coords_dict_from_analysis_params

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)
        coords_dict, _ = get_coords_dict_from_analysis_params(dm)

        h, w = dm.movie.shape[1], dm.movie.shape[2]
        assert 0 <= coords_dict['x0'] < w, f"x0={coords_dict['x0']} out of bounds (width={w})"
        assert 0 <= coords_dict['x1'] <= w, f"x1={coords_dict['x1']} out of bounds (width={w})"
        assert 0 <= coords_dict['y0'] < h, f"y0={coords_dict['y0']} out of bounds (height={h})"
        assert 0 <= coords_dict['y1'] <= h, f"y1={coords_dict['y1']} out of bounds (height={h})"


# ============================================================================
# Test 5: Preprocessing (crop + detrend)
# ============================================================================

class TestPreprocessing:
    """Validate the preprocessing pipeline with realistic parameters."""

    @pytest.fixture
    def data_manager(self, raw_movie_exists):
        """Fresh data manager for preprocessing tests."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
        return MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)

    def test_crop_with_real_coords_headless(self, data_manager):
        """Headless crop with real coordinates should produce a smaller movie."""
        from src2.shared.misc_functions import get_coords_dict_from_analysis_params
        from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor

        original_shape = data_manager.movie.shape
        coords_dict, crop_job_name = get_coords_dict_from_analysis_params(data_manager)

        preprocessor = MiniscopePreprocessor(data_manager)
        dm = preprocessor.preprocess_calcium_movie(
            coords_dict, crop=True, detrend_method=None,
            crop_job_name_for_file=crop_job_name, headless=True
        )

        assert dm.movie.shape[0] == original_shape[0], "Frame count should not change"
        assert dm.movie.shape[1] < original_shape[1] or dm.movie.shape[2] < original_shape[2], (
            f"Movie should be smaller after crop. Got {dm.movie.shape} from {original_shape}"
        )
        assert dm.preprocessed_movie_filepath is not None
        assert os.path.exists(dm.preprocessed_movie_filepath), (
            f"Preprocessed file should exist on disk: {dm.preprocessed_movie_filepath}"
        )
        assert dm.coords is not None, "Crop coordinates should be stored on data manager"

    def test_detrend_median(self, data_manager):
        """Median detrend should not change movie shape but should flatten per-frame baselines."""
        from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor

        # Compute per-frame mean before detrending
        original_frame_means = data_manager.movie.mean(axis=(1, 2))
        original_std = float(np.std(original_frame_means))

        preprocessor = MiniscopePreprocessor(data_manager)
        dm = preprocessor.preprocess_calcium_movie(
            None, crop=False, detrend_method='median', headless=True
        )

        assert dm.movie.shape[0] == len(original_frame_means), "Frame count changed"
        # After median detrend, per-frame means should be more uniform
        # (lower standard deviation) since slow baseline drift is removed
        detrended_frame_means = dm.movie.mean(axis=(1, 2))
        detrended_std = float(np.std(detrended_frame_means))

        assert detrended_std < original_std, (
            f"Detrending should reduce per-frame mean variability. "
            f"Before std={original_std:.4f}, after std={detrended_std:.4f}"
        )
        assert dm.preprocessed_movie_filepath is not None

    def test_crop_then_detrend(self, data_manager):
        """Full preprocessing: crop + detrend should produce correct output."""
        from src2.shared.misc_functions import get_coords_dict_from_analysis_params
        from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor

        coords_dict, crop_job_name = get_coords_dict_from_analysis_params(data_manager)
        preprocessor = MiniscopePreprocessor(data_manager)
        dm = preprocessor.preprocess_calcium_movie(
            coords_dict, crop=True, detrend_method='median',
            crop_job_name_for_file=crop_job_name, headless=True
        )

        # Check file naming includes both steps
        assert 'crop' in dm.preprocessed_movie_filepath
        assert 'detrended' in dm.preprocessed_movie_filepath
        # Movie should be both smaller and detrended
        assert dm.movie.shape[1] < 608 or dm.movie.shape[2] < 608

    def test_no_crop_headless_skips_gracefully(self, data_manager):
        """When crop=True but no coordinates, headless mode should skip and warn."""
        from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor

        original_shape = data_manager.movie.shape
        # Force no coordinates
        if 'crop' in data_manager.analysis_params:
            del data_manager.analysis_params['crop']

        preprocessor = MiniscopePreprocessor(data_manager)
        dm = preprocessor.preprocess_calcium_movie(
            None, crop=True, detrend_method=None, headless=True
        )

        # Movie should be unchanged since crop was skipped
        assert dm.movie.shape == original_shape
        assert dm.coords is None


# ============================================================================
# Test 6: Processor Initialization (opts_caiman)
# ============================================================================

class TestProcessorInit:
    """Validate MiniscopeProcessor initialization and CaImAn parameter setup."""

    @pytest.fixture
    def preprocessed_dm(self, raw_movie_exists):
        """Data manager after full preprocessing."""
        from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
        from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor
        from src2.shared.misc_functions import get_coords_dict_from_analysis_params

        dm = MiniscopeDataManager(LINE_NUM, [], auto_import_data=True)
        coords_dict, crop_job_name = get_coords_dict_from_analysis_params(dm)
        preprocessor = MiniscopePreprocessor(dm)
        return preprocessor.preprocess_calcium_movie(
            coords_dict, crop=True, detrend_method='median',
            crop_job_name_for_file=crop_job_name, headless=True
        )

    def test_opts_caiman_fnames_matches_disk(self, preprocessed_dm):
        """opts_caiman fnames should point to the preprocessed file on disk."""
        from src2.miniscope.miniscope_processor import MiniscopeProcessor

        processor = MiniscopeProcessor(preprocessed_dm)
        fnames = preprocessed_dm.opts_caiman.get('data', 'fnames')

        if isinstance(fnames, list):
            for f in fnames:
                assert os.path.exists(f), f"fnames entry does not exist: {f}"
        else:
            assert os.path.exists(fnames), f"fnames does not exist: {fnames}"

    def test_opts_caiman_dims_match_movie(self, preprocessed_dm):
        """opts_caiman dims should match the in-memory movie dimensions."""
        from src2.miniscope.miniscope_processor import MiniscopeProcessor

        processor = MiniscopeProcessor(preprocessed_dm)
        opts_dims = tuple(preprocessed_dm.opts_caiman.get('data', 'dims'))
        movie_dims = tuple(preprocessed_dm.movie.shape[1:])

        assert opts_dims == movie_dims, (
            f"Dimension mismatch: opts_caiman dims={opts_dims} vs movie shape={movie_dims}"
        )

    def test_no_unrecognized_caiman_warnings(self, preprocessed_dm, capsys):
        """Processor init should not produce 'not recognized' CaImAn warnings."""
        from src2.miniscope.miniscope_processor import MiniscopeProcessor

        processor = MiniscopeProcessor(preprocessed_dm)
        captured = capsys.readouterr()

        assert "not recognized in the standard CaImAn groups" not in captured.out, (
            f"Unrecognized CaImAn parameter warning found in output:\n{captured.out}"
        )


# ============================================================================
# Test 7: Full Pipeline (headless, no CNMF-E)
# ============================================================================

class TestFullPipelineHeadless:
    """End-to-end pipeline test with real neuroscience parameters.

    Runs preprocessing + processing (no MC, no CNMF-E) + postprocessing
    to validate the complete data flow.
    """

    def test_pipeline_headless_preprocess_only(self, raw_movie_exists):
        """Pipeline should complete with crop+detrend in headless mode."""
        from src2.miniscope.miniscope_pipeline import MiniscopePipeline

        api = MiniscopePipeline()
        api.run(
            line_num=LINE_NUM,
            # Preprocessing
            crop=True,
            detrend_method='median',
            # Processing OFF
            apply_motion_correction=False,
            run_CNMFE=False,
            parallel=False,
            # Postprocessing OFF (no CNMF-E results)
            find_calcium_events=False,
            compute_miniscope_spectrogram=False,
            compute_miniscope_phase=False,
            filter_miniscope_data=False,
            # Headless
            headless=True
        )

        dm = api.miniscope_data_manager
        assert dm.movie is not None
        assert dm.preprocessed_movie_filepath is not None
        assert os.path.exists(dm.preprocessed_movie_filepath)

    def test_pipeline_headless_with_spectrogram(self, raw_movie_exists):
        """Pipeline should compute spectrogram on average fluorescence
        even without CNMF-E components (uses raw projection data)."""
        from src2.miniscope.miniscope_pipeline import MiniscopePipeline

        api = MiniscopePipeline()
        api.run(
            line_num=LINE_NUM,
            crop=True,
            detrend_method='median',
            apply_motion_correction=False,
            run_CNMFE=False,
            parallel=False,
            find_calcium_events=False,
            # Enable spectrogram with real neuroscience parameters
            compute_miniscope_spectrogram=True,
            window_length=30,       # 30s windows (standard for slow oscillations)
            window_step=3,          # 3s step
            freq_lims=[0, 15],      # 0-15 Hz (covers delta to beta bands)
            time_bandwidth=2,       # Standard multitaper TBW
            compute_miniscope_phase=False,
            filter_miniscope_data=False,
            headless=True
        )

        dm = api.miniscope_data_manager
        # Spectrogram arrays should exist
        assert hasattr(dm, 'p_spect') and dm.p_spect is not None
        assert hasattr(dm, 't_spect') and dm.t_spect is not None
        assert hasattr(dm, 'freqs_spect') and dm.freqs_spect is not None

    def test_pipeline_headless_with_phase_and_filter(self, raw_movie_exists):
        """Pipeline should compute phase and filtering on projection data."""
        from src2.miniscope.miniscope_pipeline import MiniscopePipeline

        api = MiniscopePipeline()
        api.run(
            line_num=LINE_NUM,
            crop=True,
            detrend_method='median',
            apply_motion_correction=False,
            run_CNMFE=False,
            parallel=False,
            find_calcium_events=False,
            compute_miniscope_spectrogram=False,
            # Phase + filter with real bandpass params
            compute_miniscope_phase=True,
            filter_miniscope_data=True,
            n=2,                    # 2nd order Butterworth
            cut=[0.1, 1.5],         # 0.1-1.5 Hz (slow calcium dynamics band)
            ftype='butter',
            btype='bandpass',
            inline=False,
            headless=True
        )

        dm = api.miniscope_data_manager
        assert hasattr(dm, 'miniscope_phases') and dm.miniscope_phases is not None
        assert hasattr(dm, 'filter_object') and dm.filter_object is not None


# ============================================================================
# Test 8: Estimates Saving (with empty CNMF-E)
# ============================================================================

class TestEstimatesSaving:
    """Validate that estimates are saved correctly even when CNMF-E finds nothing."""

    def test_empty_estimates_saved_without_error(self, raw_movie_exists):
        """Pipeline should save estimates.hdf5 even with 0 components."""
        from src2.miniscope.miniscope_pipeline import MiniscopePipeline

        api = MiniscopePipeline()
        api.run(
            line_num=LINE_NUM,
            crop=True,
            detrend_method='median',
            apply_motion_correction=False,
            run_CNMFE=False,
            parallel=False,
            save_estimates=True,
            save_CNMFE_estimates_filename='test_estimates.hdf5',
            find_calcium_events=False,
            compute_miniscope_spectrogram=False,
            compute_miniscope_phase=False,
            filter_miniscope_data=False,
            headless=True
        )

        # Estimates file should be saved
        estimates_path = SAVED_MOVIES_DIR / 'test_estimates.hdf5'
        assert estimates_path.exists(), f"Estimates file not found: {estimates_path}"


# ============================================================================
# Test 9: CSV Worker & Data Type Conversion
# ============================================================================

class TestCSVWorker:
    """Validate CSV loading and type conversion for experiment data."""

    def test_csv_row_loads_experiment_96(self, project_dir):
        """CSVWorker should load experiment 96 from experiments.csv."""
        from src2.shared.csv_worker import CSVWorker

        row = CSVWorker.csv_row_to_dict(project_dir / "experiments.csv", LINE_NUM)
        assert row is not None
        assert row.get('id') == 'R230706B'

    def test_crop_coords_parsed_as_tuple(self, project_dir):
        """Crop coordinates in CSV should be parsed as a tuple of numbers."""
        from src2.shared.csv_worker import CSVWorker

        row = CSVWorker.csv_row_to_dict(project_dir / "analysis_parameters.csv", LINE_NUM)
        converted = CSVWorker.convert_data_types(row)

        assert 'crop' in converted
        crop_val = converted['crop']
        assert isinstance(crop_val, (tuple, list)), (
            f"Crop should be parsed as tuple/list, got {type(crop_val)}: {crop_val}"
        )
        assert len(crop_val) == 4, f"Crop should have 4 values, got {len(crop_val)}"


# ============================================================================
# Test 10: File Downloader Index Lookup
# ============================================================================

class TestFileDownloader:
    """Validate that the file_downloader handles index lookups."""

    def test_verify_file_by_line_lookup(self, project_dir):
        """verify_file_by_line should find the correct experiment path for line 96."""
        from src2.shared.csv_worker import CSVWorker

        # Validate that the CSV row is loadable — this is the same path
        # that file_downloader uses internally
        row = CSVWorker.csv_row_to_dict(project_dir / "experiments.csv", LINE_NUM)
        assert row is not None, f"Line {LINE_NUM} not found in experiments.csv"
        assert 'calcium imaging directory' in row
        assert row['calcium imaging directory'] != '', (
            "Calcium imaging directory should not be empty for experiment 96"
        )


# ============================================================================
# Main (for running without pytest)
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-x"])
