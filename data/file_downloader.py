from box_credentials import dev_token, BASE_FILE_PATH
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth   
from os import path as os_path, makedirs

"""TO DO:
    - rewrite all CSVs to have standard relative paths to the base folder
    - Add box folder IDs to all CSVs so filereader can download it.
    - Work with teammates to develop standardized nomenclature and use of this file.
    - Make Authorization permanant using Client Credentials Grant
    - Add command line compatibility
    - Maybe Modularize as a class?
"""
        
client = None
    
def make_auth():
    auth = BoxDeveloperTokenAuth(token=dev_token)
    client = BoxClient(auth=auth)
    return client
    
def verify_file(path: str):
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    if not client: # Makes sure we're connected to box
        client = make_auth()
    if not os_path.exists(f"{BASE_FILE_PATH}/{path}"): # Checks if the directory doesn't already exist
        makedirs(f"{BASE_FILE_PATH}/{path}") # Makes a folder for our downloads
        file_id = get_file_id(path) # WIP function to get the id of the folder we're downloading
        download_file(path, file_id) # Calls the download function to get our data
    elif os_path.exists(f"{BASE_FILE_PATH}/{path}"): # If we already have the folder, then we don't need to download anything
        return True # NOTE: This will still return True even if the downloads are incomplete or the folder is empty
    else:
        print("Error (error message here)") # Just in case

def get_file_id(path: str, csv="experiments.csv"):
    """Opens and reads the CSV file (experiements.csv by default) to get the box id of that experiment folder"""
    # Will figure out the best way to store this and get the right CSV File
    #temporary manual override
    return "274171379379"
    pass


def download_file(path: str, ID):
    """Called from verify_file or run manually to download a file from box and store it in a standard path
    """
    if not client: # Makes sure we're connected to Box
        client = make_auth()
    
    try:
        for item in client.folders.get_folder_items(ID).entries: #Goes to the folder we want to download
            print(item.name) #Debug print statement to know what item we're currently looking at
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
    client = make_auth()
    verify_file("K99/R221107A/2023_03_09/15_52_17")