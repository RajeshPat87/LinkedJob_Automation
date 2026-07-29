'''
One time Google authorization for the Drive/Sheets upload.

gcloud's Application Default Credentials work today but Google is phasing out the
spreadsheets scope for gcloud's built-in client ID, so this uses your own OAuth client
instead. The refresh token it saves keeps working unattended, which is what the cron job
needs.

Setup, once:

  1. Open https://console.cloud.google.com/apis/credentials?project=gen-lang-client-0379363024
  2. Create Credentials -> OAuth client ID -> Application type "Desktop app"
  3. Download the JSON and save it as   client_secret.json   in the project root
  4. If the consent screen is in "Testing" mode, add rajeshsqldba87@gmail.com under
     Audience -> Test users, otherwise the sign-in is rejected
  5. Run:  .venv/bin/python3 setup/authorize_google.py

That opens a browser, you approve once, and the token lands in .google_token.json.
Delete that file and re-run this script to switch accounts or re-consent.
'''

import os
import sys

CLIENT_SECRET_FILE = "client_secret.json"
TOKEN_FILE = ".google_token.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive.file']


def load_token():
    '''Returns saved user credentials, refreshing them when expired. None when not authorized.'''
    if not os.path.exists(TOKEN_FILE):
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    credentials = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if credentials.valid:
        return credentials
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_token(credentials)
        return credentials
    return None


def save_token(credentials) -> None:
    '''Writes the token where the uploader looks for it, readable only by this user.'''
    with open(TOKEN_FILE, 'w', encoding='utf-8') as file:
        file.write(credentials.to_json())
    os.chmod(TOKEN_FILE, 0o600)


# Under WSL there is no Linux browser, and xdg-open falls through to an unusable fallback.
# These are the usual Windows install paths, tried in order.
WINDOWS_BROWSERS = (
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)


def use_windows_browser() -> bool:
    '''Points the webbrowser module at a Windows browser when running under WSL.

    Returns False when no Windows browser is found, in which case the caller should fall
    back to printing the URL for the user to open manually.
    '''
    if "microsoft" not in os.uname().release.lower(): return False
    for path in WINDOWS_BROWSERS:
        if os.path.exists(path):
            os.environ['BROWSER'] = path.replace(" ", r"\ ") + " %s"
            return True
    return False


def authorize():
    '''Runs the browser consent flow and stores the resulting refresh token.'''
    if not os.path.exists(CLIENT_SECRET_FILE):
        raise SystemExit(
            f"Missing {CLIENT_SECRET_FILE} in {os.getcwd()}.\n"
            "Create a Desktop app OAuth client and save its JSON there - see the steps at the "
            "top of this file.")

    opened = use_windows_browser()
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    # port=0 picks a free port. WSL2 forwards localhost, so the redirect from the Windows
    # browser reaches this server. If nothing opens, the printed URL still works.
    credentials = flow.run_local_server(
        port=0, prompt='consent', open_browser=opened,
        authorization_prompt_message="Open this URL to authorize:\n{url}")
    save_token(credentials)
    return credentials


if __name__ == "__main__":
    existing = load_token()
    if existing and "--force" not in sys.argv:
        print(f"Already authorized ({TOKEN_FILE} is valid). Re-run with --force to redo it.")
    else:
        authorize()
        print(f"Authorized. Token saved to {TOKEN_FILE}")
    print("Now run:  .venv/bin/python3 setup/upload_to_sheets.py --all")
