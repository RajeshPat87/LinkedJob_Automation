'''
Uploads the dated CSV exports to Google Drive as one spreadsheet per day.

Drive layout, mirroring the local "all excels/<date>/" folders:

    My Drive/
        LinkedIn Job Applier/
            2026-07-28      <- tabs: Applied | External Jobs | Failed Jobs | Run Log
            2026-07-29      <- same four tabs for that day
            ...

Within a day's spreadsheet the three data tabs hold that day's newest snapshot (the bot's
history CSVs are cumulative, so the newest snapshot is the complete picture), and the Run
Log tab lists every run of that day. The Run Log is recomputed from the files on disk each
time, so re-uploading a day or backfilling an old one produces the same result rather than
duplicating rows.

Authentication uses OAuth, never an account password (Google blocks password based API
sign-in). Credentials are resolved in this order:

  1. GOOGLE_SHEETS_CREDENTIALS -> path to a service account JSON key.
  2. Application Default Credentials, e.g. after:
       gcloud auth application-default login \
         --scopes=https://www.googleapis.com/auth/spreadsheets,https://www.googleapis.com/auth/drive.file,openid

Usage:
    python setup/upload_to_sheets.py           # upload the most recent day
    python setup/upload_to_sheets.py --all     # upload every dated folder
'''

import csv
import os
import sys

import sheets_targets
from export_paths import date_folders, latest_export, runs_in

SCOPES = ['https://www.googleapis.com/auth/spreadsheets',
          'https://www.googleapis.com/auth/drive.file']
DRIVE_FOLDER_NAME = "LinkedIn Job Applier"
SPREADSHEET_MIME = 'application/vnd.google-apps.spreadsheet'
FOLDER_MIME = 'application/vnd.google-apps.folder'

# Tab name -> export prefix. Order defines the tab order in each day's spreadsheet.
TAB_PREFIXES = {
    'Applied': 'applied',
    'External Jobs': 'external',
    'Failed Jobs': 'failed',
}
RUN_LOG_TAB = 'Run Log'
RUN_LOG_HEADER = ['Run Timestamp', *TAB_PREFIXES]
TAB_ORDER = (*TAB_PREFIXES, RUN_LOG_TAB)

SCOPE_HINT = ("Not authorized for Drive/Sheets yet. Run:\n"
              "  .venv/bin/python3 setup/authorize_google.py\n"
              "(see that file's header for the one time client_secret.json setup)")


def build_credentials():
    '''Returns scoped credentials from the first source that is set up.

    Order: an explicit service account key, then the token from authorize_google.py, then
    gcloud Application Default Credentials. The token is preferred over ADC because Google
    is phasing out the spreadsheets scope for gcloud's built-in client ID.
    '''
    key_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
    if key_path:
        from google.oauth2 import service_account
        return service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)

    import authorize_google
    token = authorize_google.load_token()
    if token:
        return token

    import google.auth
    credentials, _ = google.auth.default(scopes=SCOPES)
    return credentials


def build_apis():
    '''Builds the Sheets and Drive clients from one set of credentials.'''
    from googleapiclient.discovery import build
    credentials = build_credentials()
    return (build('sheets', 'v4', credentials=credentials, cache_discovery=False),
            build('drive', 'v3', credentials=credentials, cache_discovery=False))


def read_csv_values(path: str) -> list[list[str]]:
    '''Reads a CSV into the row-major list of lists the Sheets values API expects.'''
    csv.field_size_limit(1000000)
    with open(path, 'r', encoding='utf-8') as file:
        return [row for row in csv.reader(file)]


def still_exists(drive_api, file_id: str) -> bool:
    '''True when a remembered Drive file is still present and not in the trash.'''
    try:
        found = drive_api.files().get(fileId=file_id, fields='id,trashed').execute()
    except Exception:
        return False
    return not found.get('trashed', False)


def ensure_folder(drive_api, registry: dict) -> tuple[str, dict]:
    '''Returns the Drive folder ID for the exports, creating the folder when needed.'''
    remembered = registry.get('folder_id')
    if remembered and still_exists(drive_api, remembered):
        return remembered, registry
    created = drive_api.files().create(
        body={'name': DRIVE_FOLDER_NAME, 'mimeType': FOLDER_MIME}, fields='id').execute()
    print(f"Created Drive folder '{DRIVE_FOLDER_NAME}' ({created['id']})")
    return created['id'], sheets_targets.with_folder(registry, created['id'])


def name_tabs(sheets_api, spreadsheet_id: str) -> None:
    '''Renames the default sheet to the first tab and adds the rest, in order.'''
    meta = sheets_api.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields='sheets.properties(sheetId,title)').execute()
    first_sheet_id = meta['sheets'][0]['properties']['sheetId']
    requests = [{'updateSheetProperties': {
        'properties': {'sheetId': first_sheet_id, 'title': TAB_ORDER[0]}, 'fields': 'title'}}]
    requests += [{'addSheet': {'properties': {'title': title}}} for title in TAB_ORDER[1:]]
    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body={'requests': requests}).execute()


def add_missing_tabs(sheets_api, spreadsheet_id: str) -> None:
    '''Adds any tabs a remembered spreadsheet does not have yet.'''
    meta = sheets_api.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields='sheets.properties.title').execute()
    present = {sheet['properties']['title'] for sheet in meta.get('sheets', [])}
    missing = [title for title in TAB_ORDER if title not in present]
    if not missing: return
    sheets_api.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={'requests': [{'addSheet': {'properties': {'title': title}}} for title in missing]}
    ).execute()


