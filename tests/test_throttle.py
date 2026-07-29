'''
Tests for the application pacing helpers. Run with:  python -m pytest tests
(or `python tests/test_throttle.py` if pytest is not installed)
'''

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.throttle import (ApplicationPacer, SECONDS_PER_HOUR, gap_wait_seconds,
                              hourly_cap_wait_seconds, is_soft_block_text)


LINKEDIN_NOTICE = ("We noticed you're applying at a fast pace. To ensure genuine applications get the "
                   "attention they deserve, we've briefly paused LinkedIn Apply as a safeguard against "
                   "automated inauthentic activities. You can continue shortly.")


def test_recognises_linkedin_fast_pace_notice():
    assert is_soft_block_text(LINKEDIN_NOTICE)


def test_ignores_ordinary_job_page_text():
    assert not is_soft_block_text("Senior DevOps Engineer - Easy Apply - Posted 3 hours ago")
    assert not is_soft_block_text("")


def test_no_gap_wait_before_the_first_application():
    assert gap_wait_seconds(None, now=1000.0, min_gap=45, max_gap=120) == 0


def test_gap_wait_is_within_configured_range():
    wait = gap_wait_seconds(last_application_at=1000.0, now=1000.0, min_gap=45, max_gap=120)
    assert 45 <= wait <= 120


def test_gap_wait_shrinks_by_time_already_elapsed():
    assert gap_wait_seconds(last_application_at=1000.0, now=1200.0, min_gap=45, max_gap=120) == 0


def test_hourly_cap_of_zero_never_waits():
    assert hourly_cap_wait_seconds([1.0, 2.0, 3.0], now=4.0, cap=0) == 0


def test_hourly_cap_waits_for_oldest_application_to_age_out():
    stamps = [1000.0, 1100.0, 1200.0]
    assert hourly_cap_wait_seconds(stamps, now=1300.0, cap=3) == SECONDS_PER_HOUR - 300
    assert hourly_cap_wait_seconds(stamps, now=1300.0, cap=4) == 0


def test_hourly_cap_ignores_applications_older_than_an_hour():
    stamps = [0.0, 10.0, 5000.0]
    assert hourly_cap_wait_seconds(stamps, now=5000.0, cap=2) == 0


def _pacer(**kwargs):
    clock = {"t": 0.0}
    slept = []

    def sleeper(secs):
        slept.append(secs)
        clock["t"] += secs

    pacer = ApplicationPacer(clock=lambda: clock["t"], sleeper=sleeper, announce=lambda _: None, **kwargs)
    return pacer, clock, slept


def test_pacer_does_not_wait_before_the_first_application():
    pacer, _, slept = _pacer(min_gap=45, max_gap=120, hourly_cap=15)
    assert pacer.wait_for_slot() == 0
    assert slept == []


def test_pacer_waits_between_consecutive_applications():
    pacer, _, slept = _pacer(min_gap=45, max_gap=45, hourly_cap=0)
    pacer.record_application()
    assert pacer.wait_for_slot() == 45
    assert slept == [45]


def test_pacer_enforces_the_hourly_cap():
    pacer, clock, _ = _pacer(min_gap=0, max_gap=0, hourly_cap=2)
    pacer.record_application()
    clock["t"] += 10
    pacer.record_application()
    waited = pacer.wait_for_slot()
    assert waited == SECONDS_PER_HOUR - 10


def test_pacer_keeps_a_full_history_of_submissions():
    pacer, clock, _ = _pacer(min_gap=0, max_gap=0, hourly_cap=0)
    pacer.record_application()
    clock["t"] += 5
    pacer.record_application()
    assert len(pacer.timestamps) == 2
    assert pacer.last_application_at == 5.0


if __name__ == "__main__":
    failures = 0
    for name, test in sorted(globals().copy().items()):
        if not name.startswith("test_") or not callable(test): continue
        try:
            test()
            print("PASS", name)
        except AssertionError as e:
            failures += 1
            print("FAIL", name, e)
    print("\n{} failed".format(failures) if failures else "\nAll tests passed")
    sys.exit(1 if failures else 0)
