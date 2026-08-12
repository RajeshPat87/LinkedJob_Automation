'''
Driver for LinkedIn AI search's apply flow.

The classic Easy Apply modal (`.artdeco-modal` + `div[data-test-form-element]` questions) does
not exist on accounts moved to the AI job search. The replacement is an inline 5-page dialog:

    page 1  Contact info      email / phone country code / mobile number
    page 2  Resume            one radio per stored resume, plus an upload control
    page 3  Top choice        an optional checkbox
    page 4  Additional Q's    free text and Yes/No radio groups
    page 5  Review            "Submit application"

Its form controls carry React generated ids (`«r2q»`) that change on every render, so controls
are matched by their question text instead. Verified against the live site on 2026-08-12.
'''

import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select

from modules.helpers import print_lg
from modules.linkedin_ui import apply_progress, find_apply_dialog, find_step_button

# Safety net: the flow is only ever submitted through submit_application(), never by the
# page-advancing loop. Any button whose text matches this is refused everywhere else.
SUBMIT_TEXT = "submit application"

# Guard against an unexpected page looping forever without ever reaching Review.
MAX_PAGES = 12

# A dropdown's leading "choose something" entry, which is never a valid answer.
PLACEHOLDER_OPTION = re.compile(r"^\s*(select an option|select\.\.\.|select|choose|-+|)\s*$", re.I)


##> ------ Reading the form ------

# For each visible control, find the text that acts as its question. `label[for]` works on the
# contact page; the questions page has no such label, so the nearest ancestor line that looks
# like a prompt is used. Character counters ("0/20") and the option labels of a radio group
# ("Yes"/"No") are explicitly rejected - both otherwise win over the real question.
_READ_FORM_JS = r"""
const root = arguments[0];
if (!root) return [];

const isCounter = t => /^\d+\s*\/\s*\d+/.test(t) || /^\d+ of \d+ characters/.test(t);
const isOption  = t => /^(yes|no|next|back|review|submit application|discard|dismiss)$/i.test(t);

function questionFor(el) {
    if (el.id) {
        const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
        if (l && (l.innerText || '').trim()) return (l.innerText || '').trim();
    }
    let node = el;
    for (let i = 0; i < 8 && node; i++) {
        node = node.parentElement;
        if (!node) break;
        const lines = (node.innerText || '').split('\n').map(s => s.trim()).filter(Boolean);
        const cand = lines.find(t => !isCounter(t) && !isOption(t) &&
                                     (/[?*]$/.test(t) || t.length > 12));
        if (cand) return cand;
    }
    return '';
}

const out = [];
const seenGroups = new Set();
for (const el of root.querySelectorAll('input, select, textarea')) {
    if (el.offsetParent === null || el.type === 'hidden') continue;
    if (el.type === 'radio') {
        // report the group once, with all of its options
        const group = el.closest('[role=radiogroup], fieldset') || el.parentElement;
        if (!group || seenGroups.has(group)) continue;
        seenGroups.add(group);
        const radios = [...group.querySelectorAll('input[type=radio]')];
        out.push({kind: 'radio', question: questionFor(group.firstElementChild || group),
                  // The options carry no label[for] and no useful value - "Yes"/"No" is only
                  // present as the text of a wrapper a couple of levels up from the input.
                  options: radios.map(r => {
                      const l = r.id ? document.querySelector(`label[for="${CSS.escape(r.id)}"]`) : null;
                      let t = l ? (l.innerText || '').trim() : '';
                      if (!t) { const w = r.closest('label'); t = w ? (w.innerText || '').trim() : ''; }
                      if (!t) {
                          let n = r;
                          for (let i = 0; i < 4 && n; i++) {
                              n = n.parentElement;
                              if (!n) break;
                              const tt = (n.innerText || '').trim();
                              if (tt && tt.length < 40 && !tt.includes('\n')) { t = tt; break; }
                          }
                      }
                      return t;
                  }),
                  checked: radios.findIndex(r => r.checked),
                  elements: radios});
        continue;
    }
    out.push({
        kind: el.tagName === 'SELECT' ? 'select'
            : el.type === 'checkbox' ? 'checkbox'
            : el.tagName === 'TEXTAREA' ? 'textarea'
            : el.type === 'file' ? 'file' : 'text',
        question: questionFor(el),
        options: el.tagName === 'SELECT' ? [...el.options].map(o => o.text.trim()) : [],
        value: el.value || '',
        required: el.required || el.getAttribute('aria-required') === 'true',
        elements: [el]
    });
}
return out;
"""


