import ast
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# CSV column schema constants
# ---------------------------------------------------------------------------

# Columns that must remain as plain strings (no numeric coercion).
# Extend via the ``extra_string_columns`` parameter to :meth:`CSVWorker.convert_data_types`
# rather than by modifying this set — that keeps schema evolution localised
# to the call site without touching shared code.
STRING_COLUMNS: frozenset = frozenset({
    'id',
    'calcium imaging directory',
    'ephys directory',
    'method_deconvolution',
    'method_init',
    'border_nan',
    'comments',
})

# Columns whose string value should be split on ';' to produce a list.
SEMICOLON_LIST_COLUMNS: frozenset = frozenset({
    'LFP and EEG CSCs',
})


class CSVWorker:
    """Utility class for reading and parsing experiment CSV files.
    
    Provides static methods to load rows from CSV files and convert
    string values to appropriate Python data types.
    """

    @staticmethod
    def csv_row_to_dict(csv_file: str | Path, line_num: int | str) -> dict[str, Any] | None:
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
                try:
                    header = next(reader)
                except StopIteration:
                    return None  # empty file
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

            # Check for the required 'line number' column before querying.
            if 'line number' not in df.columns:
                available = list(df.columns)
                raise ValueError(
                    f"Required column 'line number' not found in {csv_file}.\n"
                    f"  Your CSV has columns: {available}\n"
                    "  ACE-NeuroTools expects exact column names.  Run\n"
                    "    python -m aceneurotools.init --project-path <dir>\n"
                    "  to generate an experiments_template.csv showing all "
                    "required column headers."
                )

            line_num_int = int(line_num)
            # Use numeric comparison to be robust against pandas auto-converting to float (e.g. 97 vs 97.0)
            row = df.loc[pd.to_numeric(df['line number'], errors='coerce') == line_num_int]
            if row.empty:
                raise ValueError(
                    f"Subject line number {line_num} not found in {csv_file}.\n"
                    "  Check that the 'line number' column contains this value."
                )
            res = row.squeeze()
            if hasattr(res, 'to_dict'):
                return cast(dict[str, Any], res.to_dict())
            return None
        except FileNotFoundError:
            print(
                f"experiments.csv not found: {csv_file}\n"
                "  Ensure --project-path points to the directory containing "
                "experiments.csv."
            )
            return None
        except (pd.errors.EmptyDataError, pd.errors.ParserError) as e:
            print(f"Error parsing CSV {csv_file}: {e}")
            return None


    @staticmethod
    def convert_data_types(
        params_dict: dict[str, Any],
        extra_string_columns: frozenset | None = None,
        extra_list_columns: frozenset | None = None,
    ) -> dict[str, Any]:
        """Convert string values in a dict to appropriate Python types.

        Handles lists, tuples, booleans, floats, dates, and None values.
        Columns in :data:`STRING_COLUMNS` are kept as plain strings.
        Columns in :data:`SEMICOLON_LIST_COLUMNS` are split on ``';'`` to
        produce a list.

        The built-in column sets can be extended without modifying source code
        by passing *extra_string_columns* or *extra_list_columns*.  This
        enables callers to register additional schema-specific columns that
        should bypass numeric coercion.

        Args:
            params_dict: Dictionary with string values from CSV.
            extra_string_columns: Optional :class:`frozenset` of additional
                column names that must remain as plain strings.  Merged with
                :data:`STRING_COLUMNS` at call time.
            extra_list_columns: Optional :class:`frozenset` of additional
                column names whose values should be split on ``';'`` to
                produce a list.  Merged with :data:`SEMICOLON_LIST_COLUMNS`.

        Returns:
            Dict with values converted to appropriate types.
        """
        string_cols = STRING_COLUMNS | (extra_string_columns or frozenset())
        list_cols = SEMICOLON_LIST_COLUMNS | (extra_list_columns or frozenset())

        converted_params: dict[str, Any] = {}

        for key, value in params_dict.items():
            if key in list_cols:
                converted_params[key] = str(value).split(";")
                continue

            if key in string_cols:
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
    def _convert_date(date_str: Any) -> datetime | Any:
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
