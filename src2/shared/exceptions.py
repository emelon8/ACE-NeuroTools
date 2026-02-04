class ExperimentAnalysisError(Exception):
    """Base exception for experiment_analysis package."""
    pass

class DataImportError(ExperimentAnalysisError):
    """Failed to load raw data or metadata."""
    pass

class ProcessingError(ExperimentAnalysisError):
    """Error during signal/video processing algorithms (CaImAn, filtering, etc)."""
    pass

class ConfigurationError(ExperimentAnalysisError):
    """Invalid configuration parameters or missing config files."""
    pass

class DataIntegrityError(ExperimentAnalysisError):
    """Issues with data shape, corrupted files, or NaN/Inf values."""
    pass
