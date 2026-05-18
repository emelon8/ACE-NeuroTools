
import pandas as pd
import os
from pathlib import Path
from typing import Any, cast

def csv_row_to_dict(csv_file: str | Path, line_num: int | str) -> dict[str, Any] | None:
    path_obj = Path(csv_file)
    try:
        df = pd.read_csv(path_obj)
        if 'line number' not in df.columns:
            print(f"Columns: {df.columns.tolist()}")
            return None

        line_num_int = int(line_num)
        # Use numeric comparison to be robust against pandas auto-converting to float (e.g. 97 vs 97.0)
        row = df.loc[pd.to_numeric(df['line number'], errors='coerce') == line_num_int]
        if row.empty:
            print(f"Row empty for {line_num}")
            return None
        res = row.squeeze()
        if hasattr(res, 'to_dict'):
            return cast(dict[str, Any], res.to_dict())
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# Test case 1: Normal
with open("test_repro.csv", "w") as f:
    f.write("line number,id\n97,subject1\n98,subject2\n")

print("Test 1 (Normal):")
print(csv_row_to_dict("test_repro.csv", 97))

# Test case 2: Spaces in values
with open("test_repro_spaces.csv", "w") as f:
    f.write("line number,id\n 97 ,subject1\n98,subject2\n")

print("\nTest 2 (Spaces in values):")
print(csv_row_to_dict("test_repro_spaces.csv", 97))

# Test case 3: Spaces in header
with open("test_repro_header_space.csv", "w") as f:
    f.write("line number ,id\n97,subject1\n98,subject2\n")

print("\nTest 3 (Spaces in header):")
print(csv_row_to_dict("test_repro_header_space.csv", 97))

# Test case 4: Mixed types (e.g. some strings in line number)
with open("test_repro_mixed.csv", "w") as f:
    f.write("line number,id\n97,subject1\n98,subject2\nNA,subject3\n")

print("\nTest 4 (Mixed types):")
print(csv_row_to_dict("test_repro_mixed.csv", 97))

os.remove("test_repro.csv")
os.remove("test_repro_spaces.csv")
os.remove("test_repro_header_space.csv")
os.remove("test_repro_mixed.csv")
