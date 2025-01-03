#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 26 22:23:35 2024

@author: lukerichards
"""

import os

MINISCOPE_PATH = '/Users/lukerichards/Desktop/K99/miniscope_data/dexmedetomidine/R230706B/2023_09_08/15_15_12'
EPHYS_PATH = '/Users/lukerichards/Desktop/K99/Neuralynx_data/R230706B/2023-09-08_14-36-19'

# Specify the full file path
full_miniscope = MINISCOPE_PATH + "/Miniscope/Metadata_&_timestamps.txt"
full_ephys = EPHYS_PATH + "/Events_&_PFLCP.txt"


def make_file(file_name):
    # Extract the directory path
    directory = os.path.dirname(file_name)
    
    # Create the directories if they don't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create the file
    with open(file_name, 'w') as file:
        file.write("")  # You can add initial content here if needed

make_file(full_miniscope)
make_file(full_ephys)