'''
LinkedIn UI compatibility layer.

LinkedIn is rolling out an AI ("semantic") job search per account. On accounts that have it,
`/jobs/search/` redirects to `/jobs/search-results/` and the entire job markup changes:

* every CSS class is build-hashed (`_13c144a3`) and regenerates on each LinkedIn deploy, so a
  class name is never a safe selector - `componentkey`, `id` and `aria-label` are the durable hooks
* the `location` query parameter is silently discarded; the new UI keys off a numeric `geoId`
* job cards carry no anchor and no `data-job-id`, and each card is rendered twice
* the Easy Apply modal is gone; the apply flow is an inline 5-page dialog anchored on `#dialog-header`

Every selector here was verified against the live site on 2026-08-12, not guessed. The classic
markup is still handled throughout, so this module works on accounts on either rollout.
'''

import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement

from modules.clickers_and_finders import scroll_to_view
from modules.helpers import print_lg


##> ------ Search URL ------

# The AI search drops `location` and resolves places by numeric geoId instead. Each ID below was
# verified by loading the search and confirming the location pill echoed the expected place.
#
# To add a location: run the search on linkedin.com with that location selected and copy the
# `geoId=` value out of the address bar, or run `python setup/resolve_geo_ids.py`.
GEO_IDS = {
    "india": "102713980",
    "united arab emirates": "104305776",
    "singapore": "102454443",
    "netherlands": "102890719",
    "australia": "101452733",
    "japan": "101355337",
    "united states": "103644278",
    "united kingdom": "101165590",
    "canada": "101174742",
    "germany": "101282230",
}


def resolve_geo_id(location: str) -> str | None:
    '''
    Function to map a configured location name to the geoId the AI search needs
    * Takes in `location` of type `str` - the location as written in config/search.py
    * Returns the geoId, or `None` when the location isn't in `GEO_IDS`
    '''
    return GEO_IDS.get((location or "").strip().lower())


##> ------ Which UI is being served ------

NEW_UI_PATH = "/jobs/search-results"


def is_new_ui(driver: WebDriver) -> bool:
    '''
    Function to detect LinkedIn's AI job search
    * Returns True when the browser landed on the new search results page

    Checked per search rather than once per run: the rollout is applied server side and a
    session can be served either UI.
    '''
    try:
        return NEW_UI_PATH in driver.current_url
    except Exception:
        return False


##> ------ Job cards ------

# Prefix of the AI search card's componentkey; the remainder is the job id.
JOB_CARD_COMPONENT_PREFIX = "job-card-component-ref-"

# Known containers for one job card, newest first. Waiting on a single hard coded selector meant
# one LinkedIn rename made every search time out with nothing to go on.
JOB_CARD_SELECTORS = (
    "//*[starts-with(@componentkey, 'job-card-component-ref-')]",
    "//li[@data-occludable-job-id]",
    "//li[.//div[@data-job-id]]",
    "//div[@data-job-id and contains(@class, 'job-card-container')]",
    "//li[contains(@class, 'scaffolded-layout__list-item')][.//a[contains(@href, '/jobs/view/')]]",
)

# The shared 5s wait was tight for a cold LinkedIn page load, and a slow load was
# indistinguishable from a markup change.
JOB_LIST_TIMEOUT = 20

# LinkedIn's wording when a search legitimately matches nothing, so an empty result list is not
# misreported as a browser failure.
NO_RESULTS_MARKERS = ("no matching jobs found", "we couldn't find", "try different keywords",
                      "no results found")


def is_new_ui_card(job: WebElement) -> bool:
    '''
    Function to tell an AI search job card apart from a classic one
    * Takes in `job` of type `WebElement` - the job card
    '''
    try:
        return (job.get_dom_attribute('componentkey') or "").startswith(JOB_CARD_COMPONENT_PREFIX)
    except Exception:
        return False


