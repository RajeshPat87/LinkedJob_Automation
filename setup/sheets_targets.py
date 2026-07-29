'''
Remembers what has already been created in Google Drive.

Without this, every run would create a brand new Drive folder and a duplicate spreadsheet
for the same day. The registry maps the Drive folder ID and each dated folder to the
spreadsheet that represents it:

    {
      "folder_id": "1AbC...",
      "spreadsheets": {"2026-07-28": "1XyZ...", "2026-07-29": "1QrS..."}
    }

Updates return a new dict rather than mutating the one passed in, so a failed run cannot
leave a half-updated registry in memory.
'''

import json

TARGET_FILE = "all excels/.sheets_targets.json"
EMPTY_REGISTRY: dict = {'folder_id': None, 'spreadsheets': {}}


def load() -> dict:
    '''Reads the registry, returning an empty one when nothing has been created yet.'''
    try:
        with open(TARGET_FILE, 'r', encoding='utf-8') as file:
            stored = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(EMPTY_REGISTRY)
    return {'folder_id': stored.get('folder_id'),
            'spreadsheets': dict(stored.get('spreadsheets') or {})}


def save(registry: dict) -> None:
    '''Persists the registry next to the exports.'''
    with open(TARGET_FILE, 'w', encoding='utf-8') as file:
        json.dump(registry, file, indent=2, sort_keys=True)


def with_folder(registry: dict, folder_id: str) -> dict:
    '''Returns a copy of the registry carrying the Drive folder ID.'''
    return {**registry, 'folder_id': folder_id}


def with_spreadsheet(registry: dict, date_key: str, spreadsheet_id: str) -> dict:
    '''Returns a copy of the registry with one day's spreadsheet recorded.'''
    return {**registry, 'spreadsheets': {**registry['spreadsheets'], date_key: spreadsheet_id}}


def spreadsheet_for(registry: dict, date_key: str) -> str | None:
    '''Returns the spreadsheet ID already created for a date, if any.'''
    return registry['spreadsheets'].get(date_key)
