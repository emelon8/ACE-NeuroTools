#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 26 14:04:10 2025

@author: sandbox1
"""

import os
import pandas as pd
import numpy as np
import csv
import json
import shutil
from datetime import datetime
from typing import List, Dict, Union, Tuple
import tkinter as tk
from tkinter import messagebox, simpledialog

# Import existing miniscope modules
from src2.miniscope.miniscope_api import MiniscopeAPI
from src2.shared.paths import ANALYSIS_PARAMS


class CNMFEParameterTester:
   
    
    def __init__(self, base_output_dir: str):
        self.base_output_dir = base_output_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.test_dir = None
        self.results_data = []
        self.analysis_params_df = None
        
        # Load analysis parameters CSV
        self._load_analysis_params()
        
    def _load_analysis_params(self):
        try:
            self.analysis_params_df = pd.read_csv(ANALYSIS_PARAMS)
            print(f"Loaded analysis parameters from: {ANALYSIS_PARAMS}")
            print(f"Available columns: {self.analysis_params_df.columns.tolist()}")
        except Exception as e:
            raise FileNotFoundError(f"Could not load analysis parameters CSV: {e}")
    
    def generate_test_values(self, parameter_name: str, baseline_value: Union[float, int], method: str = "automatic", custom_values: List[Union[float, int]] = None) -> List[Union[float, int]]:
        if method == "manual":
            if custom_values is None or len(custom_values) == 0:
                raise ValueError("Custom values must be provided for manual method")
            return custom_values
        
    
    def setup_test_directory(self, experiment_id: int, parameter_name: str) -> str:
        test_name = f"param_test_exp{experiment_id}_{parameter_name}_{self.timestamp}"
        self.test_dir = os.path.join(self.base_output_dir, test_name)
        os.makedirs(self.test_dir, exist_ok=True)
        
        print(f"Created test directory: {self.test_dir}")
        return self.test_dir
    
    def _create_temp_params_file(self, experiment_id: int, parameter_name: str, parameter_value: Union[float, int]) -> str:
       
        # Copy original dataframe
        temp_df = self.analysis_params_df.copy()
        
        # Modify the specific parameter
        temp_df.at[experiment_id - 1, parameter_name] = parameter_value
        
        # Save to temporary file
        temp_file = os.path.join(self.test_dir, f"temp_params_{parameter_name}_{parameter_value}.csv")
        temp_df.to_csv(temp_file, index=False)
        
        return temp_file
    
    def _organize_results(self, data_manager, output_dir: str):
        
        try:
            # Create saved_movies subdirectory
            saved_movies_dir = os.path.join(output_dir, 'saved_movies')
            os.makedirs(saved_movies_dir, exist_ok=True)
            
            # Move estimates file if it exists
            if hasattr(data_manager, 'estimates_filepath') and data_manager.estimates_filepath:
                if os.path.exists(data_manager.estimates_filepath):
                    dest_path = os.path.join(saved_movies_dir, 'estimates.hdf5')
                    shutil.copy2(data_manager.estimates_filepath, dest_path)
                    print(f"Copied estimates to: {dest_path}")
            
            # Move other relevant files if they exist
            if hasattr(data_manager, 'opts_caiman_filepath') and data_manager.opts_caiman_filepath:
                if os.path.exists(data_manager.opts_caiman_filepath):
                    dest_path = os.path.join(saved_movies_dir, 'opts_caiman.json')
                    shutil.copy2(data_manager.opts_caiman_filepath, dest_path)
                    
        except Exception as e:
            print(f"Warning: Could not organize all results: {e}")
    
    def run_single_test_with_editing(self, experiment_id: int, parameter_name: str, parameter_value: Union[float, int], filenames: List[str] = None) -> Dict:
        
        # Create subdirectory for this test
        test_subdir = os.path.join(self.test_dir, f"{parameter_name}_{parameter_value}")
        os.makedirs(test_subdir, exist_ok=True)
        
        print(f"\n{'='*60}")
        print(f"Testing {parameter_name} = {parameter_value}")
        print(f"Output directory: {test_subdir}")
        print(f"{'='*60}")
        
        # Temporarily modify the analysis parameters CSV for this test
        temp_params_file = self._create_temp_params_file(experiment_id, parameter_name, parameter_value)
        
        try:
            # Store original ANALYSIS_PARAMS path
            original_params_path = ANALYSIS_PARAMS
            
            # Temporarily replace the global ANALYSIS_PARAMS path
            import src2.shared.paths as paths_module
            paths_module.ANALYSIS_PARAMS = temp_params_file
            
            # Initialize and run MiniscopeAPI
            api = MiniscopeAPI()
            
            # Use default filenames if none provided
            if filenames is None:
                filenames = ['0.avi']
            
            # Run the analysis with current parameters
            api.run(
                line_num=experiment_id,
                filenames=filenames,
                
                # Preprocessing parameters - using defaults from your script
                crop=True,
                crop_with_crop=True,
                crop_square=False,
                detrend_method=None,
                df_over_f=False,
                secs_window=5,
                quantile_min=8,
                df_over_f_method='delta_f_over_sqrt_f',
                
                # Processing parameters
                parallel=False,
                n_processes=6,
                apply_motion_correction=False,
                inspect_motion_correction=False,  # Disable for batch processing
                plot_params=False,  # Disable for batch processing
                run_CNMFE=True,
                save_estimates=True,
                save_CNMFE_estimates_filename='estimates.hdf5',
                save_CNMFE_params=True,
                
                # Post-processing parameters - ENABLE GUI for interactive editing
                remove_components_with_gui=True,  # ENABLE GUI for this workflow
                find_calcium_events=True,
                derivative_for_estimates='first',
                event_height=5,
                compute_miniscope_phase=True,
                filter_miniscope_data=True,
                n=2,
                cut=[0.1, 1.5],
                ftype='butter',
                btype='bandpass',
                inline=True,
                compute_miniscope_spectrogram=True,
                window_length=30,
                window_step=3,
                freq_lims=[0, 15],
                time_bandwidth=2
            )
            
            # Count initial components found
            components_found = 0
            if api.miniscope_data_manager.CNMFE_obj is not None:
                if hasattr(api.miniscope_data_manager.CNMFE_obj, 'estimates'):
                    if hasattr(api.miniscope_data_manager.CNMFE_obj.estimates, 'A'):
                        components_found = api.miniscope_data_manager.CNMFE_obj.estimates.A.shape[1]
            
            print(f"Initial components found: {components_found}")
            
            try:
                components_deleted = int(input(
                f"\nCNMF-E found {components_found} components.\n"
                f"How many did you delete in the GUI? "
            ))
            except: 
                components_deleted < 0
                
            # Move results to test subdirectory
            self._organize_results(api.miniscope_data_manager, test_subdir)
            
            # Calculate deletion metrics
            final_components = components_found - components_deleted
            components_deleted = max(0, components_found - final_components)
            deletion_rate = (components_deleted / components_found) if components_found > 0 else 0.0
            
            # Create complete test result
            test_result = {
                'experiment_id': experiment_id,
                'parameter_name': parameter_name,
                'parameter_value': parameter_value,
                'components_found': components_found,
                'components_deleted': components_deleted,
                'final_components': final_components,
                'deletion_rate': round(deletion_rate, 2),
                'output_dir': test_subdir,
                'timestamp': datetime.now().isoformat()
            }
            
            # Save individual test info
            with open(os.path.join(test_subdir, 'test_info.json'), 'w') as f:
                json.dump(test_result, f, indent=2)
            print(f"Test completed!")
            return test_result
            
        except Exception as e:
            print(f"Error during test execution: {e}")
            test_result = {
                'experiment_id': experiment_id,
                'parameter_name': parameter_name,
                'parameter_value': parameter_value,
                'components_found': 0,
                'components_deleted': 0,
                'final_components': 0,
                'deletion_rate': 0.0,
                'output_dir': test_subdir,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            return test_result
            
        finally:
            # Restore original ANALYSIS_PARAMS path
            paths_module.ANALYSIS_PARAMS = original_params_path
            
            # Clean up temporary file
            if os.path.exists(temp_params_file):
                os.remove(temp_params_file)
    
    def _count_final_components_from_api(self, api, test_result) -> int:

        try:
            if api.miniscope_data_manager.CNMFE_obj is not None:
                if hasattr(api.miniscope_data_manager.CNMFE_obj, 'estimates'):
                    if hasattr(api.miniscope_data_manager.CNMFE_obj.estimates, 'A'):
                        return api.miniscope_data_manager.CNMFE_obj.estimates.A.shape[1]
            return 0
        except Exception as e:
            print(f"Warning: Could not count final components from API: {e}")
            return 0
    
    def run_interactive_parameter_test_suite(self, test_result, experiment_id: int, parameter_name: str, test_values: List[Union[float, int]], filenames: List[str] = None) -> List[Dict]:

        print(f"\nStarting INTERACTIVE parameter test suite for {parameter_name}")
        print(f"Testing {len(test_values)} values: {test_values}")

        
        # Setup test directory
        self.setup_test_directory(experiment_id, parameter_name)
        
        all_results = []
        
        for i, value in enumerate(test_values):
            print(f"\n{'='*80}")
            print(f"PROGRESS: {i+1}/{len(test_values)} - Testing {parameter_name} = {value}")
            print(f"{'='*80}")
            
            # Wait for user confirmation to proceed
            input(f"\nPress Enter to start test {i+1}/{len(test_values)} ({parameter_name} = {value})...")
            
            # Run single test with interactive editing
            test_result = self.run_single_test_with_editing(
                experiment_id, parameter_name, value, filenames
            )
            
            # Add to results
            all_results.append(test_result)
            self.results_data.append(test_result)
            
            # Update and save results CSV after each test
            self._save_results_csv(test_result)
            
            # Show current progress
            print(f"\n{'='*60}")
            print(f"COMPLETED TEST {i+1}/{len(test_values)}")
            print(f"Parameter: {parameter_name} = {value}")
            print(f"Deletion rate: {test_result['deletion_rate']:.1f}%")
            print(f"{'='*60}")
            
            # Ask if user wants to continue (except for last test)
            if i < len(test_values) - 1:
                continue_test = input(f"\nContinue to next test? (y/n): ").lower().strip()
                if continue_test.startswith('n'):
                    print("Test suite stopped by user.")
                    break
        
        # Generate final summary
        self._generate_summary_stats(test_result)
        
        print(f"\n{'='*80}")
        print(f"PARAMETER TEST SUITE COMPLETED!")
        print(f"{'='*80}")
        print(f"Parameter tested: {parameter_name}")
        print(f"Tests completed: {len(all_results)}")
        print(f"Results saved in: {self.test_dir}")
        
        # Show quick summary of results
        if all_results:
            best_result = min(all_results, key=lambda x: x['deletion_rate'])
            print(f"\nBest result:")
            print(f"  {parameter_name} = {best_result['parameter_value']}")
           
        
        return all_results
    
    def _save_results_csv(self, test_result) -> str:
        """
        Save results to CSV file.
        
        Returns:
            str: Path to saved CSV file
        """
        if not self.results_data:
            return ""
        
        csv_path = os.path.join(self.test_dir, 'results_comparison.csv')
        
        fieldnames = [
            'experiment_id', 'parameter_name', 'parameter_value', 
            'components_found', 'components_deleted', 'final_components', 
            'deletion_rate', 'output_dir'
        ]

        
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results_data:
                # Only include relevant fields
                row = {field: result.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        print(f"Results updated in: {csv_path}")
        return csv_path
    
    def _generate_summary_stats(self, test_result):
        """Generate and save summary statistics."""
        if not self.results_data:
            return
        
        # Calculate summary statistics
        df = pd.DataFrame(self.results_data)
        
        summary_stats = {
            'total_tests': len(df),
            'parameter_tested': df['parameter_name'].iloc[0] if len(df) > 0 else 'N/A',
            'experiment_id': df['experiment_id'].iloc[0] if len(df) > 0 else 'N/A',
            'avg_components_found': df['components_found'].mean(),
            'avg_deletion_rate': df['deletion_rate'].mean(),
            'best_parameter_value': None,
            'best_deletion_rate': None
        }
        
        if len(df) > 0 and 'deletion_rate' in df.columns:
            # Find parameter value with lowest deletion rate
            best_idx = df['deletion_rate'].idxmin()
            summary_stats['best_parameter_value'] = df.loc[best_idx, 'parameter_value']
            summary_stats['best_deletion_rate'] = df.loc[best_idx, 'deletion_rate']
        
        # Save summary
        summary_path = os.path.join(self.test_dir, 'summary_stats.json')
        with open(summary_path, 'w') as f:
            json.dump(summary_stats, f, indent=2, default=str)
        
        print("\nSUMMARY STATISTICS:")
        print(f"Parameter tested: {summary_stats['parameter_tested']}")
        print(f"Average components found: {summary_stats['avg_components_found']:.1f}")
        print(f"Average deletion rate: {summary_stats['avg_deletion_rate']:.1f}%")
        if summary_stats['best_parameter_value'] is not None:
            print(f"Best parameter value: {summary_stats['best_parameter_value']} "
                  f"(deletion rate: {summary_stats['best_deletion_rate']:.1f}%)")
        
        return summary_stats


def main(test_result):
   
    # MANUAL CONFIGURATION - EDIT THESE VALUES
    
    # 1. Base output directory for test results
    base_output_dir = "C:/miniscope_parameter_tests"  # MODIFY THIS PATH
    
    # 2. Experiment configuration
    experiment_id = 97  # ROW NUMBER from analysis_parameters.csv (1-based)
    parameter_name = "gSig"  # PARAMETER NAME to test (must match CSV column)
    
    # 3. Test value generation method and settings
    value_generation_method = "manual"  
    
    custom_values = [(7,7)]
    

    # 4. Movie filenames to analyze
    filenames = ['0.avi']  
    
    # END MANUAL CONFIGURATION
    
    try:
        print("="*80)
        print("CNMF-E PARAMETER TESTER - INTERACTIVE MODE")
        print("="*80)
        
        # Create tester instance
        tester = CNMFEParameterTester(base_output_dir)
        
        # Validate inputs
        if experiment_id < 1 or experiment_id > len(tester.analysis_params_df):
            raise ValueError(f"Invalid experiment_id {experiment_id}. Must be 1-{len(tester.analysis_params_df)}")
        
        if parameter_name not in tester.analysis_params_df.columns:
            available_params = [col for col in tester.analysis_params_df.columns 
                              if col not in ['experiment_id', 'calcium imaging directory']]
            raise ValueError(f"Invalid parameter_name '{parameter_name}'. Available: {available_params}")
        
        # Get baseline value
        baseline_value = tester.analysis_params_df.iloc[experiment_id - 1][parameter_name]
        
        print("Configuration:")
        print(f"  Experiment ID: {experiment_id}")
        print(f"  Parameter: {parameter_name}")
        print(f"  Baseline value: {baseline_value}")
        
        # Generate test values based on method
        if value_generation_method == "manual":
            test_values = custom_values
        
        print(f"  Test values: {test_values}")
        print(f"  Movie files: {filenames}")
        
        # Confirmation
        print(f"\n{'='*60}")
        print("READY TO START PARAMETER TESTING")
        print(f"{'='*60}")
        print(f"This will run {len(test_values)} tests sequentially.")

        
        # Run the interactive test suite
        results = tester.run_interactive_parameter_test_suite(
            test_result=test_result,
            experiment_id=experiment_id,
            parameter_name=parameter_name,
            test_values=test_values,
            filenames=filenames
        )
        
        print(f"\n{'='*80}")
        print(f"ALL TESTS COMPLETED SUCCESSFULLY!")
        print(f"{'='*80}")
        print(f"Results saved in: {tester.test_dir}")

        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main(test_result=None)
