'''
Builds a Google Sheets ready export of external (non Easy Apply) jobs.

These are jobs where the bot captured the company's own apply link instead of applying on
LinkedIn, so each row is a to-do: open the portal link and finish the application manually.
'''

from datetime import datetime

from country_lookup import country_for_row, priority_of
from export_paths import run_path
from sheets_formatting import (clean_date, domain_of, hyperlink, is_url, preview, read_rows,
                               write_rows)

SOURCE_PATH = "all excels/all_applied_applications_history.csv"
EXPORT_PREFIX = "external"
FIELDNAMES = ['Job ID', 'Title', 'Company', 'Country', 'Priority', 'Work Location',
              'Work Style', 'Portal', 'Apply Link', 'LinkedIn Job Link', 'Date Posted',
              'Date Collected', 'Experience required', 'Manually Applied?',
              'About Job (preview)']


def to_export_row(row: dict[str, str]) -> dict[str, str]:
    '''Maps one history row to the external-jobs tracking columns.'''
    external = (row.get('External Job link') or "").strip()
    country = country_for_row(row)
    return {
        'Job ID': row.get('Job ID', ''),
        'Title': row.get('Title', ''),
        'Company': row.get('Company', ''),
        'Country': country,
        'Priority': priority_of(country),
        'Work Location': row.get('Work Location', ''),
        'Work Style': row.get('Work Style', ''),
        'Portal': domain_of(external),
        'Apply Link': hyperlink(external, "Apply"),
        'LinkedIn Job Link': hyperlink(row.get('Job Link', ''), "LinkedIn"),
        'Date Posted': clean_date(row.get('Date Posted', '')),
        'Date Collected': clean_date(row.get('Date Applied', '')) or clean_date(row.get('Date Posted', '')),
        'Experience required': row.get('Experience required', ''),
        'Manually Applied?': 'No',
        'About Job (preview)': preview(row.get('About Job', '')),
    }


def export(moment: datetime | None = None) -> str:
    '''Writes every applied-history row with a real external apply link, and returns the path.

    Ordered by country priority so the jobs you most want to apply to sit at the top of the
    to-do list.
    '''
    path = run_path(EXPORT_PREFIX, moment or datetime.now())
    external_rows = [to_export_row(row) for row in read_rows(SOURCE_PATH)
                     if is_url(row.get('External Job link', ''))]
    external_rows.sort(key=lambda row: (row['Priority'], row['Date Posted']))
    count = write_rows(path, FIELDNAMES, external_rows)
    print(f"Wrote {count} external jobs to {path}")
    return path


if __name__ == "__main__":
    export()
