# Multimodal API Outputs & Analysis Guide

The `multimodal_api.py` script integrates both modalities, performing alignment and cross-modal analysis.

## Outputs
*   **Phase-Locking Histograms:** The script calculates the EEG phase at the exact timestamps of Calcium events.
    *   **Analysis:** Examine the resulting histograms to determine if neuronal activity is modulated by specific LFP oscillations (e.g., locking to the trough of Theta).
*   **Aligned Data:** The script produces time-aligned data structures, allowing for correlation analysis between calcium amplitude and EEG power.