def dedupe_job_cards(cards: list[WebElement]) -> list[WebElement]:
    '''
    Function to drop repeated matches of the same job card
    * The AI search nests two elements carrying the same `componentkey`, so a raw find returns
      every job twice and the bot would open each one twice
    * Keeps the first (outermost) match per job, preserving result order
    '''
    seen, unique = set(), []
    for card in cards:
        try:
            key = (card.get_dom_attribute('componentkey')
                   or card.get_dom_attribute('data-occludable-job-id'))
        except Exception:
            continue
        if key:
            if key in seen: continue
            seen.add(key)
        unique.append(card)
    return unique


def find_job_cards(driver: WebDriver) -> tuple[list[WebElement], str]:
    '''
    Function to find the job cards on the current search results page
    * Tries each known markup in `JOB_CARD_SELECTORS` order
    * Returns a tuple of (job cards, the selector that matched), or `([], "")` when none match
    '''
    for selector in JOB_CARD_SELECTORS:
        cards = driver.find_elements(By.XPATH, selector)
        if cards: return dedupe_job_cards(cards), selector
    return [], ""


def wait_for_job_cards(driver: WebDriver, timeout: int = JOB_LIST_TIMEOUT) -> tuple[list[WebElement], str]:
    '''
    Function to wait for the job results list to render
    * Polls every known markup, so a LinkedIn rename falls through to the next candidate
      instead of timing out every search
    * Returns a tuple of (job cards, the selector that matched)
    * Raises `TimeoutException` if no markup produced a card within `timeout` seconds
    '''
    deadline = time.time() + timeout
    while True:
        cards, selector = find_job_cards(driver)
        if cards: return cards, selector
        if time.time() >= deadline:
            raise TimeoutException(f"No job cards matched any known markup within {timeout}s")
        time.sleep(0.5)


def load_all_job_cards(driver: WebDriver, selector: str, max_rounds: int = 15) -> list[WebElement]:
    '''
    Function to force LinkedIn's lazily rendered results list to materialise every card
    * Takes in `selector` of type `str` - the matched entry from `JOB_CARD_SELECTORS`
    * The AI search renders a virtualised list, so only cards near the viewport exist in the
      DOM. Without this the bot sees roughly a screenful and paginates early.
    * Returns all job cards that could be loaded
    '''
    cards = dedupe_job_cards(driver.find_elements(By.XPATH, selector))
    for _ in range(max_rounds):
        if not cards: break
        try:
            scroll_to_view(driver, cards[-1])
        except Exception:
            break
        time.sleep(1)
        grown = dedupe_job_cards(driver.find_elements(By.XPATH, selector))
        if len(grown) <= len(cards):
            cards = grown
            break
        cards = grown
    return cards


def extract_job_id(job: WebElement) -> str:
    '''
    Function to read the Job ID from a job card
    * Falls back through the componentkey, a descendant `data-job-id` and the job link, so cards
      matched by any entry in `JOB_CARD_SELECTORS` still yield an ID
    * Returns the Job ID, or "Unknown" when the card carries none
    '''
    job_id = job.get_dom_attribute('data-occludable-job-id')
    if job_id: return job_id

    # AI search cards expose no link and no data-job-id; the id lives in the componentkey,
    # e.g. componentkey="job-card-component-ref-4450131581"
    component_key = job.get_dom_attribute('componentkey') or ""
    if component_key.startswith(JOB_CARD_COMPONENT_PREFIX):
        job_id = component_key[len(JOB_CARD_COMPONENT_PREFIX):]
        if job_id: return job_id

    for element in job.find_elements(By.XPATH, ".//*[@data-job-id]"):
        job_id = element.get_dom_attribute('data-job-id')
        if job_id: return job_id
    for link in job.find_elements(By.XPATH, ".//a[contains(@href, '/jobs/view/')]"):
        # Links look like /jobs/view/4449571379/?eBP=..., so take the segment after 'view'
        part = (link.get_attribute('href') or "").split('/jobs/view/')[-1].split('/')[0].split('?')[0]
        if part.isdigit(): return part
    return "Unknown"


