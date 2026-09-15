"""This is a file to safely store your box credentials and keep them secure during your git commits.
THIS PROGRAM WAS DEVELOPED FOR BOX-SDK-10.0.1

To properly set up this file:
1. *Make a copy of this file and rename it to "box_credentials.py"* 
2. Insert your box credentials in the appropriate fields (For directions on how to obtain these credentials, see the documentation here: <https://developer.box.com/guides/authentication/client-credentials/client-credentials-setup/>)
    a. To obtain your box credentials, go to the box developer console at <https://byu.app.box.com/developers/console>
    b. If you're the first person on your team to set this up, create a custom app and select "Server Authentication (Client Credentials Grant)". This app can accommodate up to 15 team members.
      a. Navigate to configuration and select the box labeled "Write all files and folders stored in Box"
      b. For temporary testing, replace the dev_token placeholder with a Box developer token. The auth object below will then use that token.
      c. For a permanent setup, leave the dev_token placeholder unchanged and enter the client ID, client secret, and user ID. Your enterprise must authorize this app.
3. You're done!

TODO: In a future release, move this configuration to a user-specific config directory 
(e.g., ~/.config/aceneurotools/) to better support package distribution via Conda/PyPI.
"""

from box_sdk_gen import BoxCCGAuth, BoxDeveloperTokenAuth, CCGConfig

dev_token = 'PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE'

ccgconfig = CCGConfig(
  client_id="YOUR_CLIENT_ID",
  client_secret="YOUR_CLIENT_SECRET",
  user_id="YOUR_USER_ID"
)
if dev_token != 'PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE':
  auth = BoxDeveloperTokenAuth(token=dev_token)
else:
  auth = BoxCCGAuth(config=ccgconfig)
