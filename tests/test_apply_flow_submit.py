'''
Tests for the AI search apply flow's submit confirmation and choice answers. Run with:
python -m pytest tests   (or `python tests/test_apply_flow_submit.py` if pytest is not installed)
'''

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import apply_flow
from modules.apply_flow import is_sent_confirmation


class FakeElement:
    def __init__(self, text: str = "", displayed: bool = True):
        self.text = text
        self._displayed = displayed
        self.clicks = 0

    def is_displayed(self) -> bool:
        return self._displayed

    def click(self) -> None:
        self.clicks += 1

    def find_elements(self, by, xpath):
        return []


class FakeDriver:
    '''A page whose dialogs change to `after` once the submit button is clicked'''
    def __init__(self, submit: FakeElement, after: list):
        self.submit = submit
        self.after = after
        self.scripts = 0

    def find_elements(self, by, xpath):
        if "dialog" in xpath:
            return self.after if self.submit.clicks else []
        return [] if self.submit.clicks else [self.submit]

    def execute_script(self, script, *args):
        self.scripts += 1


def test_recognises_linkedins_sent_wording():
    assert is_sent_confirmation("Application sent\nYour application was sent to Tata Consultancy Services\nDone")
    assert is_sent_confirmation("Application submitted")
    assert is_sent_confirmation("Your application has been sent")


def test_review_page_and_other_jobs_are_not_a_confirmation():
    assert not is_sent_confirmation("4/4 pages\nReview your application\nSubmit application")
    assert not is_sent_confirmation("DevOps Engineer\nApplied 2 hours ago")
    assert not is_sent_confirmation("")
    assert not is_sent_confirmation(None)


def test_confirmed_when_the_sent_dialog_appears(monkeypatch):
    monkeypatch.setattr(apply_flow.time, "sleep", lambda _: None)
    submit = FakeElement("Submit application")
    driver = FakeDriver(submit, [FakeElement("Your application was sent to Acme\nDone")])
    assert apply_flow.confirm_submitted(driver, submit, timeout=3)
    assert submit.clicks == 1


def test_not_confirmed_when_nothing_is_sent(monkeypatch):
    clock = iter(range(0, 1000))
    monkeypatch.setattr(apply_flow.time, "sleep", lambda _: None)
    monkeypatch.setattr(apply_flow.time, "time", lambda: next(clock))
    submit = FakeElement("Submit application")
    driver = FakeDriver(submit, [FakeElement("4/4 pages\nSubmit application")])
    assert not apply_flow.confirm_submitted(driver, submit, timeout=4)


def _stub_runaibot(monkeypatch):
    # The real module opens Chrome on import
    import types
    stub = types.ModuleType("runAiBot")
    stub.answer_common_questions = lambda label, answer: answer
    stub.resolve_text_answer = lambda *args: ("", False)
    monkeypatch.setitem(sys.modules, "runAiBot", stub)


def test_country_dropdown_gets_the_configured_country(monkeypatch):
    _stub_runaibot(monkeypatch)
    from config.personals import country
    options = ["Select an option", "United States of America", "India"]
    answer, _ = apply_flow._answer_for("Country*", "select", options, "Hyderabad")
    assert answer == country


def test_phone_country_code_is_still_left_alone(monkeypatch):
    _stub_runaibot(monkeypatch)
    assert apply_flow._answer_for("Phone country code*", "select", ["India (+91)"], "Hyderabad") is None



if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
