from os import listdir, makedirs
from os import path as os_path
from pathlib import Path
from typing import Any

import pandas as pd

# Box cloud storage is optional.  If box_credentials.py or box-sdk-gen are not
# present, the module loads cleanly and USING_BOX defaults to False (assumes
# all data is already available locally).
try:
    from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth  # type: ignore[import]

    from aceneurotools.shared.box_credentials import auth, dev_token  # type: ignore[import]
    _BOX_AVAILABLE = True
except ImportError:
    _BOX_AVAILABLE = False

USING_BOX: bool = _BOX_AVAILABLE

def verify_avi(miniscope_path: str, avi: str, base_file_path: str | Path | None = None) -> bool:
    """Check if a specific AVI file exists in the Miniscope directory."""
    if base_file_path is None:
        raise ValueError("base_file_path is required.")
    return os_path.exists(f"{base_file_path}/{miniscope_path}/Miniscope/{avi}")

def verify_path(path: str, base_file_path: str | Path | None = None) -> bool:
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required.")
    base = base_file_path
    full_path = f"{base}/{path}"
    if os_path.exists(full_path): # If we already have the folder, then we don't need to download anything
        if not listdir(full_path):
            return False #If the folder is empty (i.e., the download connection failed), it will still return false so verify_file will download it.
        return True # This will  return True even if the downloads are incomplete
    else:
        makedirs(full_path) # Makes a folder for our downloads
        return False

def verify_file_by_line(
    line_num: int | str,
    csv_path: str | Path,
    do_type: str = "both",
    avi_list: list[str] = [],
    base_file_path: str | Path | None = None
) -> bool | None:
    """Finds the path from the CSV line_num given and checks if it exists in our 
    downloaded data. If a folder doesn't exist, it calls download_file().
    
    Args:
        line_num: The experiment line number.
        csv_path: Path to experiments.csv.
        do_type: 'both', 'miniscope', or 'ephys'.
        avi_list: Specific filenames to check/download.
        base_file_path: Base path for data storage. Required.
    """

    if  USING_BOX: # This code will run if you're using box to store your data.
        if base_file_path is None:
            raise ValueError("base_file_path is required for Box file verification.")
        # If not, you can rewrite this file to interface with your cloud storage of choice
        # Currently, if USING_BOX is False, we assume everthing is already stored locally, and the function will return None

        # Verify the arguments
        line_num_str: str = str(line_num)
        if do_type not in ["both", "miniscope", "ephys"]:
            raise ValueError("variable 'do_type' must be 'both', 'miniscope', or 'ephys' in order to work")

        # print("Getting path and ID from CSV")
        try:
            df = pd.read_csv(csv_path, index_col="line number") # Tries to read the CSV
            df.index = df.index.astype(str)  # Ensure consistent string-based index lookup
            print(f"Loaded CSV: {csv_path}")
        except (pd.errors.EmptyDataError, FileNotFoundError, pd.errors.ParserError):
            return False # Will return false if we can't read the CSV

        miniscope_id = df.at[line_num_str, "Box Calcium Folder ID"]
        miniscope_path = df.at[line_num_str, "calcium imaging directory"]
        ephys_id = df.at[line_num_str, "Box ephys folder ID"]
        ephys_path = df.at[line_num_str, "ephys directory"]

        downloaded_miniscope: bool = False
        downloaded_ephys: bool = False
        need_to_download: list[str] = [avi for avi in avi_list if not verify_avi(miniscope_path, avi, base_file_path=base_file_path)] # Makes a list of avi files we don't already have and need to download

        client: Any | None = None # Declaring client here, but only initializing it if we actually need to download something

        if do_type in ["both", "miniscope"]:
            if pd.isnull(miniscope_path) or pd.isnull(miniscope_id): # Checks if we have the data we need to perform the download
                print("The miniscope path or ID do not exist in the CSV file, cannot download") # DEBUG: Prints the error
            else:
                if not verify_path(miniscope_path, base_file_path=base_file_path): # Checks if we've already downloaded this folder
                    if not client: # Checks if we've established the client yet
                        client = make_auth() # Makes the client now that we need to download something, conserves API calls
                        if not client: # Return false if we have an error establishing the client and can't download our files
                            return False
                    downloaded_miniscope = download_file(client, miniscope_path, int(miniscope_id), need_to_download, base_file_path=base_file_path) # Updates download status for return statement
                elif need_to_download or avi_list == []: # If the folder already exists but we need specific avi files, or we want ALL files (avi_list=[]), re-check Box for any missing files
                    if not client: # Checks if we've established the client yet
                        client = make_auth() # Makes the client now that we need to download something, conserves API calls
                        if not client: # Return false if we have an error establishing the client and can't download our files
                            return False
                    downloaded_miniscope = download_file(client, miniscope_path, int(miniscope_id), need_to_download, base_file_path=base_file_path) # Updates download status for return statement
        if do_type in ["both", "ephys"]:
            if pd.isnull(ephys_path) or pd.isnull(ephys_id): # Checks if we have the data we need to perform the download
                print("The ephys path or ID do not exist in the CSV file, cannot download") # DEBUG: Prints the error
                pass
            elif not verify_path(ephys_path, base_file_path=base_file_path): # Checks if we've already downloaded this folder
                if not client: # Checks if we've established the client yet
                    client = make_auth() # Makes the client now that we need to download something, conserves API calls
                    if not client: # Return false if we have an error establishing the client and can't download our files
                        return False
                downloaded_ephys = download_file(client, ephys_path, int(ephys_id), base_file_path=base_file_path) # Updates download status for return statement

        # Final return statement logic
        if do_type == "both":
            return downloaded_miniscope and downloaded_ephys
        elif do_type == "miniscope":
            return downloaded_miniscope
        elif do_type == "ephys":
            return downloaded_ephys
        return False
    else:
        return None

