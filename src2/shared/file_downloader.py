from src2.shared.box_credentials import dev_token, auth
from src2.shared.paths import BASE_FILE_PATH, EXPERIMENTS
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from os import path as os_path, makedirs, listdir
import pandas as pd

USING_BOX = True # Disabling this disables all the downloading data and instead will simply return None since we assume if you're not using box everthing is downloaded locally



def verify_avi(miniscope_path:str,avi:str):
    """Check if a specific AVI file exists in the Miniscope directory."""
    return os_path.exists(f"{BASE_FILE_PATH}/{miniscope_path}/Miniscope/{avi}")



def verify_path(path: str):
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    if os_path.exists(f"{BASE_FILE_PATH}/{path}"): # If we already have the folder, then we don't need to download anything
        if not listdir(f"{BASE_FILE_PATH}/{path}"):
            return False #If the folder is empty (i.e., the download connection failed), it will still return false so verify_file will download it.
        return True # This will  return True even if the downloads are incomplete
    else:
        makedirs(f"{BASE_FILE_PATH}/{path}") # Makes a folder for our downloads
        return False
    

def verify_file_by_line(line_num, csv_path: str, do_type="both", avi_list=[]):
    """Checks the path where the file should be.
    Finds the path from the CSV line_num given and checks if it exists in our downloaded data
    If a folder doesn't exist, break the search and call download_file(path, ID) to download and store the file
    """
    
    if  USING_BOX: # This code will run if you're using box to store your data. 
        # If not, you can rewrite this file to interface with your cloud storage of choice
        # Currently, if USING_BOX is False, we assume everthing is already stored locally, and the function will return None

              
        # Verify the arguments
        line_num = str(line_num)
        if not do_type in ["both", "miniscope", "ephys"]:
            raise ValueError("variable 'do_type' must be 'both', 'miniscope', or 'ephys' in order to work")
        
        
        # print("Getting path and ID from CSV")
        try:
            df = pd.read_csv(csv_path, index_col="line number") # Tries to read the CSV
            df.index = df.index.astype(str)  # Ensure consistent string-based index lookup
            print(f"Loaded CSV: {csv_path}")
        except (pd.errors.EmptyDataError, FileNotFoundError, pd.errors.ParserError) as e:
            # print(e)
            return False # Will return false if we can't read the CSV
        
        line_num = str(line_num)
        miniscope_id = df.at[line_num, "Box Calcium Folder ID"]
        miniscope_path = df.at[line_num, "calcium imaging directory"]
        ephys_id = df.at[line_num, "Box ephys folder ID"]
        ephys_path = df.at[line_num, "ephys directory"]
        
        
        downloaded_miniscope, downloaded_ephys = False, False # Booleans to help us w/ our return statement at the end
        need_to_download = [avi for avi in avi_list if not verify_avi(miniscope_path, avi)] # Makes a list of avi files we don't already have and need to download
        
        client = None # Declaring client here, but only initializing it if we actually need to download something
        
        if do_type in ["both", "miniscope"]:
            if pd.isnull(miniscope_path) or pd.isnull(miniscope_id): # Checks if we have the data we need to perform the download
                print("The miniscope path or ID do not exist in the CSV file, cannot download") # DEBUG: Prints the error
            else:
                if not verify_path(miniscope_path): # Checks if we've already downloaded this folder
                    if not client: # Checks if we've established the client yet
                        client = make_auth() # Makes the client now that we need to download something, conserves API calls
                        if not client: # Return false if we have an error establishing the client and can't download our files
                            return False
                    downloaded_miniscope=download_file(client, miniscope_path,int(miniscope_id), need_to_download) # Updates download status for return statement
                elif need_to_download or avi_list == []: # If the folder already exists but we need specific avi files, or we want ALL files (avi_list=[]), re-check Box for any missing files
                    if not client: # Checks if we've established the client yet
                        client = make_auth() # Makes the client now that we need to download something, conserves API calls
                        if not client: # Return false if we have an error establishing the client and can't download our files
                            return False
                    downloaded_miniscope=download_file(client, miniscope_path,int(miniscope_id), need_to_download) # Updates download status for return statement
        if do_type in ["both", "ephys"]:   
            if pd.isnull(ephys_path) or pd.isnull(ephys_id): # Checks if we have the data we need to perform the download
                print("The ephys path or ID do not exist in the CSV file, cannot download") # DEBUG: Prints the error
                pass
            elif not verify_path(ephys_path): # Checks if we've already downloaded this folder
                if not client: # Checks if we've established the client yet
                    client = make_auth() # Makes the client now that we need to download something, conserves API calls
                    if not client: # Return false if we have an error establishing the client and can't download our files
                        return False  
                downloaded_ephys=download_file(client, ephys_path,int(ephys_id)) # Updates download status for return statement

        # Final return statement logic
        if do_type == "both":
            return downloaded_miniscope and downloaded_ephys
        elif do_type == "miniscope":
            return downloaded_miniscope
        elif do_type == "ephys":
            return downloaded_ephys
    else:
        return None
    

