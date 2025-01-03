#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Dec 31 19:46:20 2024

@author: lukerichards
"""

from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth

TOKEN = 'KBsGhORE4MhcUXLx8RSNeIQjHcTocPQH'
FILE_PATH = 'K99/Neuralynx_data/R230706A/2023-12-07_14-32-11/EPFCLFPvsCBEEG.ncs' # Replace with the actual file path in Box
DOWNLOAD_PATH = '/Users/lukerichards/Desktop/notes.nev'  # Replace with the desired local path








"""
Download a specific file from Box using its file path.

Args:
    token (str): The developer token for authentication.
    file_path (str): The full path to the file in Box (e.g., "Folder/Subfolder/File.txt").
    download_path (str): The local path where the file should be saved.
"""

token = TOKEN
file_path = FILE_PATH
download_path = DOWNLOAD_PATH

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

print(f"File '{file_name}' downloaded successfully to '{download_path}'.")

