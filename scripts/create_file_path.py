#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 26 22:23:35 2024

@author: lukerichards
"""

import os

# Specify the full file path
file_path = "/Users/lukerichards/Desktop/K99/Neuralynx_data/R220817B/2022-11-28_14-15-03/data.txt"

# Extract the directory path
directory = os.path.dirname(file_path)

# Create the directories if they don't exist
os.makedirs(directory, exist_ok=True)

# Create the file
with open(file_path, 'w') as file:
    file.write("")  # You can add initial content here if needed

print(f"File created at: {file_path}")
