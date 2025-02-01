import numpy as np
import pandas as pd
from src2.paths import ANALYSIS_PARAMS, EXPERIMENTS
import logging
import ast
from datetime import datetime
import pickle
import os

# Configure logging.   Change "CRITIAL" to "INFO" to see most useful things
logging.basicConfig(level=logging.CRITICAL, format="%(asctime)s - %(levelname)s - %(message)s")

class DataManager:
    """
    Handles data loading, saving, and validation.
    """
    def __init__ (self, line_num):
        self.line_num=line_num
    
    def import_metadata(self):
        
        meta_data_unconverted = self.csv_row_to_dict(EXPERIMENTS, self.line_num) 
        meta_data_converted = self.convert_data_types(meta_data_unconverted)
        self.meta_data = meta_data_converted
        
    def import_analysis_parameters(self):
        analysis_params_uncoverted = self.csv_row_to_dict(ANALYSIS_PARAMS, self.line_num)
        meta_data_converted = self.convert_data_types(analysis_params_uncoverted)
        self.analysis_params = meta_data_converted
        
        
    
    
    def csv_row_to_dict(self, csv_file, line_num):
        try:
            df = pd.read_csv(csv_file)
            
            # Convert the input line_num to a string (to match the CSV column)
            line_num_str = str(line_num)
            
            # Grab corresponding row
            row = df.loc[df['line number'] == line_num_str]  
            
            if row.empty:
                raise ValueError(f"Line number {line_num} (as string: '{line_num_str}') not found")
            
            return row.squeeze().to_dict()
        
        except FileNotFoundError:
            print(f"File {csv_file} not found")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
        
    
    
    def convert_data_types(self, params_dict):
        """Convert string values to appropriate data types in parameters dictionary."""
        converted_params = {}
        
        for key, value in params_dict.items():
            try:
                # Handle special cases first
                if key == 'date (YYMMDD)':
                    converted_params[key] = datetime.strptime(str(value), '%y%m%d')
                    continue
    
                # General type conversion pipeline
                try:
                    # Attempt Python literal evaluation
                    converted = ast.literal_eval(str(value))
                except (ValueError, SyntaxError):
                    # Handle special string cases
                    lower_val = str(value).lower()
                    if lower_val in {'true', 'false'}:
                        converted = lower_val == 'true'
                    elif str(value).strip() in {'', 'None', 'nan'}:
                        converted = None
                    elif str(value).startswith('('):
                        # Tuple conversion (matching old behavior)
                        converted = tuple(
                            int(x) for x in 
                            str(value).strip('()').split(',') 
                            if x.strip().isdigit()
                        )
                    else:
                        # Final fallback to float
                        converted = float(value)
                else:
                    # Use literal_eval result if successful
                    converted = converted
    
                converted_params[key] = converted
    
            except Exception as e:
                print(f"Type conversion failed for {key}={value}: {str(e)}")
                converted_params[key] = None  # Fallback to None
    
        return converted_params
        
    
    


    def save_obj(self, filename=None, *, include_job_id=False, include_subject_id=False, include_timestamp=False):
        """Save the class instance to a pickled file with dynamic naming."""
        
        # make a name for the file
        if filename is None:
            # Build filename components using list comprehension
            components = []
            if include_subject_id:
                components.append(str(self.experiment['id']))
            
            # Add class name 
            components.append(self.__class__.__name__)
            
            # Add timestamp if needed
            if include_timestamp:
                components.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
            
            # Construct filename with safe separator
            filename = "_".join(components) + ".pickle"
    
        # Use context manager for automatic file handling
        with open(filename, 'wb') as file:
            pickle.dump(self, file)
            
            
            
            
        