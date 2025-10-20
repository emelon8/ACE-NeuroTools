from box_credentials import dev_token, base_file_path
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth
from os import path as os_path, makedirs

"""TO DO:
    - rewrite all CSVs to have standard relative paths to the base folder
    - Add box folder IDs to all CSVs so filereader can download it.
    - Work with teammates to develop standardized nomenclature and use of this file.
"""
        
auth = None
client = None
    
def make_auth():
    BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=dev_token)
    auth = BoxDeveloperTokenAuth
    BoxClient = BoxClient(auth=auth)
    client = BoxClient

def verify_file(path: str):
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    if not client:
        makeauth()
    if not os_path.exists(f"{base_file_path}/{path}"):
        makedirs(f"{base_file_path}/{path}")
        file_id = get_file_id(path)
        download_file(path, file_id)
    elif os_path.exists(f"{base_file_path}/{path}"):
        return True
    else:
        print("Error (error message here)")

def get_file_id(path: str, csv="experiments.csv"):
    """Opens and reads the CSV file (experiements.csv by default) to get the box id of that experiment folder"""
    
    #temporary manual override
    return "274171379379"
    pass


def download_file(path: str, ID):
    """Called from verify_file or run manually to download a file from box and store it in a standard path
    """
    if not client:
        make_auth()
    
    try:
        for item in client.folders.get_folder_items(ID).entries:
            print(item.name)
            if item.type == 'folder':
                print(f"Found a folder: {item.name}")
                makedirs(f"{base_file_path}/{path}/{item.name}")
                download_file(path=f"{path}/{item.name}", ID=item.id)
                continue
        
            with open(f"{base_file_path}/{path}/{item.name}", "wb") as output_file:
                client.downloads.download_file_to_output_stream(item.id, output_stream=output_file)
                print(f"File '{item.name}' downloaded successfully to '{base_file_path}/{path}/{item.name}'")

        return True # Returns True once everthing is downloaded
    except Exception as e:
        print(e)
        return False


if __name__ == '__main__':
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=dev_token)
    client: BoxClient = BoxClient(auth=auth)
    verify_file("K99/R221107A/2023_03_09/15_52_17")