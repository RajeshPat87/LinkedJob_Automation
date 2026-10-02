'''
Tests for the classic Easy Apply modal helpers. Run with:  python -m pytest tests
(or `python tests/test_easy_apply_steps.py` if pytest is not installed)
'''

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.linkedin_ui import find_modal_step_button, pick_phone_country_option


class FakeButton:
    def __init__(self, text: str = "", aria_label: str = "", displayed: bool = True):
        self.text = text
        self._aria_label = aria_label
        self._displayed = displayed

    def is_displayed(self) -> bool:
        return self._displayed

    def get_attribute(self, name: str):
        return self._aria_label if name == "aria-label" else None


class FakeModal:
    def __init__(self, buttons: list):
        self._buttons = buttons

    def find_elements(self, by, xpath):
        return list(self._buttons)


COUNTRY_CODES = ["Andorra (+376)", "British Indian Ocean Territory (+246)", "India (+91)", "Indonesia (+62)"]


def test_picks_the_country_from_the_phone_code_list():
    assert pick_phone_country_option(COUNTRY_CODES, "India") == "India (+91)"


def test_country_match_ignores_case_and_similar_names():
    assert pick_phone_country_option(COUNTRY_CODES, "india") == "India (+91)"
    assert pick_phone_country_option(["British Indian Ocean Territory (+246)"], "India") is None


def test_no_country_or_no_match_gives_none():
    assert pick_phone_country_option(COUNTRY_CODES, "") is None
    assert pick_phone_country_option(COUNTRY_CODES, "Wakanda") is None


def test_prefers_review_over_next():
    modal = FakeModal([FakeButton("Next"), FakeButton("Review")])
    assert find_modal_step_button(modal, timeout=0).text == "Review"


def test_finds_next_whatever_the_inner_markup():
    modal = FakeModal([FakeButton("Back"), FakeButton("  Next \n")])
    assert find_modal_step_button(modal, timeout=0).text.strip() == "Next"


def test_falls_back_to_aria_label():
    button = FakeButton("", aria_label="Continue to next step")
    assert find_modal_step_button(FakeModal([button]), timeout=0) is button


def test_never_returns_submit_or_hidden_buttons():
    modal = FakeModal([FakeButton("Submit application"), FakeButton("Next", displayed=False),
                       FakeButton("Next steps")])
    assert find_modal_step_button(modal, timeout=0) is None


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"): test()
    print("All tests passed")