def make_auth() -> Any | None:
    """Creates the box client object to connect to the box servers.
    When you are using this file normally, use CCGAuth
    * When you are debugging, use the box developer token since you'll be making more API calls and most box contracts will charge extra if you make too many api calls that aren't with dev tokens"""
    # auth = BoxDeveloperTokenAuth(token=dev_token) # UNCOMMENT THIS LINE TO TEMPORARILY OVERRIDE CCGAUTH WITH THE BOX DEVELOPER TOKEN
    try:
        client = BoxClient(auth=auth)
        print("Successfully connected to Box client")
        return client
    except Exception as e:
        print(e)
        return None

def download_file(
    client: Any,
    path: str,
    ID: int,
    need_to_download: list[str] = [],
    base_file_path: str | Path | None = None
) -> bool:
    """Connects to the client and tries to download everything in the folder and 
    child folders if they haven't already been downloaded.
    
    Args:
        client: BoxClient instance.
        path: Relative path within the data directory.
        ID: Box folder ID.
        need_to_download: Optional list of specific filenames to retrieve.
        base_file_path: Base path for data storage. Required.
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required for downloading files.")
    try:
        for item in client.folders.get_folder_items(str(ID)).entries: #Goes to the folder we want to download
            print(item.name) # Debug print statement to know what item we're currently looking at
            if item.type == 'folder': # Additional code to download any subfolders
                print(f"Found a folder: {item.name}") # DEBUG: Print statement that we found a folder
                if not os_path.exists(f"{base_file_path}/{path}/{item.name}"): # Checks if the subfolder already exists
                    makedirs(f"{base_file_path}/{path}/{item.name}") # Makes new directory for sub folder
                if item.name == "Miniscope": # Checks if the subfolder is miniscope
                    for sub_item in client.folders.get_folder_items(item.id).entries:  # Look at each item in the miniscope folder
                        if (sub_item.name in need_to_download or need_to_download == []) or "avi" not in sub_item.name: # If we need to download it or we're downloading everyting
                            filepath = f"{base_file_path}/{path}/Miniscope/{sub_item.name}"
                            if not os_path.exists(filepath): # Will only download a file if it doesn't already exist (Only applies if we're downloading everything)
                                with open(filepath, "wb") as output_file: # Creates a file to store the data
                                    client.downloads.download_file_to_output_stream(sub_item.id, output_stream=output_file) # Downloads data to the file
                                    print(f"File '{sub_item.name}' downloaded successfully to '{filepath}'") # DEBUG: Prints that we've successfully downloaded a file. Line won't run if there's an error
                else: # If for some reason we have a sub-folder that isn't the miniscope folder, we recursively call the function to download it.
                    download_file(client, f"{path}/{item.name}", int(item.id), need_to_download, base_file_path=base_file_path)

            else:
                filepath = f"{base_file_path}/{path}/{item.name}"
                if not os_path.exists(filepath): # Will only download a file if it doesn't already exist.
                    with open(filepath, "wb") as output_file: # Creates a file to store the data
                        client.downloads.download_file_to_output_stream(item.id, output_stream=output_file) # Downloads data to the file
                        print(f"File '{item.name}' downloaded successfully to '{filepath}'") # DEBUG: Prints that we've successfully downloaded a file. Line won't run if there's an error

        return True # Returns True once everthing is downloaded
    except Exception as e: #Catches any error
        print(f"Download failed: {e}")
        return False

if __name__ == '__main__': # Runs when we run the file.
    import argparse
    parser = argparse.ArgumentParser(description="Download experiment data from Box")
    parser.add_argument('--project-path', type=str, required=True,
                        help="Path to project directory (containing experiments.csv)")
    parser.add_argument('--data-path', type=str, required=True,
                        help="Base path for raw experimental data storage")
    parser.add_argument('--line-num', type=int, default=96,
                        help="Experiment line number")
    parser.add_argument('--do-type', type=str, default="miniscope",
                        choices=["both", "miniscope", "ephys"])
    args = parser.parse_args()

    experiments_csv = Path(args.project_path) / "experiments.csv"
    verify_file_by_line(
        line_num=args.line_num,
        csv_path=experiments_csv,
        do_type=args.do_type,
        avi_list=["0.avi"],
        base_file_path=args.data_path
    )
