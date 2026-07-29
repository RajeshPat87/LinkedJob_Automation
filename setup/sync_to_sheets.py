'''
One command sync: writes this run's dated exports, then uploads that day's spreadsheet.

Run from the project root so the relative "all excels/" paths resolve:
    .venv/bin/python3 setup/sync_to_sheets.py
'''

import sys
from datetime import datetime

import export_external_jobs
import export_failed_jobs
import export_for_sheets
import upload_to_sheets

SCOPE_HINT = upload_to_sheets.SCOPE_HINT


def sync() -> None:
    '''Writes this run's snapshots, then uploads the day's spreadsheet to Drive.

    All three exports share one timestamp so the run's files sit together in the dated
    folder. The exports are the durable output, so an upload failure (expired or unscoped
    credentials, no network) is reported but never discards the freshly written CSVs.
    '''
    moment = datetime.now()
    paths = {
        'Applied': export_for_sheets.export(moment),
        'External Jobs': export_external_jobs.export(moment),
        'Failed Jobs': export_failed_jobs.export(moment),
    }
    try:
        print("Spreadsheet for " + moment.strftime("%Y-%m-%d") + ": "
              + upload_to_sheets.upload(paths))
    except Exception as error:
        print(f"Exports written, but the Drive upload failed: {type(error).__name__}: {error}",
              file=sys.stderr)
        print(SCOPE_HINT, file=sys.stderr)


if __name__ == "__main__":
    sync()
