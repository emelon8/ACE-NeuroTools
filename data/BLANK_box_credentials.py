"""This is a file to safely store your box credentials and keep them secure during your git commits.
THIS PROGRAM WAS DEVELOPED FOR BOX-SDK-10.0.1

To properly set up this file:
1. Make a copy of this file and rename it to "box_credentials.py" 
2. Insert your box developer token in the field labled PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE
    a. To obtain your box developer token, go to the box developer console at <https://byu.app.box.com/developers/console>
    b. create a custom app and select "Server Authentication (Client Credentials Grant)"
    tbd 
3. You're done!"""

from pathlib import Path

dev_token = 'PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE'

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Replace DATA_DIR / "downloaded_data" with a different path if you're storing your data elsewhere
BASE_FILE_PATH = DATA_DIR / "downloaded_data" 