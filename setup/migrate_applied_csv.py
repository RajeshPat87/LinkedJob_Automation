'''
One-off migration for `all excels/all_applied_applications_history.csv`.

Adds the `Status` column and repairs the Work Location / Work Style fields that were
mangled by the `other_details.find(' · ') == -1` slicing bug in `get_job_main_details`.
Company names lost their final character to the same bug and cannot be recovered from
the CSV, so they are left as-is rather than guessed at.

Writes a `.backup` copy of the original before touching anything.
'''

import csv
import shutil

csv.field_size_limit(1000000)

CSV_PATH = "all excels/all_applied_applications_history.csv"
FIELDNAMES = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'Status', 'About Job',
              'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume', 'Re-posted',
              'Date Posted', 'Date Applied', 'Job Link', 'External Job link', 'Questions Found',
              'Connect Request']


def is_mangled(company: str, value: str) -> bool:
    '''
    The bug produced Work Location / Work Style as `company[2:]` minus a trailing character,
    so flag any value that is a suffix-slice of the company name.
    '''
    company, value = company.strip(), value.strip()
    if not value: return True
    return len(company) > 2 and company[2:].startswith(value[:max(len(value) - 1, 1)])


def migrate() -> None:
    with open(CSV_PATH, 'r', encoding='utf-8') as file:
        rows = list(csv.DictReader(file))

    shutil.copyfile(CSV_PATH, CSV_PATH + ".backup")
    print(f"Backed up {len(rows)} rows to {CSV_PATH}.backup")

    repaired = 0
    for row in rows:
        link = (row.get('External Job link') or "").strip()
        row['Status'] = "Easy Applied" if link == "Easy Applied" else "External link collected"
        if is_mangled(row.get('Company', ''), row.get('Work Location', '')):
            row['Work Location'] = "Unknown"
            row['Work Style'] = "Unknown"
            repaired += 1

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)

    print(f"Added Status column and cleared {repaired} mangled Work Location / Work Style values")


if __name__ == "__main__":
    migrate()