def read_form(driver: WebDriver, dialog: WebElement) -> list[dict]:
    '''
    Function to read every answerable control on the current apply page
    * Returns a list of dicts: kind, question, options, value, required, elements
    '''
    try:
        return driver.execute_script(_READ_FORM_JS, dialog) or []
    except Exception as e:
        print_lg("Couldn't read the apply form.", e)
        return []


def page_heading(dialog: WebElement) -> str:
    '''
    Function to read which page of the apply flow is open, e.g. "2/5 pages - Resume"
    '''
    try:
        lines = [line.strip() for line in (dialog.text or "").split("\n") if line.strip()]
    except Exception:
        return "Unknown"
    pages = next((line for line in lines if re.fullmatch(r"\d+/\d+ pages", line)), "")
    section = ""
    if pages and pages in lines:
        index = lines.index(pages)
        if index + 1 < len(lines): section = lines[index + 1]
    return f"{pages} - {section}".strip(" -") or (lines[0] if lines else "Unknown")


##> ------ Answering ------

def _answer_for(question: str, kind: str, options: list[str], work_location: str,
                job_description: str | None = None) -> tuple[str, bool] | None:
    '''
    Function to decide what to answer for one question
    * Reuses `runAiBot.resolve_text_answer`, so the years-of-experience, notice period, salary
      and AI-fallback rules behave exactly as they do on the classic Easy Apply modal - a
      second copy of them here would answer "Yes" into numeric fields and stall the flow
    * Imported lazily because runAiBot imports this module
    * Returns a tuple of (answer, needs_typeahead), or `None` to leave the control untouched
    * `needs_typeahead` marks the location fields that only accept a value picked from their
      own dropdown - typing into them leaves the form invalid and Next is silently refused
    '''
    from runAiBot import resolve_text_answer, answer_common_questions
    from config.personals import gender, disability_status

    label_org = (question or "").strip().rstrip('*').strip()
    label = label_org.lower()
    if not label: return None

    # LinkedIn prefills these from the verified profile; overwriting them breaks the flow
    if 'email' in label or 'phone country code' in label: return None
    needs_typeahead = False

    if kind in ('radio', 'select'):
        # Choice questions have their own small ruleset in the classic UI; free-text rules like
        # "answer 5 for years of experience" must not be applied to a Yes/No group.
        if 'gender' in label or 'sex' in label: answer = gender
        elif 'disability' in label: answer = disability_status
        elif 'proficiency' in label: answer = 'Professional'
        else: answer = answer_common_questions(label, 'Yes')
    else:
        answer, needs_typeahead = resolve_text_answer(label, label_org, work_location, job_description)
        if not answer: return None

    if kind in ('radio', 'select') and options:
        # Snap the answer onto an offered option, bidirectionally: "Yes" must match "Yes, I do"
        for option in options:
            if not option: continue
            if answer.lower() == option.lower(): return option, needs_typeahead
        for option in options:
            if not option: continue
            if answer.lower() in option.lower() or option.lower() in answer.lower():
                return option, needs_typeahead
    return answer, needs_typeahead


