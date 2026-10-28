'''
Typing answers into LinkedIn's form fields so that they pass its validation on submit.

LinkedIn's forms are React-controlled. Two things went wrong with plain Selenium typing:

* `element.clear()` only empties the DOM value. React keeps its own copy and restores it on the
  next keystroke, so every revisit appended the answer again ("7997282703" x4, "14" -> "1414").
* Numeric questions carry a format and a range ("Enter a whole number between 0 and 99",
  "Enter a decimal number larger than 0.0"). A value outside them passes Next on some pages but
  fails at submit with "We couldn't submit your application".

`replace_text` fixes the first, `fit_to_validation` the second by reading the field's own error
message and adjusting the answer to what it asks for.
'''

import re
import time
from typing import NamedTuple

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from modules.helpers import print_lg

# How often to retry clearing a field React keeps refilling
CLEAR_ATTEMPTS = 3

# Time for React to render a field's validation message after it loses focus
VALIDATION_DELAY = 0.5

_NUMBER = r"(-?\d[\d,]*(?:\.\d+)?)"


class NumberRule(NamedTuple):
    '''What a numeric field accepts, as stated by its validation message'''
    whole: bool                 # "whole number" / "integer", else decimals are allowed
    low: float | None = None
    high: float | None = None
    low_strict: bool = False    # "larger than" excludes the bound, "between" includes it
    high_strict: bool = False


class LengthRule(NamedTuple):
    '''A maximum character count, as stated by a text field's validation message'''
    max_chars: int


##> ------ Parsing validation messages ------

def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def parse_rule(message: str) -> NumberRule | LengthRule | None:
    '''
    Function to turn a LinkedIn validation message into a rule
    * Returns `None` for messages that don't state a format or range ("Please enter a valid answer")
    '''
    text = (message or "").lower()
    if not text: return None

    length = re.search(r"(\d+)\s+characters?\s+or\s+(?:less|fewer)|maximum of\s+(\d+)\s+characters?", text)
    if length: return LengthRule(int(length.group(1) or length.group(2)))

    whole = bool(re.search(r"whole number|integer", text))
    if not (whole or "number" in text or "decimal" in text): return None

    between = re.search(rf"between\s+{_NUMBER}\s+and\s+{_NUMBER}", text)
    if between: return NumberRule(whole, _to_float(between.group(1)), _to_float(between.group(2)))

    low = re.search(rf"(?<!no )(larger|greater|more) than\s+{_NUMBER}|at least\s+{_NUMBER}", text)
    high = re.search(rf"(less|smaller|lower) than\s+{_NUMBER}|at most\s+{_NUMBER}|no more than\s+{_NUMBER}", text)
    # "Enter a valid phone number" names no format or range to fit to
    if not (whole or low or high or "decimal" in text): return None
    return NumberRule(
        whole,
        _to_float(low.group(2) or low.group(3)) if low else None,
        _to_float(high.group(2) or high.group(3) or high.group(4)) if high else None,
        low_strict=bool(low and low.group(1)),
        high_strict=bool(high and high.group(1)),
    )


def _format_number(value: float, whole: bool) -> str:
    if whole: return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fit_value(answer: str, rule: NumberRule | LengthRule) -> str | None:
    '''
    Function to adjust `answer` so it satisfies `rule`
    * Returns the adjusted answer, or `None` when it can't be made to fit (no number in it)
    '''
    if isinstance(rule, LengthRule): return answer[:rule.max_chars]

    found = re.search(_NUMBER, answer or "")
    if not found: return None
    value = _to_float(found.group(1))
    if rule.whole: value = round(value)
    step = 1 if rule.whole else 0.01

    if rule.low is not None:
        floor = rule.low + step if rule.low_strict else rule.low
        value = max(value, floor)
    if rule.high is not None:
        ceiling = rule.high - step if rule.high_strict else rule.high
        value = min(value, ceiling)
    return _format_number(value, rule.whole)


##> ------ Typing into the page ------

def _value(element: WebElement) -> str:
    return element.get_attribute("value") or ""


def replace_text(element: WebElement, text: str) -> bool:
    '''
    Function to replace whatever a text control holds with `text`
    * Select-all + Backspace goes through React's own handlers, unlike `element.clear()`
    * Returns `True` if the control ends up holding exactly `text`
    '''
    for _ in range(CLEAR_ATTEMPTS):
        element.send_keys(Keys.CONTROL, "a")
        element.send_keys(Keys.BACKSPACE)
        if _value(element): continue        # React put the old value back; try again
        if text: element.send_keys(text)
        if _value(element) == text: return True
    return _value(element) == text


# A field's validation message: whatever its aria-describedby points at, else an error element
# near it. Character counters ("3/20") also hang off aria-describedby and are skipped.
_FIELD_ERROR_JS = r"""
const el = arguments[0];
const isCounter = t => /^\d+\s*\/\s*\d+/.test(t) || /^\d+ of \d+ characters/i.test(t);
const isError = t => t && !isCounter(t) &&
    /enter|valid|required|must|between|larger|greater|less|smaller|number|characters/i.test(t);
for (const id of (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean)) {
    const node = document.getElementById(id);
    const text = node ? (node.innerText || '').trim() : '';
    if (isError(text)) return text;
}
let node = el;
for (let i = 0; i < 5 && node; i++) {
    node = node.parentElement;
    if (!node) break;
    const error = node.querySelector('[role=alert], .artdeco-inline-feedback--error, [class*="error"]');
    const text = error ? (error.innerText || '').trim() : '';
    if (isError(text)) return text;
}
return '';
"""


def field_error(driver: WebDriver, element: WebElement) -> str:
    '''
    Function to read the validation message LinkedIn shows for one field, or `""` if none
    '''
    try:
        return driver.execute_script(_FIELD_ERROR_JS, element) or ""
    except Exception as e:
        print_lg("Couldn't read the field's validation message.", e)
        return ""


def fit_to_validation(driver: WebDriver, element: WebElement, answer: str, question: str = "") -> str:
    '''
    Function to retype `answer` if LinkedIn rejects it with a format or range message
    * Blurs the field first, because LinkedIn only validates on blur
    * Returns the answer the field now holds
    '''
    try:
        driver.execute_script("arguments[0].blur();", element)
    except Exception:
        pass
    time.sleep(VALIDATION_DELAY)
    message = field_error(driver, element)
    if not message: return answer

    rule = parse_rule(message)
    fixed = fit_value(answer, rule) if rule else None
    if fixed is None or fixed == answer:
        print_lg(f'LinkedIn rejects "{answer}" for "{question}": {message}')
        return answer

    print_lg(f'"{answer}" is out of range for "{question}" ({message}), using "{fixed}".')
    replace_text(element, fixed)
    return fixed
