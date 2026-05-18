
import pandas as pd
import os
from pathlib import Path
from aceneurotools.shared.csv_worker import CSVWorker

def test_csv_worker(csv_file, line_num):
    try:
        res = CSVWorker.csv_row_to_dict(csv_file, line_num)
        return res
    except ValueError as e:
        print(f"Caught expected error: {e}")
        return None

# Test case 1: Normal
with open("test_repro.csv", "w") as f:
    f.write("line number,id\n97,subject1\n98,subject2\n")

print("Test 1 (Normal):")
print(test_csv_worker("test_repro.csv", 97))

# Test case 2: Spaces in values
with open("test_repro_spaces.csv", "w") as f:
    f.write("line number,id\n 97 ,subject1\n98,subject2\n")

print("\nTest 2 (Spaces in values):")
print(test_csv_worker("test_repro_spaces.csv", 97))

# Test case 3: Spaces in header
with open("test_repro_header_space.csv", "w") as f:
    f.write("line number ,id\n97,subject1\n98,subject2\n")

print("\nTest 3 (Spaces in header):")
print(test_csv_worker("test_repro_header_space.csv", 97))

os.remove("test_repro.csv")
os.remove("test_repro_spaces.csv")
os.remove("test_repro_header_space.csv")