def ensure_day_spreadsheet(sheets_api, drive_api, registry: dict, date_key: str,
                           folder_id: str) -> tuple[str, dict]:
    '''Returns the spreadsheet ID for one day, creating it inside the Drive folder if needed.'''
    remembered = sheets_targets.spreadsheet_for(registry, date_key)
    if remembered and still_exists(drive_api, remembered):
        add_missing_tabs(sheets_api, remembered)
        return remembered, registry

    created = drive_api.files().create(
        body={'name': date_key, 'mimeType': SPREADSHEET_MIME, 'parents': [folder_id]},
        fields='id').execute()
    name_tabs(sheets_api, created['id'])
    print(f"Created spreadsheet '{date_key}' ({created['id']})")
    return created['id'], sheets_targets.with_spreadsheet(registry, date_key, created['id'])


def write_tab(sheets_api, spreadsheet_id: str, tab: str, values: list[list[str]]) -> None:
    '''Replaces a tab's contents, keeping HYPERLINK cells as live formulas.'''
    sheets_api.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=f"'{tab}'").execute()
    if not values: return
    sheets_api.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=f"'{tab}'!A1",
        valueInputOption='USER_ENTERED', body={'values': values}).execute()


def run_log_values(date_key: str) -> list[list[str]]:
    '''Builds the Run Log rows for a day by counting the snapshot files each run produced.'''
    rows = [RUN_LOG_HEADER]
    for moment, paths in runs_in(date_key):
        counts = [max(len(read_csv_values(paths[prefix])) - 1, 0) if prefix in paths else ""
                  for prefix in TAB_PREFIXES.values()]
        rows.append([moment.strftime("%Y-%m-%d %H:%M:%S"), *counts])
    return rows


def freeze_headers(sheets_api, spreadsheet_id: str) -> None:
    '''Freezes and bolds the header row on every tab.'''
    meta = sheets_api.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields='sheets.properties(sheetId,title)').execute()
    requests = []
    for sheet in meta.get('sheets', []):
        properties = sheet['properties']
        if properties['title'] not in TAB_ORDER: continue
        sheet_id = properties['sheetId']
        requests.append({'updateSheetProperties': {
            'properties': {'sheetId': sheet_id, 'gridProperties': {'frozenRowCount': 1}},
            'fields': 'gridProperties.frozenRowCount'}})
        requests.append({'repeatCell': {
            'range': {'sheetId': sheet_id, 'startRowIndex': 0, 'endRowIndex': 1},
            'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}},
            'fields': 'userEnteredFormat.textFormat.bold'}})
    if requests:
        sheets_api.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={'requests': requests}).execute()


def write_day(sheets_api, spreadsheet_id: str, date_key: str) -> None:
    '''Fills one day's spreadsheet: that day's newest snapshot per tab, plus its Run Log.'''
    print(f"{date_key}:")
    for tab, prefix in TAB_PREFIXES.items():
        path = latest_export(prefix, date_key)
        if not path:
            print(f"  {tab}: no export for this day, skipped")
            continue
        values = read_csv_values(path)
        write_tab(sheets_api, spreadsheet_id, tab, values)
        print(f"  {tab}: {max(len(values) - 1, 0)} rows from {path}")

    log_rows = run_log_values(date_key)
    write_tab(sheets_api, spreadsheet_id, RUN_LOG_TAB, log_rows)
    print(f"  {RUN_LOG_TAB}: {len(log_rows) - 1} run(s)")
    freeze_headers(sheets_api, spreadsheet_id)


def upload_days(date_keys: list[str]) -> dict[str, str]:
    '''Uploads several dated folders, reusing one set of credentials. Returns date -> URL.'''
    if not date_keys:
        raise SystemExit("No dated exports found. Run the export scripts first.")

    sheets_api, drive_api = build_apis()
    registry = sheets_targets.load()
    folder_id, registry = ensure_folder(drive_api, registry)

    urls = {}
    try:
        for date_key in date_keys:
            spreadsheet_id, registry = ensure_day_spreadsheet(
                sheets_api, drive_api, registry, date_key, folder_id)
            write_day(sheets_api, spreadsheet_id, date_key)
            urls[date_key] = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    finally:
        # Saved even on a partial failure, so an interrupted batch does not orphan the
        # folder or spreadsheets it already created.
        sheets_targets.save(registry)
    return urls


def upload(paths: dict[str, str] | None = None) -> str:
    '''Uploads the day a run belongs to, or the most recent day when called standalone.

    `paths` is the run's export paths as returned by the export scripts; only the date they
    sit in is needed, since the day's tabs are rebuilt from disk.
    '''
    from export_paths import folder_name
    if paths:
        date_key = folder_name(next(iter(paths.values())))
    else:
        folders = date_folders()
        if not folders:
            raise SystemExit("No dated exports found. Run the export scripts first.")
        date_key = folders[-1]
    return upload_days([date_key])[date_key]


if __name__ == "__main__":
    try:
        if "--all" in sys.argv:
            results = upload_days(date_folders())
            print("\nUploaded {} day(s) to Drive folder '{}':".format(
                len(results), DRIVE_FOLDER_NAME))
            for date_key, url in results.items():
                print(f"  {date_key}: {url}")
        else:
            print("Spreadsheet: " + upload())
    except SystemExit:
        raise
    except Exception as error:
        print(f"Upload failed: {type(error).__name__}: {error}", file=sys.stderr)
        print("\n" + SCOPE_HINT, file=sys.stderr)
        raise SystemExit(1)
