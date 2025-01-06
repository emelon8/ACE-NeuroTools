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
    """
    Download a file from Box and save it to the specified path.

    Args:
        token (str): Box developer token.
        file_path (str): Path of the file on Box.
        download_path (str): Local path to save the file.
    """
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

    # Print the names of all files in the directory
    folder_items = client.folders.get_folder_items(folder_id).entries
    print("Files in the directory:")
    for item in folder_items:
        if item.type == 'file':
            print(item.name)

    file = next(
        (item for item in folder_items if item.name == file_name and item.type == 'file'),
        None
    )
    if not file:
        raise FileNotFoundError(f"File '{file_name}' not found in path '{file_path}'.")

    # Download the file content using its ID
    print(f"Downloading file: {file.name}")
    with open(download_path, 'wb') as f:
        client.downloads.download_file_to_output_stream(file.id, f)

    print(f"File saved to {download_path}")



        
def get_ephys_directory(line_num):
    expDict = returnExperimentDictionary(line_num)
    return expDict['calcium imaging directory']

    
def make_file(file_name):
    # Extract the directory path
    directory = os.path.dirname(file_name)
    
    # Create the directories if they don't exist
    os.makedirs(directory, exist_ok=True)
    
    # Create the file
    #with open(file_name, 'w') as file:
     #   file.write("")  # You can add initial content here if needed
        
        
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

        # File paths
        events_path = os.path.join(ephys_directory, "/Miniscope/metaData.json")
        channel_path = os.path.join(ephys_directory, "/Miniscope/timeStamps.csv")
        last = os.path.join(ephys_directory, "metaData.json")
        
        #make_file(events_path)
        make_file(channel_path)
        #make_file(last)


    print("Files downloaded successfully.")


