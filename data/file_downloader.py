from box_credentials import dev_token, BASE_FILE_PATH, auth
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth, BoxCCGAuth
from os import path as os_path, makedirs
import sys
from pathlib import Path
import pandas as pd

"""TO DO:  
    - Add box folder IDs to all CSVs so filereader can download it.
    - Work with teammates to develop standardized nomenclature and use of this file.
    - rewrite to use pathlib instead of os.path
    - Make Authorization permanant using Client Credentials Grant
    - Add command line compatibility
    - Maybe Modularize as a class?
"""
        
client = None

PROJECT_ROOT = Path(__file__).parent.parent




def verify_args(args):
    """This function verifies command line arguments to run the code
        -d: Downloads ephys or miniscope files: py filedownloader.py -d [row number, csv path, "ephys" or "miniscope"]
        -db: Downloads both ephys and miniscope files: py filedownloader.py -db [row number, csv path]
        -h: Help, prints out a help menu
    
    """
    if len(args) == 5 and args[1] == '-d':
        verify_file_by_line(args[2],args[3],args[4])
    elif len(args) == 4 and args[1] == '-db':
        verify_file_by_line(args[2],args[3])
    pass


def verify_path(path: str):
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    if os_path.exists(f"{BASE_FILE_PATH}/{path}"): # If we already have the folder, then we don't need to download anything
        return True # NOTE: This will still return True even if the downloads are incomplete or the folder is empty
    else:
        makedirs(f"{BASE_FILE_PATH}/{path}") # Makes a folder for our downloads
        return False
    

def verify_file_by_line(row, csv_path: str, do_type="both"):
    """Checks the path where the file should be.
    Finds the path from the CSV row given and checks if it exists in our downloaded data
    If a folder doesn't exist, break the search and call download_file(path, ID) to download and store the file
    """
    # Verify the arguments
    row = str(row)
    if not do_type in ["both", "miniscope", "ephys"]:
        raise ValueError("variable 'do_type' must be 'y', 'miniscope', or 'ephys' in order to work")
    
    
    print("Getting path and ID from CSV")
    try:
        df = pd.read_csv(csv_path, index_col="line number")
        print(f"Loaded CSV: {csv_path}")
    except Exception as e:
        print(e)
        return False
    row = str(row)
    miniscope_id = df.at[row, "Box Calcium Folder ID"]
    miniscope_path = df.at[row, "calcium imaging directory"]
    ephys_id = df.at[row, "Box ephys folder ID"]
    ephys_path = df.at[row, "ephys directory"]
    
    if do_type in ["both", "miniscope"]:
        if pd.isnull(miniscope_path) or pd.isnull(miniscope_id):
            print("The miniscope path or ID do not exist in the CSV file, cannot download")
        elif not verify_path(miniscope_path):
            download_file(miniscope_path,int(miniscope_id))
    if do_type in ["both", "ephys"]:   
        if pd.isnull(ephys_path) or pd.isnull(ephys_id):
            print("The ephys path or ID do not exist in the CSV file, cannot download") 
        if not verify_path(ephys_path):
            download_file(ephys_path,int(ephys_id))


    
   
    
    
    

# _________________Below is the all the auth and sdk code_________________
    
def make_auth():
    # auth = BoxDeveloperTokenAuth(token=dev_token)
    try:
        client = BoxClient(auth=auth)
        print("Successfully connected to Box client")
        return client
    except Exception as e:
        print(e)




def download_file(path: str, ID):
    """Called from verify_file or run manually to download a file from box and store it in a standard path
    """
    client = make_auth()
    
    try:
        for item in client.folders.get_folder_items(ID).entries: #Goes to the folder we want to download
            print(item.name) # Debug print statement to know what item we're currently looking at
            if item.type == 'folder': # Additional code to recursively call download_file if our folder contains subfolders
                print(f"Found a folder: {item.name}")
                makedirs(f"{BASE_FILE_PATH}/{path}/{item.name}") # Makes new directory for sub folder
                download_file(path=f"{path}/{item.name}", ID=item.id)
                continue # Returns to the start of the loop to avoid an error
        
            with open(f"{BASE_FILE_PATH}/{path}/{item.name}", "wb") as output_file: # Creates a file to store the data
                client.downloads.download_file_to_output_stream(item.id, output_stream=output_file) # Downloads data to the file
                print(f"File '{item.name}' downloaded successfully to '{BASE_FILE_PATH}/{path}/{item.name}'") # Prints that we've successfully downloaded a file. Line won't run if there's an error

        return True # Returns True once everthing is downloaded
    except Exception as e: #Catches any error
        print(e) # Prints the error to the terminal
        return False


if __name__ == '__main__': #Main function, mainly for testing.
    # client = make_auth()
    if len(sys.argv) > 1:
        verify_args(sys.argv)
    verify_file_by_line(23,PROJECT_ROOT / "data" / "experiments.csv")