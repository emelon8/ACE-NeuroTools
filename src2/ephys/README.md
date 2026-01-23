# Ephys API Outputs & Analysis Guide

The `ephys_api.py` script handles loading, filtering, and visualizing EEG/LFP data.

## Outputs
*   **Channel Plots:** Visualizes raw or filtered voltage traces. Use these to inspect signal quality and identify artifacts (e.g., movement noise).
*   **Spectrograms:** Visualizes power across frequencies over time. Essential for identifying brain states (e.g., Theta rhythm, Delta waves).
*   **Phase Plots:** Displays the instantaneous phase of the signal, useful for verifying phase extraction for specific bands.