# Card badge lines that are never the company or the location, so they must not be mistaken for
# one when a card omits a field.
CARD_BADGE_MARKERS = ("Posted ", "Actively reviewing", "Be an early applicant", "Promoted",
                      "Easy Apply", "Apply", "Viewed", "Applied", "·", "Saved", "Verified job")


def parse_new_ui_card(job: WebElement) -> tuple[str, str, str, bool]:
    '''
    Function to read a job card from LinkedIn's AI search
    * Every class name on the card is build-hashed and the card holds no link or subtitle
      element, so the visible text lines are the only durable structure to read:
        0: accessibility label, repeats the title as "Selected, <title>" / "<title> (Verified job)"
        1: title      2: company      3: location, with the work style in brackets
      Later lines are salary and badges ("Posted 2 days ago", "Applied", "Apply", ...)
    * Returns a tuple of (title, company, work_location, already_applied)
    '''
    try:
        lines = [line.strip() for line in (job.text or "").split("\n") if line.strip()]
    except Exception:
        return "Unknown", "Unknown", "Unknown", False
    if not lines: return "Unknown", "Unknown", "Unknown", False

    # Skip the a11y label only when it really is a decorated copy of the title below it
    start = 1 if len(lines) > 1 and lines[1] and lines[1] in lines[0] else 0
    title = lines[start] if len(lines) > start else "Unknown"
    company = lines[start + 1] if len(lines) > start + 1 else "Unknown"
    work_location = lines[start + 2] if len(lines) > start + 2 else "Unknown"

    # A card missing the company or location would otherwise pick up a badge line
    if any(company.startswith(marker) for marker in CARD_BADGE_MARKERS): company = "Unknown"
    if any(work_location.startswith(marker) for marker in CARD_BADGE_MARKERS): work_location = "Unknown"

    # "Applied" is a badge of its own; "Apply" is the card's apply affordance and is NOT it
    already_applied = any(line == "Applied" or line.startswith("Applied ") for line in lines)
    return title, company, work_location, already_applied


##> ------ Pagination ------

# The AI search has no artdeco pagination; its controls are keyed by data-testid.
NEXT_PAGE_TESTID = "pagination-controls-next-button-visible"


def go_to_next_page(driver: WebDriver) -> bool:
    '''
    Function to advance the AI search results to the next page
    * Returns True when a next page was opened, False when already on the last page
    '''
    buttons = [button for button in
               driver.find_elements(By.CSS_SELECTOR, f'[data-testid="{NEXT_PAGE_TESTID}"]')
               if button.is_displayed()]
    if not buttons: return False
    try:
        scroll_to_view(driver, buttons[0])
        time.sleep(0.5)
        buttons[0].click()
    except Exception:
        driver.execute_script("arguments[0].click();", buttons[0])
    time.sleep(4)
    return True


##> ------ Job details pane ------

def job_description_text(driver: WebDriver, job_id: str) -> str:
    '''
    Function to read the job description from the AI search detail pane
    * The description sits in `#JobDetails_AboutTheJob_<job id>`, which is stable across deploys
      because it is keyed by job id rather than by class name
    * Returns the description text, or "" when it isn't present
    '''
    for element in driver.find_elements(By.ID, f"JobDetails_AboutTheJob_{job_id}"):
        text = (element.text or "").strip()
        if text: return text
    return ""


def about_company_text(driver: WebDriver, job_id: str) -> str:
    '''
    Function to read the About the Company block from the AI search detail pane
    * The classic `.jobs-company__box` no longer exists; this is its replacement
    * Returns the text, or "" when it isn't present

    The block is rendered lazily below the fold, so it reports empty text until it is scrolled
    into view - which silently disabled the whole company blacklist.
    '''
    for element in driver.find_elements(By.ID, f"JobDetails_AboutTheCompany_{job_id}"):
        text = (element.text or "").strip()
        if text: return text
        try:
            scroll_to_view(driver, element)
            time.sleep(1)
            # `.text` returns only what is actually visible, so a block that is rendered but
            # still off-screen reads as empty; innerText returns it either way.
            text = (driver.execute_script("return arguments[0].innerText;", element) or "").strip()
            if text: return text
        except Exception:
            continue
    return ""


