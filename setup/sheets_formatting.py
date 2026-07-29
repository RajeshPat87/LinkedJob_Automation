'''
Shared helpers for building Google Sheets ready CSV exports from the bot's history files.

The raw history CSVs carry full job descriptions and stack traces (thousands of characters
per cell), which makes them unreadable in a spreadsheet. These helpers trim long text,
normalise the microsecond timestamps, and turn URLs into clickable HYPERLINK formulas.
'''

import csv
from typing import Iterable

csv.field_size_limit(1000000)

PLACEHOLDERS = frozenset({"", "unknown", "pending", "skipped", "not available", "none", "n/a"})


def read_rows(path: str) -> list[dict[str, str]]:
    '''Reads a history CSV into a list of dicts. Returns [] when the file does not exist yet.'''
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return list(csv.DictReader(file))
    except FileNotFoundError:
        return []


def write_rows(path: str, fieldnames: Iterable[str], rows: Iterable[dict[str, str]]) -> int:
    '''Writes rows to a CSV with the given header. Returns the number of data rows written.'''
    written = 0
    with open(path, 'w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            written += 1
    return written


def is_real_value(value: str) -> bool:
    '''True when a cell holds actual data rather than one of the bot's placeholder strings.'''
    return (value or "").strip().lower() not in PLACEHOLDERS


def is_url(value: str) -> bool:
    '''True when a cell holds an http(s) URL.'''
    return (value or "").strip().startswith("http")


def preview(text: str, length: int = 300) -> str:
    '''Collapses a long text block to a single trimmed line.'''
    single_line = " ".join((text or "").split())
    return single_line[:length] + ("..." if len(single_line) > length else "")


def hyperlink(url: str, label: str) -> str:
    '''Wraps a URL as a Sheets HYPERLINK formula, or returns "" when there is no real URL.'''
    url = (url or "").strip()
    if not is_url(url): return ""
    return '=HYPERLINK("{}","{}")'.format(url.replace('"', '%22'), label)


def clean_date(value: str) -> str:
    '''Drops microseconds from the bot's ISO timestamps so Sheets parses them as dates.'''
    value = (value or "").strip()
    if not is_real_value(value): return ""
    return value.split(".")[0]


def domain_of(url: str) -> str:
    '''Extracts the host from a URL, used to label which portal an external apply link points at.'''
    if not is_url(url): return ""
    host = url.split("//", 1)[1].split("/", 1)[0]
    return host[4:] if host.startswith("www.") else host
