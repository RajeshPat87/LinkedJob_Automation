'''
Derives a country from a job's location text and ranks it by search priority.

The priority order comes from `search_locations` in config/search.py, so the ranking in the
spreadsheet always matches the order the bot actually searches in. LinkedIn location strings
are inconsistent ("Bengaluru, Karnataka, India", "Dubai", "Greater Tokyo Area", "Remote"),
so matching is done on country names first, then on major-city hints.
'''

import os
import sys

# Import the search config the same way the bot does, whichever directory this is run from.
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
try:
    from config.search import search_locations
except ImportError:
    search_locations = []

UNKNOWN = "Unknown"

# Alternative spellings and abbreviations that mean the same country.
COUNTRY_ALIASES = {
    'India': ('india', 'bharat'),
    'United Arab Emirates': ('united arab emirates', 'uae', 'u.a.e', 'emirates'),
    'Singapore': ('singapore',),
    'Netherlands': ('netherlands', 'holland', 'nederland'),
    'Australia': ('australia',),
    'Japan': ('japan', 'nippon'),
}

# Major cities and regions, used when the location text names no country at all.
CITY_HINTS = {
    'India': ('bengaluru', 'bangalore', 'hyderabad', 'mumbai', 'pune', 'chennai', 'delhi',
              'noida', 'gurugram', 'gurgaon', 'kolkata', 'ahmedabad', 'kochi', 'cochin',
              'trivandrum', 'thiruvananthapuram', 'coimbatore', 'indore', 'jaipur',
              'chandigarh', 'nagpur', 'bhubaneswar', 'mysuru', 'mysore', 'vizag',
              'visakhapatnam', 'karnataka', 'maharashtra', 'telangana', 'tamil nadu',
              'kerala', 'gujarat', 'haryana', 'uttar pradesh'),
    'United Arab Emirates': ('dubai', 'abu dhabi', 'sharjah', 'ajman', 'ras al khaimah',
                             'fujairah', 'umm al quwain'),
    'Singapore': ('singapore river', 'jurong', 'tampines', 'woodlands'),
    'Netherlands': ('amsterdam', 'rotterdam', 'utrecht', 'eindhoven', 'the hague',
                    'den haag', 'groningen', 'tilburg', 'almere', 'breda', 'nijmegen',
                    'haarlem', 'amstelveen', 'delft', 'leiden'),
    'Australia': ('sydney', 'melbourne', 'brisbane', 'perth', 'adelaide', 'canberra',
                  'hobart', 'darwin', 'gold coast', 'new south wales', 'victoria',
                  'queensland'),
    'Japan': ('tokyo', 'osaka', 'yokohama', 'nagoya', 'fukuoka', 'sapporo', 'kyoto',
              'kobe', 'kawasaki', 'saitama', 'chiba', 'sendai'),
}


def priority_order() -> list[str]:
    '''Returns the configured country priority, falling back to the known countries.'''
    return list(search_locations) if search_locations else list(COUNTRY_ALIASES)


def country_of(location: str) -> str:
    '''Maps a LinkedIn location string to a country, or "Unknown" when nothing matches.

    Country names win over city hints, so "Sydney, Australia" and a bare "Sydney" both
    resolve to Australia while "Remote" stays Unknown rather than guessing.
    '''
    text = (location or "").strip().lower()
    if not text or text in ('unknown', 'remote', 'n/a'):
        return UNKNOWN

    for country, aliases in COUNTRY_ALIASES.items():
        if any(alias in text for alias in aliases):
            return country
    for country, cities in CITY_HINTS.items():
        if any(city in text for city in cities):
            return country
    return UNKNOWN


def country_for_row(row: dict) -> str:
    '''Resolves a history row's country, preferring the scraped location.

    Falls back to the search location the bot used, which is authoritative: a job returned
    by an "India" search is an India job. That fallback is what keeps the country populated
    when LinkedIn renames the job card element the location is scraped from.
    '''
    scraped = country_of(row.get('Work Location', ''))
    if scraped != UNKNOWN:
        return scraped
    return country_of(row.get('Search Location', ''))


def priority_of(country: str) -> int:
    '''Ranks a country by search priority: 1 is highest. Unknown countries sort last.'''
    order = priority_order()
    try:
        return order.index(country) + 1
    except ValueError:
        return len(order) + 1


def sort_key(country: str, fallback: str = "") -> tuple[int, str]:
    '''Sort key placing higher priority countries first, then a stable tie breaker.'''
    return (priority_of(country), fallback or "")