# _________________Below is the all the auth and sdk code for BOX_________________
    
def make_auth():
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


def download_file(client, path: str, ID, need_to_download =[]): 
    """Takes a client, a path, a folder ID and optionally a list of avi files to download.
    Connects to the client and tries to download everything in the folder and child folders if they haven't already been downloaded.
    If need_to_download is empty, it will download every avi file in the miniscope folder. Otherwise, it will only download the avi files listed. This does not apply to downloading from the ephys directory
    Feel free to modify this to match your lab's cloud storage system if it is different than ours."""
    try:
        for item in client.folders.get_folder_items(ID).entries: #Goes to the folder we want to download
            print(item.name) # Debug print statement to know what item we're currently looking at
            if item.type == 'folder': # Additional code to download any subfolders
                print(f"Found a folder: {item.name}") # DEBUG: Print statement that we found a folder
                if not os_path.exists(f"{BASE_FILE_PATH}/{path}/{item.name}"): # Checks if the subfolder already exists
                    makedirs(f"{BASE_FILE_PATH}/{path}/{item.name}") # Makes new directory for sub folder
                if item.name == "Miniscope": # Checks if the subfolder is miniscope
                    for sub_item in client.folders.get_folder_items(item.id).entries:  # Look at each item in the miniscope folder
                        if (sub_item.name in need_to_download or need_to_download == []) or "avi" not in sub_item.name: # If we need to download it or we're downloading everyting
                            if not os_path.exists(f"{BASE_FILE_PATH}/{path}/Miniscope/{sub_item.name}"): # Will only download a file if it doesn't already exist (Only applies if we're downloading everything)
                                with open(f"{BASE_FILE_PATH}/{path}/Miniscope/{sub_item.name}", "wb") as output_file: # Creates a file to store the data
                                    client.downloads.download_file_to_output_stream(sub_item.id, output_stream=output_file) # Downloads data to the file
                                    print(f"File '{sub_item.name}' downloaded successfully to '{BASE_FILE_PATH}/{path}/Miniscope/{sub_item.name}'") # DEBUG: Prints that we've successfully downloaded a file. Line won't run if there's an error 
                else: # If for some reason we have a sub-folder that isn't the miniscope folder, we recursively call the function to download it.
                    download_file(client,f"{path}/{item.name}",item.id,need_to_download)
            
            else:        
                if not os_path.exists(f"{BASE_FILE_PATH}/{path}/{item.name}"): # Will only download a file if it doesn't already exist.
                    with open(f"{BASE_FILE_PATH}/{path}/{item.name}", "wb") as output_file: # Creates a file to store the data
                        client.downloads.download_file_to_output_stream(item.id, output_stream=output_file) # Downloads data to the file
                        print(f"File '{item.name}' downloaded successfully to '{BASE_FILE_PATH}/{path}/{item.name}'") # DEBUG: Prints that we've successfully downloaded a file. Line won't run if there's an error

        return True # Returns True once everthing is downloaded
    except Exception as e: #Catches any error
        print(f"Download failed: {e}")
        return False






if __name__ == '__main__': # Runs when we run the file.
    
    verify_file_by_line(
        line_num= 96, # The one contained in the CSV column "line number"
        csv_path= EXPERIMENTS, # Path to the CSV folder
        do_type= "miniscope", # do_type must be "both", "miniscope", or "ephys"
        
        avi_list=["0.avi"] # Only need to fill this in if you're downloading miniscope files.
    )