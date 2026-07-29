'''
Builds a Google Sheets ready export of failed / skipped job attempts.

The raw failed history stores the whole job description or Python traceback in the
'Stack Trace' column, so this trims it to a preview and keeps the reason, links and
screenshot reference for triage.

Each run writes a new snapshot into that day's folder as failed_<timestamp>.csv, so the
three daily runs leave three files rather than overwriting one. See export_paths.py.
'''

from datetime import datetime

from country_lookup import country_for_row, priority_of
from export_paths import run_path
from sheets_formatting import (clean_date, hyperlink, is_real_value, preview, read_rows,
                               write_rows)

SOURCE_PATH = "all excels/all_failed_applications_history.csv"
EXPORT_PREFIX = "failed"
FIELDNAMES = ['Job ID', 'Assumed Reason', 'Failure Type', 'Country', 'Priority',
              'LinkedIn Job Link', 'Apply Link', 'Date Listed', 'Date Tried', 'Resume Tried',
              'Screenshot', 'Details (preview)']

# Easy Apply breakages are reported on the Applied tab next to the successes, so they are
# left out here to keep the three tabs mutually exclusive.
EASY_APPLY_FAILURE_REASON = "Problem in Easy Applying"

# Skips are deliberate filter decisions; anything else is a real automation failure to look at.
SKIP_REASONS = ('bad word', 'security clearance', 'blacklist', 'already applied')


def failure_type(reason: str) -> str:
    '''Separates intentional filter skips from genuine automation breakages.'''
    lowered = (reason or "").lower()
    return 'Skipped by filter' if any(hint in lowered for hint in SKIP_REASONS) else 'Automation failure'


def to_export_row(row: dict[str, str]) -> dict[str, str]:
    '''Maps one failed-history row to the triage columns.'''
    reason = row.get('Assumed Reason', '')
    screenshot = row.get('Screenshot Name', '')
    # The failed history has no scraped location, so this resolves from the search
    # location the bot recorded for the job.
    country = country_for_row(row)
    return {
        'Job ID': row.get('Job ID', ''),
        'Assumed Reason': reason,
        'Failure Type': failure_type(reason),
        'Country': country,
        'Priority': priority_of(country),
        'LinkedIn Job Link': hyperlink(row.get('Job Link', ''), "LinkedIn"),
        'Apply Link': hyperlink(row.get('External Job link', ''), "Apply"),
        'Date Listed': clean_date(row.get('Date listed', '')),
        'Date Tried': clean_date(row.get('Date Tried', '')),
        'Resume Tried': row.get('Resume Tried', ''),
        'Screenshot': screenshot if is_real_value(screenshot) else '',
        'Details (preview)': preview(row.get('Stack Trace', '')),
    }


def export(moment: datetime | None = None) -> str:
    '''Writes the skipped and broken attempts to this run's snapshot and returns its path.'''
    path = run_path(EXPORT_PREFIX, moment or datetime.now())
    rows = [to_export_row(row) for row in read_rows(SOURCE_PATH)
            if row.get('Assumed Reason') != EASY_APPLY_FAILURE_REASON]
    rows.sort(key=lambda row: (row['Priority'], row['Failure Type'], row['Date Tried']))
    count = write_rows(path, FIELDNAMES, rows)
    breakages = sum(1 for row in rows if row['Failure Type'] == 'Automation failure')
    print(f"Wrote {count} failed jobs ({count - breakages} filter skips, "
          f"{breakages} automation failures) to {path}")
    return path


if __name__ == "__main__":
    export()
