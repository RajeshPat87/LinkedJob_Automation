'''
Adds the 'Search Location' column to the existing history CSVs.

runAiBot now records which configured search location produced each job, so the country is
known from the search itself rather than scraped off job card HTML. The header is only
written when a history file is first created, so files written before this change still
carry the old header and would misalign against the new rows. This rewrites them with the
new column appended, blank for rows that predate it.

Safe to run repeatedly: a file that already has the column is left untouched.

    .venv/bin/python3 setup/migrate_add_search_location.py
'''

import csv
import os
import shutil

csv.field_size_limit(1000000)

NEW_COLUMN = 'Search Location'
TARGETS = ("all excels/all_applied_applications_history.csv",
           "all excels/all_failed_applications_history.csv")


def migrate(path: str) -> str:
    '''Appends the new column to one history file. Returns a short status message.'''
    if not os.path.exists(path):
        return f"skipped, file does not exist: {path}"

    with open(path, 'r', encoding='utf-8', newline='') as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        if NEW_COLUMN in fieldnames:
            return f"already migrated: {path}"
        rows = list(reader)

    backup = path + ".pre_search_location.backup"
    shutil.copy2(path, backup)

    with open(path, 'w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames + [NEW_COLUMN])
        writer.writeheader()
        for row in rows:
            # DictReader parks unexpected extra values under None; drop them so the row
            # matches the declared fieldnames exactly.
            row.pop(None, None)
            writer.writerow({**row, NEW_COLUMN: ''})

    return f"migrated {len(rows)} rows, backup at {backup}: {path}"


if __name__ == "__main__":
    for target in TARGETS:
        print(migrate(target))
