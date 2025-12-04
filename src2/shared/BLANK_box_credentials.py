"""This is a file to safely store your box credentials and keep them secure during your git commits.
THIS PROGRAM WAS DEVELOPED FOR BOX-SDK-10.0.1

To properly set up this file:
1. *Make a copy of this file and rename it to "box_credentials.py"* 
2. Insert your box credentials in the appropriate fields (For directions on how to obtain these credentials, see the documentation here: <https://developer.box.com/guides/authentication/client-credentials/client-credentials-setup/>)
    a. To obtain your box credentials, go to the box developer console at <https://byu.app.box.com/developers/console>
    b. If you're the first person on your team to set this up, create a custom app and select "Server Authentication (Client Credentials Grant)". This app can accommodate up to 15 team members.
      a. Navigate to configuration and select the box labeled "Write all files and folders stored in Box"
      b. For temporary testing, use the box developer token. It lasts for an hour.
      c. For a permanant set up, use the client id, client secret, and user id to authenticate, you'll have to request authorization from your enterprise in order to set this up
3. You're done!"""

from box_sdk_gen import BoxCCGAuth, CCGConfig
from src2.shared.paths import DATA_DIR

dev_token = 'PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE'

ccgconfig = CCGConfig(
  client_id="YOUR_CLIENT_ID",
  client_secret="YOUR_CLIENT_SECRET",
  user_id="YOUR_USER_ID"
)
auth = BoxCCGAuth(config=ccgconfig)