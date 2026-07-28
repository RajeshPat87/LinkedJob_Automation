'''
Builds a readable, Google Sheets ready export from the applied jobs history.

The raw history CSV keeps the full job description (~3k characters per row), which makes it
unreadable in a spreadsheet viewer. This writes the tracking columns only, with the
description trimmed to a preview, and the job links as clickable HYPERLINK formulas.
'''

import csv

csv.field_size_limit(1000000)

SOURCE_PATH = "all excels/all_applied_applications_history.csv"
EXPORT_PATH = "all excels/applied_jobs_for_sheets.csv"
FIELDNAMES = ['Job ID', 'Status', 'Title', 'Company', 'Work Location', 'Work Style',
              'Date Applied', 'Date Posted', 'Experience required', 'Apply Link',
              'LinkedIn Job Link', 'About Job (preview)']
PREVIEW_LENGTH = 300


def preview(text: str) -> str:
    '''Collapses the job description to a single trimmed line.'''
    single_line = " ".join((text or "").split())
    return single_line[:PREVIEW_LENGTH] + ("..." if len(single_line) > PREVIEW_LENGTH else "")


def hyperlink(url: str, label: str) -> str:
    '''Wraps a URL as a Sheets HYPERLINK formula, or returns "" when there is no real URL.'''
    url = (url or "").strip()
    if not url.startswith("http"): return ""
    return '=HYPERLINK("{}","{}")'.format(url.replace('"', '%22'), label)


def export() -> None:
    with open(SOURCE_PATH, 'r', encoding='utf-8') as file:
        rows = list(csv.DictReader(file))

    with open(EXPORT_PATH, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            external = (row.get('External Job link') or "").strip()
            writer.writerow({
                'Job ID': row.get('Job ID', ''),
                'Status': row.get('Status', ''),
                'Title': row.get('Title', ''),
                'Company': row.get('Company', ''),
                'Work Location': row.get('Work Location', ''),
                'Work Style': row.get('Work Style', ''),
                'Date Applied': row.get('Date Applied', ''),
                'Date Posted': row.get('Date Posted', ''),
                'Experience required': row.get('Experience required', ''),
                'Apply Link': hyperlink(external, "Apply"),
                'LinkedIn Job Link': hyperlink(row.get('Job Link', ''), "LinkedIn"),
                'About Job (preview)': preview(row.get('About Job', '')),
            })

    print(f"Wrote {len(rows)} rows to {EXPORT_PATH}")


if __name__ == "__main__":
    export()
