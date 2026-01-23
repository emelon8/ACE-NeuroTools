# Miniscope API Outputs & Analysis Guide

The `miniscope_api.py` script runs the complete calcium imaging pipeline.

## Outputs
*   **`estimates.hdf5`**: This is the primary data product. It is an HDF5 file containing the full `CNMF-E` object (spatial footprints `A`, temporal traces `C`, spikes `S`).
    *   **Analysis:** Load this file using `caiman.source_extraction.cnmf.cnmf.load_CNMF()` to perform downstream analysis like neuron clustering, activity correlation, or decoding.
*   **Component Selection GUI:** If `remove_components_with_gui=True`, an interactive window allows you to manually accept/reject neurons. This is critical for filtering out noise or "bad" components before saving the final estimates.
