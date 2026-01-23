#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example: Using component_gui with EEG time series visualization

This script demonstrates how to use the updated component_gui function
to visualize both calcium imaging data and synchronized EEG/ephys data.

Created on: 2025
Author: Updated GUI functionality
"""

import numpy as np
from src2.miniscope.gui_utils import component_gui
from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_postprocessor import MiniscopePostprocessor
# If you have ephys data:
# from src.classes import miniscope_ephys


def example_without_eeg():
    """
    Example 1: Use the GUI without EEG data (original behavior)
    """
    print("Example 1: GUI without EEG data")
    print("-" * 50)
    
    # Load your miniscope data
    dm = MiniscopeDataManager(line_num=1)
    # ... perform CNMF-E processing ...
    
    # Use GUI without EEG - works exactly as before
    estimates = component_gui(
        dm.movie, 
        dm.CNMFE_obj.estimates, 
        dm.projections
    )
    
    print("Selected components without EEG visualization")
    return estimates


def example_with_eeg_frame_synced():
    """
    Example 2: Use the GUI with EEG data that's already synchronized 
    frame-by-frame with calcium imaging
    """
    print("\nExample 2: GUI with frame-synchronized EEG data")
    print("-" * 50)
    
    # Load your miniscope data
    dm = MiniscopeDataManager(line_num=1)
    # ... perform CNMF-E processing ...
    
    # Assume you have EEG data downsampled to match the calcium frame rate
    # This could come from:
    # 1. Pre-processed EEG that was downsampled
    # 2. EEG extracted at TTL timepoints (see next example)
    
    # For demonstration, create synthetic EEG data
    # In real usage, load your actual EEG data
    num_frames = dm.movie.shape[0]
    eeg_data = np.random.randn(num_frames) * 100  # Replace with actual EEG
    
    # Use GUI with EEG
    estimates = component_gui(
        dm.movie, 
        dm.CNMFE_obj.estimates, 
        dm.projections,
        eeg_data=eeg_data,
        frame_rate=dm.metadata['frameRate']
    )
    
    print("Selected components with EEG visualization")
    return estimates


def example_with_eeg_from_miniscope_ephys():
    """
    Example 3: Use the GUI with EEG data from a miniscope-ephys experiment
    where data is synchronized via TTL events
    """
    print("\nExample 3: GUI with EEG from miniscope-ephys experiment")
    print("-" * 50)
    
    # This example requires the older src.classes structure
    # Uncomment if you're using that:
    """
    from src.classes import miniscope_ephys
    
    # Create miniscope-ephys object
    obj = miniscope_ephys.miniscopeEphys(
        lineNum=35,
        filename='data/experiments.csv',
        analysisFilename='data/analysis_parameters.csv'
    )
    
    # Import and synchronize data
    channel = 'PFCLFPvsCBEEG'
    obj.importEphysData(channels=channel)
    obj.importNeuralynxEvents()
    obj.syncNeuralynxMiniscopeTimestamps(channel=channel)
    obj.findEphysIdxOfTTLEvents(channel=channel)
    
    # Extract EEG values at calcium imaging timepoints
    eeg_synced = obj.ephys[channel][obj.ephysIdxAllTTLEvents]
    eeg_times = obj.tEphys[channel][obj.ephysIdxAllTTLEvents]
    
    # Load calcium imaging data and estimates
    # (assuming you've already done CNMF-E processing)
    
    # Use GUI with synchronized EEG
    estimates = component_gui(
        obj.movie, 
        obj.estimates, 
        obj.projections,
        eeg_data=eeg_synced,
        eeg_timestamps=eeg_times,
        frame_rate=obj.experiment['frameRate']
    )
    
    print("Selected components with synchronized EEG from miniscope-ephys")
    return estimates
    """
    
    print("(This example requires miniscope_ephys class - see code comments)")


def example_integration_with_postprocessor():
    """
    Example 4: Integrate EEG visualization with MiniscopePostprocessor
    
    This shows how to modify the postprocessor to include EEG data
    """
    print("\nExample 4: Integration with MiniscopePostprocessor")
    print("-" * 50)
    
    print("""
    To integrate EEG visualization into your processing pipeline:
    
    1. Load your EEG data before calling postprocess_calcium_movie()
    2. Store it in your data_manager or pass it as a parameter
    3. Modify the miniscope_postprocessor.py file:
    
    In MiniscopePostprocessor.postprocess_calcium_movie():
    
    Original code:
        self.data_manager.CNMFE_obj.estimates = component_gui(
            self.data_manager.movie, 
            self.data_manager.CNMFE_obj.estimates, 
            self.data_manager.projections
        )
    
    Modified code:
        # Load EEG data (example)
        eeg_data = self.data_manager.eeg_synced  # You need to add this
        
        self.data_manager.CNMFE_obj.estimates = component_gui(
            self.data_manager.movie, 
            self.data_manager.CNMFE_obj.estimates, 
            self.data_manager.projections,
            eeg_data=eeg_data,
            eeg_timestamps=self.data_manager.eeg_timestamps,  # optional
            frame_rate=self.frame_rate
        )
    
    4. Make sure to add eeg_data and eeg_timestamps attributes to your
       data_manager before calling postprocess_calcium_movie()
    """)


def main():
    """
    Run all examples
    """
    print("=" * 60)
    print("COMPONENT GUI WITH EEG VISUALIZATION - EXAMPLES")
    print("=" * 60)
    
    # Example 1: Without EEG (backward compatible)
    print("\n")
    example_without_eeg()
    
    # Example 2: With frame-synchronized EEG
    print("\n")
    example_with_eeg_frame_synced()
    
    # Example 3: With miniscope-ephys synchronized EEG
    print("\n")
    example_with_eeg_from_miniscope_ephys()
    
    # Example 4: Integration guide
    print("\n")
    example_integration_with_postprocessor()
    
    print("\n" + "=" * 60)
    print("For more information, see the component_gui docstring:")
    print(">>> help(component_gui)")
    print("=" * 60)


if __name__ == "__main__":
    main()