def fill_control(driver: WebDriver, field: dict, work_location: str,
                 randomly_answered: set | None = None,
                 job_description: str | None = None) -> tuple[str, str] | None:
    '''
    Function to answer one control on the apply page
    * Takes in `field` of type `dict` - one entry from `read_form`
    * Returns a tuple of (question, answer) for the applications log, or `None` when skipped
    '''
    kind, question = field.get('kind'), (field.get('question') or "").strip()
    elements = field.get('elements') or []
    if not elements: return None
    options = [option for option in (field.get('options') or []) if option]

    resolved = _answer_for(question, kind, options, work_location, job_description)
    if resolved is None: return None
    answer, needs_typeahead = resolved

    try:
        if kind == 'select':
            select = Select(elements[0])
            try:
                select.select_by_visible_text(answer)
            except Exception:
                match = next((option for option in options
                              if answer.lower() in option.lower() or option.lower() in answer.lower()), None)
                if not match:
                    # A required select left on its placeholder makes LinkedIn refuse Review
                    # without saying why, so fall back the way the classic modal does: take the
                    # first real option and flag it as guessed.
                    if not field.get('required'):
                        print_lg(f'No option matching "{answer}" for "{question}", leaving it as is.')
                        if randomly_answered is not None: randomly_answered.add((question, "select"))
                        return None
                    real = [option for option in options
                            if option and not PLACEHOLDER_OPTION.match(option)]
                    if not real:
                        print_lg(f'"{question}" offers no answerable option, leaving it as is.')
                        return None
                    match = real[0]
                    print_lg(f'No option matching "{answer}" for required question "{question}", '
                             f'answering "{match}".')
                    if randomly_answered is not None: randomly_answered.add((question, "select"))
                select.select_by_visible_text(match)
                answer = match

        elif kind == 'radio':
            index = next((i for i, option in enumerate(field.get('options') or [])
                          if option and (answer.lower() == option.lower()
                                         or answer.lower() in option.lower())), None)
            if index is None or index >= len(elements):
                print_lg(f'No option matching "{answer}" for "{question}", leaving it unanswered.')
                if randomly_answered is not None: randomly_answered.add((question, "radio"))
                return None
            driver.execute_script("arguments[0].click();", elements[index])
            answer = (field.get('options') or [])[index]

        elif kind == 'checkbox':
            return None     # every checkbox seen so far is optional ("Mark job as a top choice")

        elif kind in ('text', 'textarea'):
            if field.get('value') and not field.get('required'): return None
            element = elements[0]
            element.clear()
            element.send_keys(str(answer))
            if needs_typeahead:
                # A location field only accepts a value chosen from its own suggestions; typed
                # text leaves the form invalid and LinkedIn then refuses Next without saying why
                time.sleep(2)
                element.send_keys(Keys.ARROW_DOWN)
                element.send_keys(Keys.ENTER)
                time.sleep(1)

        else:
            return None
    except Exception as e:
        print_lg(f'Failed to answer "{question}".', e)
        return None

    return question, str(answer)


##> ------ Resume page ------

def choose_resume(driver: WebDriver, dialog: WebElement, resume_name: str | None = None) -> str:
    '''
    Function to pick a resume on the apply flow's resume page
    * Takes in `resume_name` of type `str` - preferred file name, matched case-insensitively
    * LinkedIn preselects the most recent resume, so doing nothing is already valid; this only
      overrides that when a preferred name is configured and offered
    * Returns the resume that will be sent, or "Previously Uploaded" when left as LinkedIn set it
    '''
    if not resume_name: return "Previously Uploaded"
    wanted = resume_name.lower().strip()
    for button in dialog.find_elements(By.XPATH, ".//button | .//*[@role='radio'] | .//input[@type='radio']"):
        try:
            text = (button.text or button.get_attribute('aria-label') or "").lower()
        except Exception:
            continue
        if wanted and wanted in text:
            try:
                driver.execute_script("arguments[0].click();", button)
                print_lg(f'Selected resume "{resume_name}".')
                return resume_name
            except Exception:
                break
    return "Previously Uploaded"


##> ------ Walking the flow ------

def advance(driver: WebDriver, dialog: WebElement) -> tuple[bool, str]:
    '''
    Function to move the apply flow on by one page
    * Clicks Next, or Review on the last question page
    * Returns a tuple of (advanced, button that was clicked)
    * `advanced` is decided by the progress bar moving, not by the click succeeding: LinkedIn
      rejects Next when a required answer is missing and leaves the page looking identical
    '''
    button = find_step_button(dialog, "Next", "Review", "Continue")
    if not button: return False, ""
    label = (button.text or "").strip()
    before = apply_progress(driver)
    try:
        driver.execute_script("arguments[0].click();", button)
    except Exception as e:
        print_lg("Couldn't click the apply flow's next button.", e)
        return False, label
    time.sleep(3)
    after = apply_progress(driver)
    # Review keeps progress at 100, so treat reaching the submit page as advancing too
    if after is not None and before is not None and after > before: return True, label
    return submit_button(driver) is not None, label


def submit_button(driver: WebDriver) -> WebElement | None:
    '''
    Function to find the apply flow's real submit button
    * Matched on exact text so no other control can ever be mistaken for it
    '''
    for button in driver.find_elements(By.XPATH, "//button"):
        try:
            if button.is_displayed() and (button.text or "").strip().lower() == SUBMIT_TEXT:
                return button
        except Exception:
            continue
    return None


def discard(driver: WebDriver) -> bool:
    '''
    Function to close a part-filled apply flow without applying
    * Returns True when nothing is left open
    '''
    for xpath in ("//button[contains(@aria-label, 'Dismiss')]",
                  "//button[normalize-space()='Discard']",
                  "//button[normalize-space()='Exit']"):
        for button in driver.find_elements(By.XPATH, xpath):
            try:
                if not button.is_displayed(): continue
                driver.execute_script("arguments[0].click();", button)
                time.sleep(1.5)
            except Exception:
                continue
    return find_apply_dialog(driver) is None
