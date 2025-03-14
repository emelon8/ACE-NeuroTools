#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import json
from datetime import datetime
from src2.shared.paths import ANALYSIS_PARAMS, EXPERIMENTS
import pickle
import pandas as pd
import ast
import json
import ast
from datetime import datetime


class DataManager:
    """
    This class manages the import and storage of metadata and analysis parameters.  Formerly the experiment class.

    metadata: a row, indexed by line_num of the experiments.csv document.  Each column is a key, and each cell is a value in the metadata dictionary.  Formerly self.experiment
    analysis_params: A similarly dictionary constructed dictionary, but with the corresponding row taken from analysis_parameters.csv.
    """



    def __init__(self, line_num, auto_import_metadata=True, auto_import_analysis_params=True):
        self.line_num = line_num
        self.metadata = None
        self.analysis_params = None

        if auto_import_metadata:
            self.import_metadata()

        if auto_import_analysis_params:
            self.import_analysis_parameters()

    def import_metadata(self):
        metadata_unconverted = self._csv_row_to_dict(EXPERIMENTS, self.line_num)
        metadata_converted = self._convert_data_types(metadata_unconverted)
        self.metadata = metadata_converted

    def import_analysis_parameters(self):
        # print(f"Looking for analysis params at: {Path(ANALYSIS_PARAMS).resolve()}")
        # print(f"File exists: {Path(ANALYSIS_PARAMS).exists()}")
        analysis_params_unconverted = self._csv_row_to_dict(ANALYSIS_PARAMS, self.line_num)
        analysis_params_converted = self._convert_data_types(analysis_params_unconverted)
        self.analysis_params = analysis_params_converted

    def save_obj(self, filename=None, *, include_job_id=False, include_subject_id=False, include_timestamp=False):
        if filename is None:
            components = []
            if include_subject_id:
                components.append(str(self.metadata['id']))
            components.append(self.__class__.__name__)
            if include_timestamp:
                components.append(datetime.now().strftime("%Y%m%d_%H%M%S"))
            filename = "_".join(components) + ".pickle"

        with open(filename, 'wb') as file:
            pickle.dump(self, file)












    # Private methods        

    def _csv_row_to_dict(self, csv_file, line_num):
        try:
            df = pd.read_csv(csv_file)
            line_num_str = str(line_num)
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


    def _convert_data_types(self, params_dict):
        non_numeric_keys = ['id', 'calcium imaging directory', 'ephys directory',
                           'method_deconvolution', 'method_init', 'border_nan', 'LFP and EEG CSCs']
        converted_params = {}
        
        for key, value in params_dict.items():
            if key in non_numeric_keys:
                converted_params[key] = value
                continue
            
            converted_value = self._convert_value(value, key)
            converted_params[key] = converted_value

        return converted_params

 
    def _convert_value(self, raw_value, key):
        """
        Converts a raw string value to its appropriate data type.
        """
        # NEW: Handle None
        if raw_value is None:
            return None

        # Check if the value is already a float
        if isinstance(raw_value, float):
            if pd.isna(raw_value): 
                return None
            else:
                return raw_value

        # Date conversion
        if key == 'date (YYMMDD)':
            return self._convert_date(raw_value)

        # Ensure raw_value is a string for further processing
        if not isinstance(raw_value, str):
            return raw_value

        # NEW: Preprocess tuple-like strings for JSON
        processed_value = raw_value.strip().replace(" ", "")
        if processed_value.startswith("(") and processed_value.endswith(")"):
            processed_value = f'[{processed_value[1:-1]}]'

        # Attempt JSON parsing
        try:
            return json.loads(processed_value)
        except (json.JSONDecodeError, AttributeError) as e:
            pass

        # Attempt Python literal evaluation
        try:
            return ast.literal_eval(processed_value)
        except (ValueError, SyntaxError) as e:
            pass

        # Check for boolean strings
        lower_val = raw_value.lower()
        if lower_val == 'true':
            return True
        elif lower_val == 'false':
            return False

        # Check for None/empty
        elif lower_val == 'none' or raw_value.strip() == '':
            return None

        # Attempt float conversion
        try:
            return float(raw_value)
        except ValueError as e:
            return raw_value
        

    def _convert_date(self, date_str):
        """
        Converts a date string in the format YYMMDD to a datetime object.
        
        Args:
            date_str: The date string or float to be converted.
        
        Returns:
            datetime: The converted datetime object, or the original value if conversion fails.
        """
        try:
            if isinstance(date_str, float):
                date_str = str(int(date_str))
            return datetime.strptime(date_str, '%y%m%d')
        except ValueError as e:
            return date_str
