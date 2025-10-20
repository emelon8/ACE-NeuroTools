from box_credentials import dev_token, base_file_path
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from os import path

"""TO DO:
    - rewrite all CSVs to have standard relative paths to the base folder
    - Add box folder IDs to all CSVs so filereader can download it.
    - Work with teammates to develop standardized nomenclature and use of this file.
"""

def main(token: str):
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=token)
    client: BoxClient = BoxClient(auth=auth)
    for item in client.folders.get_folder_items('0').entries:
        print(item.name)
    

def verify_file(path: str):
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    if not path.exists(f"{base_file_path}/{path}"):
        file_id = get_file_id(path)
        download_file(path, file_id)
    elif path.exists(f"{base_file_path}/{path}"):
        return True
    else:
        print("Error (error message here)")

def get_file_id(path: str, csv="experiments.csv"):
    """Opens and reads the CSV file (experiements.csv by default) to get the box id of that experiment folder"""
    pass


def download_file(path: str, ID):
    """Called from verify_file or run manually to download a file from box and store it in a standard path
    """
    
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=dev_token)
    client: BoxClient = BoxClient(auth=auth)
    
    try:
        for item in client.folders.get_folder_items(ID).entries:
            print(item.name)
            if item.type == 'folder':
                print("Found a folder")
            with open(f"{base_file_path}/{path}/{item.name}", "wb") as output_file:
                pass
        
        # file = client.downloads.download_file(ID)
        pass
    except Exception as e:
        print(e)
    
    #Download path: f"{base_file_path}/{path}
    
    #Upon success return true
    
    pass



if __name__ == '__main__':
    download_file("K99/R221107A/2023_03_09/15_52_17",274171379379)