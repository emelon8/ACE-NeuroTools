#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 31 19:46:20 2024

@author: lukerichards
"""

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from pathlib import Path
import csv
import os
import sys

# Add the project root to sys.path for imports to work
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

data = {
    "sleep": [37,38,83,90,92,35],
    "dexmedetomidine": [46,47,101,97,64,88],
    "isoflurane": [104,105,107,108]
}

lines = [35, 38, 83, 90, 92, 101, 64, 88, 104, 105, 107, 108]

# I'm on 88 ephys

TOKEN = 'e6W33ZuqCS6Wub4n7cArRSdoWojCXZ8A'



def returnExperimentDictionary(lineNum):

    # Dynamically locate the project root
    project_root = Path(__file__).resolve().parent.parent

    # Resolve the full path to the file
    full_path = project_root / 'data/experiments.csv'

    # Check if the file exists
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {full_path}")
    
    print('Reading experiment details from ' + str(full_path) + '...')
    experimentCSV = []
    with open(full_path, newline='') as s:
        reader = csv.reader(s)
        for row in reader:
            experimentCSV.append(row)
    
    # Make a dictionary with each of the columns in the CSV file
    experiment = {}
    for k, columnTitle in enumerate(experimentCSV[0]):
        try:
            experiment[columnTitle] = experimentCSV[lineNum][k]
        except:
            break

    return experiment


def downloadFile(token, file_path, download_path):
    
    # Authenticate the client
    auth = BoxDeveloperTokenAuth(token=token)
    client = BoxClient(auth=auth)
    
    # Split the file path into folder and file components
    path_parts = file_path.strip("/").split("/")
    folder_id = '0'  # Root folder ID
    
    # Traverse folders to locate the file
    for part in path_parts[:-1]:  # Exclude the last part (the file name)
        folder = next(
            (item for item in client.folders.get_folder_items(folder_id).entries if item.name == part and item.type == 'folder'),
            None
        )
        if not folder:
            raise FileNotFoundError(f"Folder '{part}' not found in path '{file_path}'.")
        folder_id = folder.id
    
    # Find the file ID in the last folder
    file_name = path_parts[-1]
    
    # print
    folder_items = client.folders.get_folder_items(folder_id).entries
    
    # Print the names of all files in the directory
    print("Files in the directory:")
    for item in folder_items:
        if item.type == 'file':
            print(item.name)
    
    
    
    
    file = next(
        (item for item in client.folders.get_folder_items(folder_id).entries if item.name == file_name and item.type == 'file'),
        None
    )
    if not file:
        raise FileNotFoundError(f"File '{file_name}' not found in path '{file_path}'.")
    
    # Download the file content using its ID
    file_content = client.downloads.download_file(file.id).read()
    
    # Write the file content to the specified local path
    with open(download_path, 'wb') as f:
        f.write(file_content)
        
def get_ephys_directory(line_num):
    expDict = returnExperimentDictionary(line_num)
    return expDict['ephys directory']

    
def make_file(file_name):
    # Extract the directory path
    directory = os.path.dirname(file_name)
    
    # Create the directories if they don't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create the file
    with open(file_name, 'w') as file:
        file.write("")  # You can add initial content here if needed
        
        
def cut_path(file_path, root="K99"):
    # Split the path and retain only the part starting with the root
    if root in file_path:
        _, _, trimmed_path = file_path.partition(root)
        return os.path.join(root, trimmed_path.lstrip(os.sep))
    else:
        raise ValueError(f"The root '{root}' not found in the file path.")



if __name__ == "__main__":
    
    for line_num in lines:
        ephys_directory = get_ephys_directory(line_num)
        
        events_path = ephys_directory + "/Events.nev"
        channel_path = ephys_directory = "/PFCLFPvsCBEEG.ncs"
        
        make_file(events_path)
        make_file(channel_path)
        
        box_events_path = cut_path(events_path)
        box_channel_path = cut_path(channel_path)
        
        downloadFile(TOKEN, box_events_path, events_path)
        downloadFile(TOKEN, box_channel_path, channel_path)

        

    print(f"File downloaded successfully.")

