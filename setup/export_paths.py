'''
Path layout for the per-run Sheets exports.

The bot runs every 8 hours (3 runs a day), and each run writes one snapshot CSV per export
type into a folder named for that day:

    all excels/
        2026-07-28/
            applied_20260728_000500.csv
            external_20260728_000500.csv
            failed_20260728_000500.csv
            applied_20260728_080500.csv        <- second run of the day
            ...

The filename keeps the full timestamp, not just the time, so a file still identifies itself
if it is moved or attached somewhere. All exports in one run share a single timestamp, so a
trio of files from the same run is easy to spot.
'''

import glob
import os
import re
from datetime import datetime

BASE_DIR = "all excels"
FOLDER_FORMAT = "%Y-%m-%d"
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
# Matches only files these scripts produced, so unrelated CSVs are never picked up.
FILENAME_PATTERN = r"^{prefix}_\d{{8}}_\d{{6}}\.csv$"


def run_folder(moment: datetime) -> str:
    '''Returns the dated folder for a run, creating it if needed.'''
    folder = os.path.join(BASE_DIR, moment.strftime(FOLDER_FORMAT))
    os.makedirs(folder, exist_ok=True)
    return folder


def run_path(prefix: str, moment: datetime) -> str:
    '''Builds the export path for one type within a run, e.g. "failed" -> .../failed_<ts>.csv.'''
    return os.path.join(run_folder(moment), f"{prefix}_{moment.strftime(TIMESTAMP_FORMAT)}.csv")


def parse_run_timestamp(path: str) -> datetime | None:
    '''Recovers the run timestamp from an export filename, or None if the name does not carry one.'''
    match = re.match(r"^[a-z]+_(\d{8}_\d{6})\.csv$", os.path.basename(path))
    return datetime.strptime(match.group(1), TIMESTAMP_FORMAT) if match else None


def folder_name(path: str) -> str:
    '''Returns the dated folder an export lives in, e.g. "2026-07-28".'''
    return os.path.basename(os.path.dirname(path))


def latest_export(prefix: str, date_key: str | None = None) -> str | None:
    '''Finds the newest export of a type, either overall or within one dated folder.

    Both the folder name and the timestamp sort lexicographically, so the greatest path is
    the most recent run. Returns None when that type has never been exported.
    '''
    pattern = re.compile(FILENAME_PATTERN.format(prefix=re.escape(prefix)))
    matches = [path for path in glob.glob(os.path.join(BASE_DIR, date_key or "*", f"{prefix}_*.csv"))
               if pattern.match(os.path.basename(path))]
    return max(matches) if matches else None


def runs_in(date_key: str) -> list[tuple[datetime, dict[str, str]]]:
    '''Groups a day's exports by run, oldest run first.

    Returns [(moment, {"applied": path, "external": path, "failed": path}), ...]. A run with
    a missing type still appears, with only the keys it has, so a partial run stays visible.
    '''
    grouped: dict[datetime, dict[str, str]] = {}
    for path in glob.glob(os.path.join(BASE_DIR, date_key, "*.csv")):
        match = re.match(r"^([a-z]+)_(\d{8}_\d{6})\.csv$", os.path.basename(path))
        if not match: continue
        moment = datetime.strptime(match.group(2), TIMESTAMP_FORMAT)
        grouped.setdefault(moment, {})[match.group(1)] = path
    return sorted(grouped.items())


def date_folders() -> list[str]:
    '''Lists the dated folders that hold exports, oldest first, e.g. ["2026-07-28", ...].'''
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    return sorted(name for name in os.listdir(BASE_DIR)
                  if pattern.match(name) and os.path.isdir(os.path.join(BASE_DIR, name))) \
        if os.path.isdir(BASE_DIR) else []
