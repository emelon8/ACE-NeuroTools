from box_credentials import dev_token, base_file_path
from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth

def main(token: str):
    auth: BoxDeveloperTokenAuth = BoxDeveloperTokenAuth(token=token)
    client: BoxClient = BoxClient(auth=auth)
    for item in client.folders.get_folder_items('0').entries:
        print(item.name)
    

def verify_file(path):
    """Checks the path where the file should be.
    If a folder doesn't exist, break the search and call download_file(path) to download and store the file
    """
    pass

def download_file(path):
    """Called from verify_file or run manually to download a file from box and store it in a standard path
    """
    
    #Auth block here
    
    #Try to download, if error then raise an appropriate error
    
    #Download path: f"{base_file_path}/{path}
    
    #Upon success return true
    
    pass











if __name__ == '__main__':
    main(dev_token)