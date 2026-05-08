import pandas as pd
import ast
from datetime import datetime
import json
from typing import Dict, Any, Optional, Union, List
from pathlib import Path

class CSVWorker:
    """Utility class for reading and parsing experiment CSV files.
    
    Provides static methods to load rows from CSV files and convert
    string values to appropriate Python data types.
    """

    @staticmethod
    def csv_row_to_dict(csv_file: Union[str, Path], line_num: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Load a single row from a CSV file as a dictionary.
        
        Args:
            csv_file: Path to the CSV file.
            line_num: Line number to extract (matched against 'line number' column).
            
        Returns:
            Dict mapping column names to cell values, or None on error.
        
        Raises:
            ValueError: If the CSV is malformed or the line number is not found.
        """
        import csv as csv_mod
        from typing import cast
        
        path_obj = Path(csv_file)
        
        # Validate CSV structure before pandas reads it.
        try:
            with open(path_obj) as f:
                reader = csv_mod.reader(f)
                header = next(reader)
                for row_num, data_row in enumerate(reader, start=2):
                    if not any(data_row):  # skip empty rows
                        continue
                    if len(data_row) != len(header):
                        raise ValueError(
                            f"CSV malformed: '{csv_file}' row {row_num} has "
                            f"{len(data_row)} fields but the header has {len(header)} columns. "
                            f"This usually means there is a trailing comma or an unquoted "
                            f"comma inside a value (e.g., coordinate tuples must be "
                            f"quoted: \"(x0, y0, x1, y1)\")."
                        )
        except FileNotFoundError:
            print(f"File {csv_file} not found")
            return None
        
        try:
            df = pd.read_csv(path_obj)
            line_num_str = str(line_num)
            row = df.loc[df['line number'].astype(str) == line_num_str]
            if row.empty:
                raise ValueError(f"Line number {line_num} (as string: '{line_num_str}') not found")
            res = row.squeeze()
            if hasattr(res, 'to_dict'):
                return cast(Dict[str, Any], res.to_dict())
            return None
        except FileNotFoundError:
            print(f"File {csv_file} not found")
            return None
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            print(f"Error parsing CSV: {e}")
            return None


    @staticmethod
    def convert_data_types(params_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert string values in a dict to appropriate Python types.
        
        Handles lists, tuples, booleans, floats, dates, and None values.
        
        Args:
            params_dict: Dictionary with string values from CSV.
            
        Returns:
            Dict with values converted to appropriate types.
        """
        non_numeric_keys = ['id', 'calcium imaging directory', 'ephys directory',
                           'method_deconvolution', 'method_init', 'border_nan', 'LFP and EEG CSCs']
        converted_params: Dict[str, Any] = {}
        
        for key, value in params_dict.items():
            if key in non_numeric_keys:
                if key == 'LFP and EEG CSCs':
                    converted_params[key] = str(params_dict[key]).split(";")
                    continue
                converted_params[key] = value
                continue
            
            converted_value = CSVWorker._convert_value(value, key)
            converted_params[key] = converted_value
    
        return converted_params

    @staticmethod
    def _convert_value(raw_value: Any, key: str) -> Any:
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
            return CSVWorker._convert_date(raw_value)

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
        except (json.JSONDecodeError, AttributeError):
            pass

        # Attempt Python literal evaluation
        try:
            return ast.literal_eval(processed_value)
        except (ValueError, SyntaxError):
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
        except ValueError:
            return raw_value
        

    @staticmethod
    def _convert_date(date_str: Any) -> Union[datetime, Any]:
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
            if not isinstance(date_str, str):
                date_str = str(date_str)
            return datetime.strptime(date_str, '%y%m%d')
        except ValueError:
            return date_str