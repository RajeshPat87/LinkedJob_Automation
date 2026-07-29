'''
Application pacing helpers.

LinkedIn measures how fast an account submits applications. Once a run crosses that rate
LinkedIn replies with "We noticed you're applying at a fast pace ... we've briefly paused
LinkedIn Apply", and every Easy Apply after that fails until the pause lifts. The bot used
to keep going and record each one as a failure, which both wastes the run and keeps the
account pinned against the safeguard.

This module holds the rate maths (pure functions, no Selenium) plus the page-text match
that recognises the pause notice.
'''

from random import randint
from time import sleep, time as now_seconds
from typing import Callable, Iterable


# Phrases LinkedIn uses in the temporary "applying too fast" notice. Matched against the
# lower-cased page text, so keep every entry lower case.
SOFT_BLOCK_HINTS = (
    "applying at a fast pace",
    "briefly paused linkedin apply",
    "paused linkedin apply",
    "automated inauthentic activities",
    "you can continue shortly",
)

SECONDS_PER_HOUR = 3600


def is_soft_block_text(page_text: str) -> bool:
    '''
    Returns True when `page_text` carries LinkedIn's temporary "applying at a fast pace" notice.
    '''
    if not page_text: return False
    lowered = page_text.lower()
    return any(hint in lowered for hint in SOFT_BLOCK_HINTS)


def gap_wait_seconds(last_application_at: float | None, now: float, min_gap: int, max_gap: int) -> float:
    '''
    Seconds still to wait before the next submission, given a random target gap in
    [`min_gap`, `max_gap`] since `last_application_at`. Returns 0 when nothing was applied yet.
    '''
    if last_application_at is None or max_gap <= 0: return 0.0
    target = randint(min(min_gap, max_gap), max_gap)
    return max(0.0, target - (now - last_application_at))


def hourly_cap_wait_seconds(timestamps: Iterable[float], now: float, cap: int) -> float:
    '''
    Seconds to wait for the rolling-hour budget to free a slot. `cap` of 0 disables the cap.
    Waits until the oldest submission in the current hour ages out.
    '''
    if cap <= 0: return 0.0
    recent = sorted(stamp for stamp in timestamps if now - stamp < SECONDS_PER_HOUR)
    if len(recent) < cap: return 0.0
    return max(0.0, SECONDS_PER_HOUR - (now - recent[len(recent) - cap]))


class ApplicationPacer:
    '''
    Tracks submission times and blocks until the configured gap and hourly cap allow the
    next one. `clock` and `sleeper` are injectable so the pacing can be tested without
    real waits.
    '''

    def __init__(self, min_gap: int, max_gap: int, hourly_cap: int,
                 clock: Callable[[], float] = now_seconds,
                 sleeper: Callable[[float], None] = sleep,
                 announce: Callable[[str], None] = print) -> None:
        self.min_gap = max(0, min_gap)
        self.max_gap = max(self.min_gap, max_gap)
        self.hourly_cap = max(0, hourly_cap)
        self.clock = clock
        self.sleeper = sleeper
        self.announce = announce
        self.timestamps: tuple[float, ...] = ()

    @property
    def last_application_at(self) -> float | None:
        return self.timestamps[-1] if self.timestamps else None

    def record_application(self) -> None:
        '''Marks a submission as just completed.'''
        self.timestamps = self.timestamps + (self.clock(),)

    def wait_for_slot(self) -> float:
        '''
        Sleeps until the next application is allowed. Returns the seconds waited.
        '''
        now = self.clock()
        gap_wait = gap_wait_seconds(self.last_application_at, now, self.min_gap, self.max_gap)
        cap_wait = hourly_cap_wait_seconds(self.timestamps, now, self.hourly_cap)
        wait = max(gap_wait, cap_wait)
        if wait <= 0: return 0.0
        reason = "hourly cap of {} applications".format(self.hourly_cap) if cap_wait >= gap_wait else "pacing between applications"
        self.announce("Waiting {} secs before the next application ({}).".format(round(wait), reason))
        self.sleeper(wait)
        return wait
