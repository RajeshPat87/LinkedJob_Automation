'''
Tests for typing answers into LinkedIn's React forms and fitting them to its validation. Run with:
python -m pytest tests   (or `python tests/test_form_values.py` if pytest is not installed)
'''

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.keys import Keys

from modules import form_values
from modules.form_values import LengthRule, NumberRule, fit_value, parse_rule, replace_text


class ReactInput:
    '''A React-controlled input: clear() empties only the DOM, the next keystroke restores React's copy'''
    def __init__(self, value: str = ""):
        self.dom = value
        self.react = value
        self._selected = False

    def clear(self) -> None:
        self.dom = ""

    def get_attribute(self, name):
        return self.dom if name == "value" else None

    def send_keys(self, *keys) -> None:
        if keys == (Keys.CONTROL, "a"):
            self._selected = True
        elif keys == (Keys.BACKSPACE,):
            self.react = "" if self._selected else self.react[:-1]
            self._selected = False
        else:
            self.react = self.react + "".join(keys)
        self.dom = self.react


class FakeDriver:
    '''Shows `errors` in order as the field's validation message, one per read'''
    def __init__(self, *errors: str):
        self.errors = list(errors)

    def execute_script(self, script, *args):
        if "blur" in script: return None
        return self.errors.pop(0) if self.errors else ""


##> ------ replace_text ------

def test_clear_then_type_reproduces_the_bug():
    box = ReactInput("14")
    box.clear()
    box.send_keys("14")
    assert box.get_attribute("value") == "1414"


def test_replace_text_does_not_append_to_react_value():
    box = ReactInput("7997282703")
    assert replace_text(box, "7997282703")
    assert box.get_attribute("value") == "7997282703"


def test_replace_text_overwrites_prefilled_answer():
    box = ReactInput("3")
    assert replace_text(box, "14")
    assert box.get_attribute("value") == "14"


def test_replace_text_with_empty_text_empties_the_field():
    box = ReactInput("old")
    assert replace_text(box, "")
    assert box.get_attribute("value") == ""


##> ------ parse_rule ------

def test_parses_whole_number_range():
    assert parse_rule("Enter a whole number between 0 and 99") == NumberRule(True, 0, 99)


def test_parses_strict_decimal_lower_bound():
    assert parse_rule("Enter a decimal number larger than 0.0") == NumberRule(False, 0.0, None, low_strict=True)


def test_parses_thousands_separators():
    assert parse_rule("Enter a decimal number between 0 and 99,999,999") == NumberRule(False, 0, 99999999)


def test_no_more_than_is_an_upper_bound():
    assert parse_rule("Enter a whole number no more than 50") == NumberRule(True, None, 50)


def test_parses_character_limit():
    assert parse_rule("Must be 20 characters or less") == LengthRule(20)


def test_messages_without_a_rule_are_ignored():
    assert parse_rule("Please enter a valid answer") is None
    assert parse_rule("Enter a valid phone number") is None
    assert parse_rule("") is None


##> ------ fit_value ------

def test_whole_number_drops_the_decimal():
    assert fit_value("32.0", NumberRule(True, 0, 99)) == "32"


def test_value_is_clamped_into_range():
    assert fit_value("40", NumberRule(True, 0, 30)) == "30"
    assert fit_value("0", NumberRule(False, 0.0, None, low_strict=True)) == "0.01"
    assert fit_value("15", NumberRule(True, None, 10, high_strict=True)) == "9"


def test_decimal_keeps_fraction():
    assert fit_value("32.5", NumberRule(False, 0, 100)) == "32.5"


def test_text_without_a_number_cannot_be_fitted():
    assert fit_value("Immediately", NumberRule(True, 0, 99)) is None


def test_text_is_cut_to_the_character_limit():
    assert fit_value("abcdefgh", LengthRule(5)) == "abcde"


##> ------ fit_to_validation ------

def test_valid_answer_is_left_alone(monkeypatch):
    monkeypatch.setattr(form_values, "VALIDATION_DELAY", 0)
    box = ReactInput("14")
    assert form_values.fit_to_validation(FakeDriver(""), box, "14", "Years?") == "14"
    assert box.get_attribute("value") == "14"


def test_rejected_answer_is_retyped_to_fit(monkeypatch):
    monkeypatch.setattr(form_values, "VALIDATION_DELAY", 0)
    box = ReactInput("32.0")
    driver = FakeDriver("Enter a whole number between 0 and 99")
    assert form_values.fit_to_validation(driver, box, "32.0", "Salary?") == "32"
    assert box.get_attribute("value") == "32"


def test_unfixable_answer_is_kept(monkeypatch):
    monkeypatch.setattr(form_values, "VALIDATION_DELAY", 0)
    box = ReactInput("abc")
    driver = FakeDriver("Please enter a valid answer")
    assert form_values.fit_to_validation(driver, box, "abc", "Question?") == "abc"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