##> ------ Apply flow ------

# The AI search's apply button reads "Apply", not "Easy Apply", so matching on the visible text
# misses it entirely. The aria-label is what distinguishes a LinkedIn apply from an off-site one.
LINKEDIN_APPLY_XPATH = ("//button[contains(@aria-label, 'LinkedIn Apply')]"
                        " | //button[contains(@aria-label, 'Apply to this job')]")
EXTERNAL_APPLY_XPATH = ("//button[contains(@aria-label, 'company website')]"
                        " | //a[contains(@aria-label, 'company website')]")


def find_linkedin_apply_button(driver: WebDriver) -> WebElement | None:
    '''
    Function to find the AI search's on-LinkedIn apply button
    * Returns the button, or `None` when this job applies off-site or is already applied to
    '''
    for button in driver.find_elements(By.XPATH, LINKEDIN_APPLY_XPATH):
        if button.is_displayed() and button.is_enabled(): return button
    return None


def find_external_apply_button(driver: WebDriver) -> WebElement | None:
    '''
    Function to find the AI search's off-site apply button
    * Returns the button, or `None` when the job is applied to on LinkedIn
    '''
    for button in driver.find_elements(By.XPATH, EXTERNAL_APPLY_XPATH):
        if button.is_displayed(): return button
    return None


# The apply flow is not a modal - there is no role="dialog" and no `.artdeco-modal`. The only
# durable anchor is the header's id; the flow's root is the ancestor that also holds its buttons.
APPLY_DIALOG_ANCHOR_ID = "dialog-header"

_APPLY_ROOT_JS = """
const header = document.getElementById(arguments[0]);
if (!header) return null;
let node = header;
while (node && node !== document.body) {
    const hasStepButton = [...node.querySelectorAll('button')]
        .some(b => /^(next|review|submit application|back)$/i.test((b.innerText || '').trim()));
    if (hasStepButton && node.querySelector('input, select, textarea, fieldset')) return node;
    node = node.parentElement;
}
return header.parentElement;
"""


def find_apply_dialog(driver: WebDriver) -> WebElement | None:
    '''
    Function to find the root of the AI search's inline apply flow
    * Returns the container holding the form and its step buttons, or `None` when no flow is open
    '''
    try:
        return driver.execute_script(_APPLY_ROOT_JS, APPLY_DIALOG_ANCHOR_ID)
    except Exception:
        return None


def apply_progress(driver: WebDriver) -> int | None:
    '''
    Function to read how far through the apply flow LinkedIn thinks it is
    * The flow reports itself as a percentage (20, 40, ... 100) on its progress bar
    * Returns the percentage, or `None` when there is no progress bar
    * Used to tell "the Next click advanced the form" apart from "the form rejected the click",
      which otherwise looks identical and silently loops
    '''
    for bar in driver.find_elements(By.CSS_SELECTOR, '[role=progressbar], progress'):
        value = bar.get_attribute('aria-valuenow') or bar.get_attribute('value')
        if value and value.strip().isdigit(): return int(value.strip())
    return None


def find_step_button(dialog: WebElement, *labels: str) -> WebElement | None:
    '''
    Function to find one of the apply flow's step buttons by its exact visible text
    * Takes in `labels` of type `str` - e.g. "Next", "Review", "Submit application"
    * Matched on exact text: "Next" must never match "Next steps", and a loose match on
      "Submit" would fire the real submit button
    '''
    wanted = {label.lower() for label in labels}
    for button in dialog.find_elements(By.XPATH, ".//button"):
        try:
            if not button.is_displayed(): continue
            if (button.text or "").strip().lower() in wanted: return button
        except Exception:
            continue
    return None
