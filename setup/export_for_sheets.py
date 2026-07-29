'''
Builds a readable, Google Sheets ready export of the Easy Apply attempts.

This tab answers "what did the bot actually submit on LinkedIn". External jobs are excluded
(they live in export_external_jobs.py) because for those the bot only collected a link and
never applied.

Easy Apply can also break part way through the modal, and those attempts land in the failed
history rather than the applied one. Both are merged here and told apart by the
'Easy Apply Status' column, so a failure is visible next to the successes instead of being
buried among filter skips.

Rows are ordered by the country priority from config/search.py.
'''

from datetime import datetime

from country_lookup import country_for_row, priority_of
from export_paths import run_path
from sheets_formatting import clean_date, hyperlink, preview, read_rows, write_rows

APPLIED_SOURCE = "all excels/all_applied_applications_history.csv"
FAILED_SOURCE = "all excels/all_failed_applications_history.csv"
EXPORT_PREFIX = "applied"
FIELDNAMES = ['Job ID', 'Easy Apply Status', 'Title', 'Company', 'Country', 'Priority',
              'Work Location', 'Work Style', 'Date Applied', 'Date Posted',
              'Experience required', 'Failure Reason', 'LinkedIn Job Link',
              'About Job (preview)']

# The bot writes this reason when the Easy Apply modal itself failed, as opposed to a
# deliberate filter skip or an external-apply problem.
EASY_APPLY_FAILURE_REASON = "Problem in Easy Applying"


def success_row(row: dict[str, str]) -> dict[str, str]:
    '''Maps a submitted Easy Apply row to the export columns.'''
    country = country_for_row(row)
    return {
        'Job ID': row.get('Job ID', ''),
        'Easy Apply Status': 'Success',
        'Title': row.get('Title', ''),
        'Company': row.get('Company', ''),
        'Country': country,
        'Priority': priority_of(country),
        'Work Location': row.get('Work Location', ''),
        'Work Style': row.get('Work Style', ''),
        'Date Applied': clean_date(row.get('Date Applied', '')),
        'Date Posted': clean_date(row.get('Date Posted', '')),
        'Experience required': row.get('Experience required', ''),
        'Failure Reason': '',
        'LinkedIn Job Link': hyperlink(row.get('Job Link', ''), "LinkedIn"),
        'About Job (preview)': preview(row.get('About Job', '')),
    }


def failure_row(row: dict[str, str]) -> dict[str, str]:
    '''Maps a failed Easy Apply attempt to the same columns.

    The failed history has no title, company or scraped location, so those stay blank rather
    than being guessed at. The country still resolves from the search location the bot
    recorded for the job.
    '''
    country = country_for_row(row)
    return {
        'Job ID': row.get('Job ID', ''),
        'Easy Apply Status': 'Failed',
        'Title': '',
        'Company': '',
        'Country': country,
        'Priority': priority_of(country),
        'Work Location': '',
        'Work Style': '',
        'Date Applied': '',
        'Date Posted': clean_date(row.get('Date listed', '')),
        'Experience required': '',
        'Failure Reason': row.get('Assumed Reason', ''),
        'LinkedIn Job Link': hyperlink(row.get('Job Link', ''), "LinkedIn"),
        'About Job (preview)': preview(row.get('Stack Trace', '')),
    }


def collect_rows() -> list[dict[str, str]]:
    '''Gathers Easy Apply successes and failures, ordered by country priority.'''
    rows = [success_row(row) for row in read_rows(APPLIED_SOURCE)
            if row.get('Status') == 'Easy Applied']
    rows += [failure_row(row) for row in read_rows(FAILED_SOURCE)
             if row.get('Assumed Reason') == EASY_APPLY_FAILURE_REASON]
    # Highest priority country first, then newest attempt first within a country.
    rows.sort(key=lambda row: (row['Priority'], row['Date Applied'] or row['Date Posted']),
              reverse=False)
    return rows


def export(moment: datetime | None = None) -> str:
    '''Writes this run's Easy Apply snapshot and returns its path.'''
    path = run_path(EXPORT_PREFIX, moment or datetime.now())
    rows = collect_rows()
    count = write_rows(path, FIELDNAMES, rows)
    failures = sum(1 for row in rows if row['Easy Apply Status'] == 'Failed')
    print(f"Wrote {count} Easy Apply rows ({count - failures} success, {failures} failed) to {path}")
    return path


if __name__ == "__main__":
    export()
