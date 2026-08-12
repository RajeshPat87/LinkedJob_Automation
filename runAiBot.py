'''
Author:     Sai Vignesh Golla
LinkedIn:   https://www.linkedin.com/in/saivigneshgolla/

Copyright (C) 2024 Sai Vignesh Golla

License:    GNU Affero General Public License
            https://www.gnu.org/licenses/agpl-3.0.en.html
            
GitHub:     https://github.com/GodsScion/Auto_job_applier_linkedIn

Support me: https://github.com/sponsors/GodsScion

version:    26.01.20.5.08
'''


# Imports
import os
import csv
import re
import time
from urllib.parse import urlencode
import pyautogui

# Set CSV field size limit to prevent field size errors
csv.field_size_limit(1000000)  # Set to 1MB instead of default 131KB

from random import choice, shuffle, randint
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException, WebDriverException, InvalidSessionIdException, TimeoutException

from modules import apply_flow
from modules.linkedin_ui import (about_company_text, extract_job_id, find_apply_dialog,
                                 find_external_apply_button, find_linkedin_apply_button,
                                 go_to_next_page, is_new_ui, is_new_ui_card, job_description_text,
                                 load_all_job_cards, parse_new_ui_card, resolve_geo_id,
                                 wait_for_job_cards, NO_RESULTS_MARKERS)

from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password, ai_provider
from config.settings import *

from modules.open_chrome import *
from modules.helpers import *
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.throttle import ApplicationPacer, is_soft_block_text

if use_AI:
    from modules.ai.openaiConnections import ai_create_openai_client, ai_extract_skills, ai_answer_question, ai_close_openai_client
    from modules.ai.deepseekConnections import deepseek_create_client, deepseek_extract_skills, deepseek_answer_question
    from modules.ai.geminiConnections import gemini_create_client, gemini_extract_skills, gemini_answer_question

from typing import Literal


pyautogui.FAILSAFE = False
# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

# Unattended mode, set by the cron job as UNATTENDED=1.
# Several pyautogui dialogs block until a human clicks them - the sponsor message at startup,
# the end of run summary, and the failure alerts. With nobody at the keyboard those hang the
# process forever, holding the lock and never reaching the Google Sheets sync. Here they are
# logged instead. The empty string return keeps the callers' == and `in` comparisons working.
unattended = os.environ.get('UNATTENDED', '').strip().lower() in ('1', 'true', 'yes')
if unattended:
    def _log_instead_of_dialog(*args, **kwargs) -> str:
        message = str(args[0]) if args else str(kwargs.get('text', ''))
        print_lg(f"[unattended] dialog suppressed: {' '.join(message.split())[:160]}")
        return ""
    pyautogui.alert = _log_instead_of_dialog
    pyautogui.confirm = _log_instead_of_dialog
    pyautogui.prompt = _log_instead_of_dialog

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
randomly_answered_questions = set()

# The location currently being searched. Recorded against every job so the country is known
# from the search itself, instead of being re-derived from job card HTML that LinkedIn renames.
current_search_location = ""

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False
soft_block_count = 0

# Spaces out submissions so LinkedIn's "applying at a fast pace" safeguard is not triggered.
pacer = ApplicationPacer(min_gap_between_applications, max_gap_between_applications,
                         max_applications_per_hour, announce=print_lg)

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
about_company_for_ai = None # TODO extract about company for AI
##<

#>


#< Login Functions
def is_logged_in_LN() -> bool:
    '''
    Function to check if user is logged-in in LinkedIn
    * Returns: `True` if user is logged-in or `False` if not
    '''
    if driver.current_url == "https://www.linkedin.com/feed/": return True
    if try_linkText(driver, "Sign in"): return False
    if try_xp(driver, '//button[@type="submit" and contains(text(), "Sign in")]'):  return False
    if try_linkText(driver, "Join now"): return False
    print_lg("Didn't find Sign in link, so assuming user is logged in!")
    return True


def login_LN() -> None:
    '''
    Function to login for LinkedIn
    * Tries to login using given `username` and `password` from `secrets.py`
    * If failed, tries to login using saved LinkedIn profile button if available
    * If both failed, asks user to login manually
    '''
    # Find the username and password fields and fill them with user credentials
    driver.get("https://www.linkedin.com/login")
    if username == "username@example.com" and password == "example_password":
        pyautogui.alert("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!", "Login Manually","Okay")
        print_lg("User did not configure username and password in secrets.py, hence can't login automatically! Please login manually!")
        manual_login_retry(is_logged_in_LN, 2)
        return
    try:
        wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Forgot password?")))
        try:
            text_input_by_ID(driver, "username", username, 1)
        except Exception as e:
            print_lg("Couldn't find username field.")
            # print_lg(e)
        try:
            text_input_by_ID(driver, "password", password, 1)
        except Exception as e:
            print_lg("Couldn't find password field.")
            # print_lg(e)
        # Find the login submit button and click it
        driver.find_element(By.XPATH, '//button[@type="submit" and contains(text(), "Sign in")]').click()
    except Exception as e1:
        try:
            profile_button = find_by_class(driver, "profile__details")
            profile_button.click()
        except Exception as e2:
            # print_lg(e1, e2)
            print_lg("Couldn't Login!")

    try:
        # Wait until successful redirect, indicating successful login
        wait.until(EC.url_to_be("https://www.linkedin.com/feed/")) # wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space(.)="Start a post"]')))
        return print_lg("Login successful!")
    except Exception as e:
        print_lg("Seems like login attempt failed! Possibly due to wrong credentials or already logged in! Try logging in manually!")
        # print_lg(e)
        manual_login_retry(is_logged_in_LN, 2)
#>



def get_applied_job_ids() -> set[str]:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from existing applied jobs history csv file
    '''
    job_ids: set[str] = set()
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The CSV file '{file_name}' does not exist.")
    return job_ids



# LinkedIn's own search URL parameters. Setting filters here instead of clicking through the
# "All filters" modal means they cannot silently fail: the modal's markup keeps changing, and
# a failed click was leaving the search completely unfiltered (3 week old jobs, non Easy Apply
# jobs) while only logging a one line warning.
DATE_POSTED_PARAM = {
    "Past 24 hours": "r86400",
    "Past week": "r604800",
    "Past month": "r2592000",
    "Any time": "",
}
EXPERIENCE_PARAM = {"Internship": "1", "Entry level": "2", "Associate": "3",
                    "Mid-Senior level": "4", "Director": "5", "Executive": "6"}
JOB_TYPE_PARAM = {"Full-time": "F", "Part-time": "P", "Contract": "C", "Temporary": "T",
                  "Volunteer": "V", "Internship": "I", "Other": "O"}
ON_SITE_PARAM = {"On-site": "1", "Remote": "2", "Hybrid": "3"}
SORT_BY_PARAM = {"Most recent": "DD", "Most relevant": "R"}

# Filters with no URL equivalent. When any of these is set the modal is still needed.
MODAL_ONLY_FILTERS = ('companies', 'industry', 'job_function', 'job_titles', 'benefits',
                      'commitments', 'location', 'salary')


def build_search_url(search_term: str, search_loc: str) -> str:
    '''
    Function to build a LinkedIn job search URL with the configured filters applied
    * Takes in `search_term` of type `str` - the keywords to search for
    * Takes in `search_loc` of type `str` - the location to search in
    * Returns the full search URL
    '''
    params = {'keywords': search_term}
    location = search_loc.strip()
    if location:
        params['location'] = location
        # LinkedIn's AI search discards `location` and silently falls back to the profile's own
        # location, so every search ran against the wrong place. It keys off `geoId` instead,
        # which the classic UI also accepts - so sending both is safe on either rollout.
        geo_id = resolve_geo_id(location)
        if geo_id: params['geoId'] = geo_id
        else: print_lg(f'No geoId known for "{location}". On LinkedIn\'s AI search this falls back '
                       f'to your profile location - add it to GEO_IDS in modules/linkedin_ui.py.')

    date_param = DATE_POSTED_PARAM.get(date_posted, "")
    if date_param: params['f_TPR'] = date_param
    if easy_apply_only: params['f_AL'] = 'true'

    for key, mapping, configured in (('f_E', EXPERIENCE_PARAM, experience_level),
                                     ('f_JT', JOB_TYPE_PARAM, job_type),
                                     ('f_WT', ON_SITE_PARAM, on_site)):
        codes = [mapping[value] for value in configured if value in mapping]
        if codes: params[key] = ",".join(codes)

    if SORT_BY_PARAM.get(sort_by): params['sortBy'] = SORT_BY_PARAM[sort_by]

    return "https://www.linkedin.com/jobs/search/?" + urlencode(params)


def needs_filter_modal() -> bool:
    '''
    Function to check whether any configured filter has no URL equivalent
    * Returns True only when the "All filters" modal is actually required
    '''
    return any(globals().get(name) for name in MODAL_ONLY_FILTERS)


def get_search_locations() -> list[str]:
    '''
    Function to get the locations to search, highest priority first
    * Uses `search_locations` from config/search.py when set, otherwise falls back to the
      single `search_location`, so existing configs keep working unchanged
    '''
    configured = [location.strip() for location in (search_locations or []) if location.strip()]
    return configured if configured else [search_location]


def set_search_location(location: str) -> None:
    '''
    Function to set search location
    * Takes in `location` of type `str` - the location to type into the search box
    '''
    if location.strip():
        try:
            print_lg(f'Setting search location as: "{location.strip()}"')
            search_location_ele = try_xp(driver, ".//input[@aria-label='City, state, or zip code'and not(@disabled)]", False) #  and not(@aria-hidden='true')]")
            text_input(actions, search_location_ele, location, "Search Location")
        except ElementNotInteractableException:
            try_xp(driver, ".//label[@class='jobs-search-box__input-icon jobs-search-box__keywords-label']")
            actions.send_keys(Keys.TAB, Keys.TAB).perform()
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            actions.send_keys(location.strip()).perform()
            sleep(2)
            actions.send_keys(Keys.ENTER).perform()
            try_xp(driver, ".//button[@aria-label='Cancel']")
        except Exception as e:
            try_xp(driver, ".//button[@aria-label='Cancel']")
            print_lg("Failed to update search location, continuing with default location!", e)


def apply_filters(search_loc: str) -> None:
    '''
    Function to apply job search filters
    * Takes in `search_loc` of type `str` - the location to type into the search box

    Named `search_loc`, not `location`: `location` is already a config global holding the
    dynamic location filter list, and shadowing it made multi_sel_noWait iterate the search
    string character by character.
    '''
    set_search_location(search_loc)

    try:
        recommended_wait = 1 if click_gap < 1 else 0

        wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="All filters"]'))).click()
        buffer(recommended_wait)

        wait_span_click(driver, sort_by)
        wait_span_click(driver, date_posted)
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level) 
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only: boolean_button_click(driver, actions, "Easy Apply")
        
        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)
        
        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

        show_results_button: WebElement = driver.find_element(By.XPATH, '//button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "apply current filters to show")]')
        show_results_button.click()

        global pause_after_filters
        if pause_after_filters and "Turn off Pause after search" == pyautogui.confirm("These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", "Please check your results", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg("Setting the preferences failed!")
        pyautogui.confirm(f"Faced error while applying filters. Please make sure correct filters are selected, click on show results and click on any button of this dialog, I know it sucks. Can't turn off Pause after search when error occurs! ERROR: {e}", ["Doesn't look good, but Continue XD", "Look's good, Continue"])
        # print_lg(e)



def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    # The AI search paginates through a data-testid button instead, handled by go_to_next_page.
    # Looking for the artdeco bar there logged a scary failure on every single page.
    if is_new_ui(driver): return None, None
    try:
        pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
        scroll_to_view(driver, pagination_element)
        current_page = int(pagination_element.find_element(By.XPATH, "//button[contains(@class, 'active')]").text)
    except Exception as e:
        print_lg("Failed to find Pagination element, hence couldn't scroll till end!")
        pagination_element = None
        current_page = None
        print_lg(e)
    return pagination_element, current_page



# LinkedIn's wording when an account has used up its allowance of applications for the day.
DAILY_LIMIT_MESSAGE = "LinkedIn's daily application limit has been reached for this account."
DAILY_LIMIT_HINT = "we limit daily submissions"


class DailyLimitReached(Exception):
    '''Raised when LinkedIn has capped applications for the day, so the run should stop.'''


def daily_limit_reached() -> bool:
    '''
    Function to detect LinkedIn's daily application cap on an open job page
    * Returns True when the apply button is present but disabled and LinkedIn shows its
      "we limit daily submissions ... apply tomorrow" notice

    Both conditions are required: a disabled button on its own can mean an expired posting,
    and the notice alone should not stop a run where applying still works.
    '''
    try:
        buttons = driver.find_elements(By.XPATH, "//button[contains(@class,'jobs-apply-button')]")
        if not buttons or any(button.is_enabled() for button in buttons): return False
        return DAILY_LIMIT_HINT in driver.find_element(By.TAG_NAME, 'body').text.lower()
    except Exception:
        return False


class ApplyPaused(Exception):
    '''Raised when LinkedIn's temporary "applying at a fast pace" pause outlasts our retries.'''


def soft_block_active() -> bool:
    '''
    Function to detect LinkedIn's temporary rate-limit notice ("We noticed you're applying at
    a fast pace ... we've briefly paused LinkedIn Apply") anywhere on the current page or in
    the Easy Apply modal.
    '''
    try:
        return is_soft_block_text(driver.find_element(By.TAG_NAME, 'body').text)
    except Exception:
        return False


def handle_soft_block() -> None:
    '''
    Function to back off when LinkedIn has paused applying. Waits `soft_block_cooldown_minutes`
    and lets the run continue, or raises `ApplyPaused` once the run has used up
    `max_soft_block_retries` (or when the cooldown is configured to 0).

    Applying through the pause only extends it, so waiting is the only way to finish the run.
    '''
    global soft_block_count
    soft_block_count += 1
    print_lg("\n{}\nLinkedIn has temporarily paused applying for this account "
             "(\"applying at a fast pace\" safeguard). Occurrence {} of this run.\n{}\n"
             .format("="*70, soft_block_count, "="*70))
    if soft_block_cooldown_minutes <= 0 or soft_block_count > max_soft_block_retries:
        raise ApplyPaused("LinkedIn paused applying and the configured cooldowns are used up.")
    try: screenshot(driver, "rate_limit", "LinkedIn paused applying")
    except Exception as e: print_lg("Couldn't capture the rate limit screenshot.", e)
    print_lg("Cooling down for {} min before applying again. "
             "Consider lowering max_applications_per_hour in config/settings.py."
             .format(soft_block_cooldown_minutes))
    sleep(soft_block_cooldown_minutes * 60)
    print_lg("Cooldown finished, resuming applications.")
    try: driver.refresh()
    except Exception as e: print_lg("Couldn't refresh the page after the cooldown.", e)


def dismiss_modal_overlay(attempts: int = 3) -> bool:
    '''
    Function to close any leftover LinkedIn modal whose overlay covers the job list and
    swallows clicks meant for the next job card. Returns `True` if no overlay is left.
    '''
    for _ in range(attempts):
        if not driver.find_elements(By.CLASS_NAME, "artdeco-modal-overlay"): return True
        try_xp(driver, "//button[contains(@aria-label, 'Dismiss')]")
        actions.send_keys(Keys.ESCAPE).perform()
        wait_span_click(driver, 'Discard', 1, scroll=False)
        time.sleep(0.5)
    return not driver.find_elements(By.CLASS_NAME, "artdeco-modal-overlay")


# LinkedIn keeps renaming the element that holds the job card's location. These are the known
# class names, newest first; "job-card-container__metadata-item" is the pre-2026 name that
# silently stopped matching and left every Work Location as "Unknown".
LOCATION_CLASS_CANDIDATES = (
    "artdeco-entity-lockup__caption",
    "job-card-container__metadata-wrapper",
    "job-card-container__metadata-item",
)


def extract_work_location(job: WebElement) -> str:
    '''
    Function to read the work location from a job card
    * Takes in `job` of type `WebElement` - the job card
    * Returns the location text, or "Unknown" when none of the known markups match
    '''
    for class_name in LOCATION_CLASS_CANDIDATES:
        try:
            text = job.find_element(By.CLASS_NAME, class_name).text.strip()
            if text: return text.split("\n")[0].strip()
        except NoSuchElementException:
            continue
    return "Unknown"


def log_no_job_cards(search_term: str, search_loc: str) -> None:
    '''
    Function to record why a search rendered no job cards
    * A bare `TimeoutException` prints an empty message, so every failed search used to look
      identical. This logs the page state that actually distinguishes the causes.
    '''
    try:
        url, title, page = driver.current_url, driver.title, driver.page_source.lower()
    except Exception as e:
        print_lg("Couldn't read the page to explain the empty results list.", e)
        return

    if any(marker in page for marker in NO_RESULTS_MARKERS):
        reason = ("LinkedIn returned no matching jobs for these filters. Try widening "
                  "`date_posted`, `experience_level` or `job_type` in config/search.py.")
    elif any(marker in url for marker in ("/authwall", "/login", "/checkpoint", "/uas/login")):
        reason = ("LinkedIn dropped the session or asked for verification. Log in manually in "
                  "the bot's Chrome profile, then re-run.")
    else:
        reason = ("The results list rendered no markup this bot recognises - LinkedIn most likely "
                  "renamed the job card again. Check the screenshot and page source, then add the "
                  "new selector to JOB_CARD_SELECTORS in modules/linkedin_ui.py.")

    print_lg(f'No job cards for "{search_term}" in "{search_loc}". {reason}')
    print_lg(f'Page URL: {url}\nPage title: {title}')
    try:
        print_lg(f'Saved screenshot: {screenshot(driver, "no-job-cards", f"{search_term} in {search_loc}")}')
    except Exception as e:
        print_lg("Couldn't save a screenshot of the empty results page.", e)


def get_job_main_details(job: WebElement, blacklisted_companies: set, rejected_jobs: set) -> tuple[str, str, str, str, str, bool]:
    '''
    # Function to get job main details.
    Returns a tuple of (job_id, title, company, work_location, work_style, skip)
    * job_id: Job ID
    * title: Job title
    * company: Company name
    * work_location: Work location of this job
    * work_style: Work style of this job (Remote, On-site, Hybrid)
    * skip: A boolean flag to skip this job
    '''
    skip = False
    new_ui = is_new_ui_card(job)
    # The AI search's card holds no anchor at all - the card itself is the click target.
    job_details_button = job if new_ui else job.find_element(By.TAG_NAME, 'a')  # job.find_element(By.CLASS_NAME, "job-card-list__title")  # Problem in India
    scroll_to_view(driver, job_details_button, True)
    job_id = extract_job_id(job)
    applied_on_card = False
    if new_ui:
        title, company, work_location, applied_on_card = parse_new_ui_card(job)
    else:
        title = job_details_button.text
        title = title[:title.find("\n")]
        # company = job.find_element(By.CLASS_NAME, "job-card-container__primary-description").text
        # work_location = job.find_element(By.CLASS_NAME, "job-card-container__metadata-item").text
        other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
        index = other_details.find(' · ')
        if index == -1:
            # LinkedIn now puts only the company in the subtitle and the location in its own
            # element. Slicing on index = -1 silently chopped characters off all three fields
            # (e.g. "Ingram Micro" -> "Ingram Micr"), so read them separately instead.
            company = other_details.strip()
            work_location = extract_work_location(job)
        else:
            company = other_details[:index].strip()
            work_location = other_details[index+3:].strip()
    work_style = "Unknown"
    if '(' in work_location and ')' in work_location:
        work_style = work_location[work_location.rfind('(')+1:work_location.rfind(')')].strip()
        work_location = work_location[:work_location.rfind('(')].strip()
    
    # Skip if previously rejected due to blacklist or already applied
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        skip = True
    elif job_id in rejected_jobs: 
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}!')
        skip = True
    # The AI search has no footer-job-state element; it prints "Applied" as one of the card's
    # badge lines, which parse_new_ui_card already picked up.
    if applied_on_card:
        skip = True
        print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
    elif not new_ui:
        try:
            if job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state").text == "Applied":
                skip = True
                print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
        except: pass
    if not skip:
        try:
            job_details_button.click()
        except ElementClickInterceptedException:
            # A leftover modal's overlay is painted over the job list, clear it and retry
            print_lg(f'Job list is covered by a modal, dismissing it to open "{title} | {company}". Job ID: {job_id}')
            dismiss_modal_overlay()
            try:
                scroll_to_view(driver, job_details_button, True)
                job_details_button.click()
            except Exception:
                try:
                    # Last resort, JS click goes straight to the element ignoring what's on top of it
                    driver.execute_script("arguments[0].click();", job_details_button)
                except Exception as e:
                    print_lg(f'Failed to open "{title} | {company}" job, skipping it. Job ID: {job_id}!', e)
                    skip = True
        except Exception as e:
            print_lg(f'Failed to click "{title} | {company}" job on details button. Job ID: {job_id}!')
            # print_lg(e)
            discard_job()
            job_details_button.click() # To pass the error outside
    buffer(click_gap)
    return (job_id,title,company,work_location,work_style,skip)


# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    # The AI search replaced `.jobs-company__box` with an id keyed by job id. Read that first;
    # without it every job raised NoSuchElement and the blacklist was never actually applied.
    about_company_org = about_company_text(driver, job_id)
    jobs_top_card = None
    if not about_company_org and is_new_ui(driver):
        # Say so plainly: silently reading "" here would let every blacklisted company through
        # while the run still looked healthy.
        print_lg(f"About the Company isn't available for job {job_id}, "
                 f"so the company blacklist can't be checked for it.")
        for element in driver.find_elements(By.ID, f"JobDetails_AboutTheJob_{job_id}"):
            return rejected_jobs, blacklisted_companies, element
        return rejected_jobs, blacklisted_companies, None
    if about_company_org:
        for element in driver.find_elements(By.ID, f"JobDetails_AboutTheJob_{job_id}"):
            jobs_top_card = element
            break
    else:
        jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
        about_company_element = find_by_class(driver, "jobs-company__box")
        scroll_to_view(driver, about_company_element)
        about_company_org = about_company_element.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words: 
            if word.lower() in about_company: 
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    if jobs_top_card is not None: scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # Extract all patterns like '10+ years', '5 years', '3-5 years', etc.
    matches = re.findall(re_experience, text)
    if len(matches) == 0: 
        print_lg(f'\n{text}\n\nCouldn\'t find experience requirement in About the Job!')
        return 0
    return max([int(match) for match in matches if int(match) <= 12])



def get_job_description(
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    '''
    try:
        ##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------
        jobDescription = "Unknown"
        ##<
        experience_required = "Unknown"
        found_masters = 0
        jobDescription = find_by_class(driver, "jobs-box__html-content").text
        jobDescriptionLow = jobDescription.lower()
        skip = False
        skipReason = None
        skipMessage = None
        for word in bad_words:
            # Whole word/phrase match, so "Intern" doesn't skip a job that merely says "internal"
            if re.search(r'\b' + re.escape(word.lower()) + r'\b', jobDescriptionLow):
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        # Phrases instead of the bare words "clearance"/"secret", which match things like "External Secrets"
        clearance_phrases = ('polygraph', 'security clearance', 'secret clearance', 'top secret', 'ts/sci', 'government clearance', 'active clearance')
        if not skip and security_clearance == False and any(phrase in jobDescriptionLow for phrase in clearance_phrases):
            skipMessage = f'\n{jobDescription}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n'
            skipReason = "Asking for Security clearance"
            skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    finally:
        return jobDescription, experience_required, skip, skipReason, skipMessage
        


# Function to upload resume
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    try:
        modal.find_element(By.NAME, "file").send_keys(os.path.abspath(resume))
        return True, os.path.basename(default_resume_path)
    except: return False, "Previous resume"

# Function to answer common questions for Easy Apply
def answer_common_questions(label: str, answer: str) -> str:
    if 'sponsorship' in label or 'visa' in label: answer = require_visa
    return answer




def resolve_text_answer(label: str, label_org: str, work_location: str,
                        job_description: str | None = None) -> tuple[str, bool]:
    '''
    Function to decide the answer for a free-text question
    * Takes in `label` of type `str` - the question text, lowercased
    * Takes in `label_org` of type `str` - the question as shown, used for AI and logging
    * Returns a tuple of (answer, needs_typeahead), falling back to the AI provider and then
      to `years_of_experience`
    * `needs_typeahead` is True for the location questions whose field only accepts a value
      picked from its dropdown

    Extracted so LinkedIn's AI search apply flow answers questions identically to the classic
    Easy Apply modal instead of carrying a second, drifting copy of these rules.
    '''
    answer = ""
    do_actions = False
    if 'experience' in label or 'years' in label: answer = years_of_experience
    elif 'phone' in label or 'mobile' in label: answer = phone_number
    elif 'street' in label: answer = street
    elif 'city' in label or 'location' in label or 'address' in label:
        answer = current_city if current_city else work_location
        do_actions = True
    elif 'signature' in label: answer = full_name # 'signature' in label or 'legal name' in label or 'your name' in label or 'full name' in label: answer = full_name     # What if question is 'name of the city or university you attend, name of referral etc?'
    elif 'name' in label:
        if 'full' in label: answer = full_name
        elif 'first' in label and 'last' not in label: answer = first_name
        elif 'middle' in label and 'last' not in label: answer = middle_name
        elif 'last' in label and 'first' not in label: answer = last_name
        elif 'employer' in label: answer = recent_employer
        else: answer = full_name
    elif 'notice' in label:
        if 'month' in label:
            answer = notice_period_months
        elif 'week' in label:
            answer = notice_period_weeks
        else: answer = notice_period
    elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label: 
        if 'current' in label or 'present' in label:
            if 'month' in label:
                answer = current_ctc_monthly
            elif 'lakh' in label:
                answer = current_ctc_lakhs
            else:
                answer = current_ctc
        else:
            if 'month' in label:
                answer = desired_salary_monthly
            elif 'lakh' in label:
                answer = desired_salary_lakhs
            else:
                answer = desired_salary
    elif 'linkedin' in label: answer = linkedIn
    elif 'website' in label or 'blog' in label or 'portfolio' in label or 'link' in label: answer = website
    elif 'scale of 1-10' in label: answer = confidence_level
    elif 'headline' in label: answer = linkedin_headline
    elif ('hear' in label or 'come across' in label) and 'this' in label and ('job' in label or 'position' in label): answer = "https://github.com/GodsScion/Auto_job_applier_linkedIn"
    elif 'state' in label or 'province' in label: answer = state
    elif 'zip' in label or 'postal' in label or 'code' in label: answer = zipcode
    elif 'country' in label: answer = country
    else: answer = answer_common_questions(label,answer)
    ##> ------ Yang Li : MARKYangL - Feature ------
    if answer == "":
        if use_AI and aiClient:
            try:
                if ai_provider.lower() == "openai":
                    answer = ai_answer_question(aiClient, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                elif ai_provider.lower() == "deepseek":
                    answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                elif ai_provider.lower() == "gemini":
                    answer = gemini_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                else:
                    randomly_answered_questions.add((label_org, "text"))
                    answer = years_of_experience
                if answer and isinstance(answer, str) and len(answer) > 0:
                    print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                else:
                    randomly_answered_questions.add((label_org, "text"))
                    answer = years_of_experience
            except Exception as e:
                print_lg("Failed to get AI answer!", e)
                randomly_answered_questions.add((label_org, "text"))
                answer = years_of_experience
        else:
            randomly_answered_questions.add((label_org, "text"))
            answer = years_of_experience
    ##<
    return answer, do_actions

# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:
    # Get all questions from the page
     
    all_questions = modal.find_elements(By.XPATH, ".//div[@data-test-form-element]")
    # all_questions = modal.find_elements(By.CLASS_NAME, "jobs-easy-apply-form-element")
    # all_list_questions = modal.find_elements(By.XPATH, ".//div[@data-test-text-entity-list-form-component]")
    # all_single_line_questions = modal.find_elements(By.XPATH, ".//div[@data-test-single-line-text-form-component]")
    # all_questions = all_questions + all_list_questions + all_single_line_questions

    for Question in all_questions:
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            label_org = "Unknown"
            try:
                label = Question.find_element(By.TAG_NAME, "label")
                label_org = label.find_element(By.TAG_NAME, "span").text
            except: pass
            answer = 'Yes'
            label = label_org.lower()
            select = Select(select)
            selected_option = select.first_selected_option.text
            optionsText = []
            options = '"List of phone country codes"'
            if label != "phone country code":
                optionsText = [option.text for option in select.options]
                options = "".join([f' "{option}",' for option in optionsText])
            prev_answer = selected_option
            if overwrite_previous_answers or selected_option == "Select an option":
                ##> ------ WINDY_WINDWARD Email:karthik.sarode23@gmail.com - Added fuzzy logic to answer location based questions ------
                if 'email' in label or 'phone' in label: 
                    answer = prev_answer
                elif 'gender' in label or 'sex' in label: 
                    answer = gender
                elif 'disability' in label: 
                    answer = disability_status
                elif 'proficiency' in label: 
                    answer = 'Professional'
                # Add location handling
                elif any(loc_word in label for loc_word in ['location', 'city', 'state', 'country']):
                    if 'country' in label:
                        answer = country 
                    elif 'state' in label:
                        answer = state
                    elif 'city' in label:
                        answer = current_city if current_city else work_location
                    else:
                        answer = work_location
                else: 
                    answer = answer_common_questions(label,answer)
                try: 
                    select.select_by_visible_text(answer)
                except NoSuchElementException as e:
                    # Define similar phrases for common answers
                    possible_answer_phrases = []
                    if answer == 'Decline':
                        possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"]
                    elif 'yes' in answer.lower():
                        possible_answer_phrases = ["Yes", "Agree", "I do", "I have"]
                    elif 'no' in answer.lower():
                        possible_answer_phrases = ["No", "Disagree", "I don't", "I do not"]
                    else:
                        # Try partial matching for any answer
                        possible_answer_phrases = [answer]
                        # Add lowercase and uppercase variants
                        possible_answer_phrases.append(answer.lower())
                        possible_answer_phrases.append(answer.upper())
                        # Try without special characters
                        possible_answer_phrases.append(''.join(c for c in answer if c.isalnum()))
                    ##<
                    foundOption = False
                    for phrase in possible_answer_phrases:
                        for option in optionsText:
                            # Check if phrase is in option or option is in phrase (bidirectional matching)
                            if phrase.lower() in option.lower() or option.lower() in phrase.lower():
                                select.select_by_visible_text(option)
                                answer = option
                                foundOption = True
                                break
                    if not foundOption:
                        #TODO: Use AI to answer the question need to be implemented logic to extract the options for the question
                        print_lg(f'Failed to find an option with text "{answer}" for question labelled "{label_org}", answering randomly!')
                        select.select_by_index(randint(1, len(select.options)-1))
                        answer = select.first_selected_option.text
                        randomly_answered_questions.add((f'{label_org} [ {options} ]',"select"))
            questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label = find_by_class(label, "visually-hidden", 2.0)
            except: pass
            label_org = label.text if label else "Unknown"
            answer = 'Yes'
            label = label_org.lower()

            label_org += ' [ '
            options = radio.find_elements(By.TAG_NAME, 'input')
            options_labels = []
            
            for option in options:
                id = option.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{id}"]', False)
                options_labels.append( f'"{option_label.text if option_label else "Unknown"}"<{option.get_attribute("value")}>' ) # Saving option as "label <value>"
                if option.is_selected(): prev_answer = options_labels[-1]
                label_org += f' {options_labels[-1]},'

            if overwrite_previous_answers or prev_answer is None:
                if 'citizenship' in label or 'employment eligibility' in label: answer = us_citizenship
                elif 'veteran' in label or 'protected' in label: answer = veteran_status
                elif 'disability' in label or 'handicapped' in label: 
                    answer = disability_status
                else: answer = answer_common_questions(label,answer)
                foundOption = try_xp(radio, f".//label[normalize-space()='{answer}']", False)
                if foundOption: 
                    actions.move_to_element(foundOption).click().perform()
                else:    
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    ele = options[0]
                    answer = options_labels[0]
                    for phrase in possible_answer_phrases:
                        for i, option_label in enumerate(options_labels):
                            if phrase in option_label:
                                foundOption = options[i]
                                ele = foundOption
                                answer = f'Decline ({option_label})' if len(possible_answer_phrases) > 1 else option_label
                                break
                        if foundOption: break
                    # if answer == 'Decline':
                    #     answer = options_labels[0]
                    #     for phrase in ["Prefer not", "not want", "not wish"]:
                    #         foundOption = try_xp(radio, f".//label[normalize-space()='{phrase}']", False)
                    #         if foundOption:
                    #             answer = f'Decline ({phrase})'
                    #             ele = foundOption
                    #             break
                    actions.move_to_element(ele).click().perform()
                    if not foundOption: randomly_answered_questions.add((f'{label_org} ]',"radio"))
            else: answer = prev_answer
            questions_list.add((label_org+" ]", answer, "radio", prev_answer))
            continue
        
        # Check if it's a text question
        text = try_xp(Question, ".//input[@type='text']", False)
        if text: 
            do_actions = False
            label = try_xp(Question, ".//label[@for]", False)
            try: label = label.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label.text if label else "Unknown"
            answer = "" # years_of_experience
            label = label_org.lower()

            prev_answer = text.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                answer, do_actions = resolve_text_answer(label, label_org, work_location, job_description)
                text.clear()
                text.send_keys(answer)
                if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((label, text.get_attribute("value"), "text", prev_answer))
            continue

        # Check if it's a textarea question
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            label = try_xp(Question, ".//label[@for]", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = ""
            prev_answer = text_area.get_attribute("value")
            if not prev_answer or overwrite_previous_answers:
                if 'summary' in label: answer = linkedin_summary
                elif 'cover' in label: answer = cover_letter
                if answer == "":
                ##> ------ Yang Li : MARKYangL - Feature ------
                    if use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "textarea"))
                            answer = ""
                    else:
                        randomly_answered_questions.add((label_org, "textarea"))
            text_area.clear()
            text_area.send_keys(answer)
            if do_actions:
                    sleep(2)
                    actions.send_keys(Keys.ARROW_DOWN)
                    actions.send_keys(Keys.ENTER).perform()
            questions_list.add((label, text_area.get_attribute("value"), "textarea", prev_answer))
            ##<
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer
            if not prev_answer:
                try:
                    actions.move_to_element(checkbox).click().perform()
                    checked = True
                except Exception as e: 
                    print_lg("Checkbox click failed!", e)
                    pass
            questions_list.add((f'{label} ([X] {answer})', checked, "checkbox", prev_answer))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    return questions_list




def capture_external_link(tabs_before: int, settle_seconds: int = 10) -> str | None:
    '''
    Function to grab the employer's application link from the tab LinkedIn just opened.
    Returns `None` if no new tab was opened.
    * `tabs_before` - number of browser tabs before the Apply button was clicked
    * `settle_seconds` - how long to wait for the new tab to land on the employer's site
    '''
    global tabs_count
    windows = driver.window_handles
    if len(windows) <= tabs_before: return None
    tabs_count = len(windows)
    driver.switch_to.window(windows[-1])
    # The new tab starts on about:blank and hops through a LinkedIn offsite redirect, often
    # followed by an ad network (appcast, click trackers), before reaching the employer's ATS.
    # So wait for the URL to stop changing rather than grabbing the first non-LinkedIn hop.
    application_link = driver.current_url
    settled_polls = 0
    for _ in range(settle_seconds * 2):
        time.sleep(0.5)
        current_link = driver.current_url
        landed = bool(current_link) and current_link != "about:blank" and "linkedin.com" not in current_link
        settled_polls = settled_polls + 1 if landed and current_link == application_link else 0
        application_link = current_link
        if settled_polls >= 2: break
    if close_tabs and driver.current_window_handle != linkedIn_tab: driver.close()
    driver.switch_to.window(linkedIn_tab)
    return application_link


def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str) -> tuple[bool, str, int]:
    '''
    Function to open new tab and save external job application links
    '''
    global tabs_count, dailyEasyApplyLimitReached
    if easy_apply_only:
        try:
            if "exceeded the daily application limit" in driver.find_element(By.CLASS_NAME, "artdeco-inline-feedback__message").text: dailyEasyApplyLimitReached = True
        except: pass
        if not collect_external_links:
            print_lg("Easy apply failed I guess!")
            if pagination_element != None: return True, application_link, tabs_count
    try:
        tabs_before = len(driver.window_handles)
        wait.until(EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3')]"))).click() # './/button[contains(span, "Apply") and not(span[contains(@class, "disabled")])]'
        wait_span_click(driver, "Continue", 1, True, False)
        captured_link = capture_external_link(tabs_before)
        if captured_link is None: raise Exception("Apply button didn't open an external application tab!")
        application_link = captured_link
        print_lg('Got the external application link "{}"'.format(application_link))
        return False, application_link, tabs_count
    except Exception as e:
        # print_lg(e)
        print_lg("Failed to apply!")
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        global failed_count
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str) -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        with open(failed_file_name, 'a', newline='', encoding='utf-8') as file:
            fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried', 'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name', 'Search Location']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Job Link':truncate_for_csv(job_link), 'Resume Tried':truncate_for_csv(resume), 'Date listed':truncate_for_csv(date_listed), 'Date Tried':datetime.now(), 'Assumed Reason':truncate_for_csv(error), 'Stack Trace':truncate_for_csv(exception), 'External Job link':truncate_for_csv(application_link), 'Screenshot Name':truncate_for_csv(screenshot_name), 'Search Location':truncate_for_csv(current_search_location)})
            file.close()
    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        print_lg("Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file")


def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied:  datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development']) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        with open(file_name, mode='a', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'Status', 'About Job', 'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume', 'Re-posted', 'Date Posted', 'Date Applied', 'Job Link', 'External Job link', 'Questions Found', 'Connect Request', 'Search Location']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0: writer.writeheader()
            status = "Easy Applied" if application_link == "Easy Applied" else "External link collected"
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Title':truncate_for_csv(title), 'Company':truncate_for_csv(company), 'Work Location':truncate_for_csv(work_location), 'Work Style':truncate_for_csv(work_style), 'Status':status,
                            'About Job':truncate_for_csv(description), 'Experience required': truncate_for_csv(experience_required), 'Skills required':truncate_for_csv(skills), 
                                'HR Name':truncate_for_csv(hr_name), 'HR Link':truncate_for_csv(hr_link), 'Resume':truncate_for_csv(resume), 'Re-posted':truncate_for_csv(reposted), 
                                'Date Posted':truncate_for_csv(date_listed), 'Date Applied':truncate_for_csv(date_applied), 'Job Link':truncate_for_csv(job_link), 
                                'External Job link':truncate_for_csv(application_link), 'Questions Found':truncate_for_csv(questions_list), 'Connect Request':truncate_for_csv(connect_request), 'Search Location':truncate_for_csv(current_search_location)})
        csv_file.close()
    except Exception as e:
        print_lg("Failed to update submitted jobs list!", e)
        print_lg("Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file")



# Function to discard the job application
def discard_job() -> None:
    actions.send_keys(Keys.ESCAPE).perform()
    wait_span_click(driver, 'Discard', 2)






# Function to apply to jobs
def easy_apply_new_ui(job_id: str, work_location: str, description: str | None) -> tuple[bool, str, set, object]:
    '''
    Function to complete an application in LinkedIn AI search's inline apply flow
    * The classic Easy Apply modal doesn't exist there: the flow is a 5 page dialog anchored on
      `#dialog-header`, whose form controls carry React generated ids that change every render,
      so questions are matched by their text instead
    * Returns a tuple of (applied, resume, questions_list, date_applied)
    * Raises on a flow that can't be completed, so the caller logs it as a failed job

    Nothing is ever submitted by the page loop - only the explicit submit step below can do that.
    '''
    global pause_before_submit
    questions_list = set()
    resume = "Previous resume"

    button = find_linkedin_apply_button(driver)
    if not button: return False, resume, questions_list, "Pending"

    print_lg("Opening the apply flow...")
    try: button.click()
    except Exception: driver.execute_script("arguments[0].click();", button)
    buffer(click_gap)
    time.sleep(3)

    dialog = find_apply_dialog(driver)
    if dialog is None: raise Exception("Clicked Apply but no apply flow opened.")

    for page in range(apply_flow.MAX_PAGES):
        dialog = find_apply_dialog(driver)
        if dialog is None: break
        heading = apply_flow.page_heading(dialog)
        print_lg(f"Apply flow, {heading}")

        if 'resume' in heading.lower():
            # The resume page's only controls are one radio per stored resume, whose "question"
            # is a file name. Feeding those through the question answering picked a resume at
            # random, so this page is handled on its own.
            resume = apply_flow.choose_resume(driver, dialog,
                                              default_resume_path.split('/')[-1] if useNewResume else None)
        else:
            for field in apply_flow.read_form(driver, dialog):
                answered = apply_flow.fill_control(driver, field, work_location,
                                                   randomly_answered_questions, description)
                if answered: questions_list.add((answered[0], answered[1], field.get('kind'), ""))

        if apply_flow.submit_button(driver) is not None: break

        advanced, clicked = apply_flow.advance(driver, dialog)
        if not advanced:
            # LinkedIn refuses Next while a required answer is missing and leaves the page
            # looking identical, so without this the loop spins until MAX_PAGES.
            if pause_at_failed_question:
                screenshot(driver, job_id, "Needed manual intervention for failed question")
                pyautogui.alert('Couldn\'t answer one or more questions.\nPlease complete them, then click "Continue".\n\nYou can turn off "Pause at failed question" in config/settings.py',
                                "Help Needed", "Continue")
                continue
            if questions_list: print_lg("Stuck on one of these questions...", questions_list)
            screenshot(driver, job_id, "Failed at questions")
            raise Exception(f'Apply flow would not advance past "{heading}" (clicked "{clicked}").')

    submit = apply_flow.submit_button(driver)
    if submit is None: raise Exception("Never reached the Review page of the apply flow.")

    if questions_list:
        print_lg("Answered the following questions...", questions_list)

    if pause_before_submit:
        decision = pyautogui.confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit application".\n\n\nYou can turn off "Pause before submit" in config/settings.py',
                                     "Confirm your information", ["Disable Pause", "Discard Application", "Submit Application"])
        if decision == "Discard Application": raise Exception("Job application discarded by user!")
        pause_before_submit = False if decision == "Disable Pause" else True
        submit = apply_flow.submit_button(driver) or submit

    try: submit.click()
    except Exception: driver.execute_script("arguments[0].click();", submit)
    time.sleep(3)
    date_applied = datetime.now()

    # Close the confirmation the flow leaves behind, so it can't cover the next job's card
    if not wait_span_click(driver, "Done", 2): actions.send_keys(Keys.ESCAPE).perform()
    apply_flow.discard(driver)
    return True, resume, questions_list, date_applied


def apply_to_jobs(search_terms: list[str]) -> None:
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, current_search_location
    current_city = current_city.strip()

    if randomize_search_order:  shuffle(search_terms)
    # Location is the outer loop, so the highest priority location is searched across every
    # search term before moving down to the next one.
    searches = [(location, searchTerm)
                for location in get_search_locations() for searchTerm in search_terms]
    print_lg(f'\nSearching {len(search_terms)} term(s) across {len(get_search_locations())} '
             f'location(s) in priority order: {", ".join(get_search_locations())}\n')
    for search_loc, searchTerm in searches:
        current_search_location = search_loc
        search_url = build_search_url(searchTerm, current_search_location)
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" in "{current_search_location}" <<<<\n')
        print_lg(f'Search URL: {search_url}\n')

        # Navigation used to sit outside the try below, so one wedged page load ended the
        # whole run instead of just this search. With 72 searches queued that threw away
        # every remaining location.
        try:
            dismiss_modal_overlay()
            driver.get(search_url)
            # Filters now travel in the URL, so the fragile "All filters" modal is only
            # opened when a filter that has no URL equivalent is configured.
            if needs_filter_modal(): apply_filters(current_search_location)
        except (NoSuchWindowException, InvalidSessionIdException):
            raise   # Browser is genuinely gone, let the outer handler end the run
        except Exception as e:
            print_lg(f'Failed to open search "{searchTerm}" in "{current_search_location}", skipping to the next one.', e)
            critical_error_log("In Applier Search Setup", e)
            continue

        current_count = 0
        try:
            while current_count < switch_number:
                # Wait until job listings are loaded. Polls every known markup rather than one
                # hard coded selector, so a LinkedIn rename falls through to the next candidate
                # instead of timing out every search with an empty error message.
                job_listings, matched_selector = wait_for_job_cards(driver)

                pagination_element, current_page = get_page_info()

                # Re-read the cards: the scroll in get_page_info recycles elements in LinkedIn's
                # virtualised list, and only the cards near the viewport exist in the DOM.
                buffer(3)
                job_listings = load_all_job_cards(driver, matched_selector)
                print_lg(f"Found {len(job_listings)} job cards on this page.")

            
                for job in job_listings:
                    if keep_screen_awake: pyautogui.press('shiftright')
                    if current_count >= switch_number: break
                    print_lg("\n-@-\n")

                    try:
                        job_id,title,company,work_location,work_style,skip = get_job_main_details(job, blacklisted_companies, rejected_jobs)
                    except (NoSuchWindowException, InvalidSessionIdException):
                        raise   # Browser is genuinely gone, let the outer handler end the run
                    except Exception as e:
                        print_lg("Failed to read this job card, skipping it!", e)
                        critical_error_log("In get_job_main_details", e)
                        skip_count += 1
                        continue

                    if skip: continue
                    # Redundant fail safe check for applied jobs!
                    try:
                        if job_id in applied_jobs or find_by_class(driver, "jobs-s-apply__application-link", 2):
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            continue
                    except Exception as e:
                        print_lg(f'Trying to Apply to "{title} | {company}" job. Job ID: {job_id}')

                    job_link = "https://www.linkedin.com/jobs/view/"+job_id
                    application_link = "Easy Applied"
                    date_applied = "Pending"
                    hr_link = "Unknown"
                    hr_name = "Unknown"
                    connect_request = "In Development" # Still in development
                    date_listed = "Unknown"
                    skills = "Needs an AI" # Still in development
                    resume = "Pending"
                    reposted = False
                    questions_list = None
                    screenshot_name = "Not Available"

                    try:
                        rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs,job_id,company,blacklisted_companies)
                    except ValueError as e:
                        print_lg(e, 'Skipping this job!\n')
                        failed_job(job_id, job_link, resume, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name)
                        skip_count += 1
                        continue
                    except Exception as e:
                        print_lg("Failed to scroll to About Company!")
                        # print_lg(e)



                    # Hiring Manager info
                    try:
                        hr_info_card = WebDriverWait(driver,2).until(EC.presence_of_element_located((By.CLASS_NAME, "hirer-card__hirer-information")))
                        hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                        # if connect_hr:
                        #     driver.switch_to.new_window('tab')
                        #     driver.get(hr_link)
                        #     wait_span_click("More")
                        #     wait_span_click("Connect")
                        #     wait_span_click("Add a note")
                        #     message_box = driver.find_element(By.XPATH, "//textarea")
                        #     message_box.send_keys(connect_request_message)
                        #     if close_tabs: driver.close()
                        #     driver.switch_to.window(linkedIn_tab) 
                        # def message_hr(hr_info_card):
                        #     if not hr_info_card: return False
                        #     hr_info_card.find_element(By.XPATH, ".//span[normalize-space()='Message']").click()
                        #     message_box = driver.find_element(By.XPATH, "//div[@aria-label='Write a message…']")
                        #     message_box.send_keys()
                        #     try_xp(driver, "//button[normalize-space()='Send']")        
                    except Exception as e:
                        print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')
                        # print_lg(e)


                    # Calculation of date posted
                    try:
                        # try: time_posted_text = find_by_class(driver, "jobs-unified-top-card__posted-date", 2).text
                        # except: 
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                        print("Time Posted: " + time_posted_text)
                        if time_posted_text.__contains__("Reposted"):
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "")
                        date_listed = calculate_date_posted(time_posted_text.strip())
                    except Exception as e:
                        print_lg("Failed to calculate the date posted!",e)


                    description, experience_required, skip, reason, message = get_job_description()
                    if skip:
                        print_lg(message)
                        failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        continue

                    
                    if use_AI and description != "Unknown":
                        ##> ------ Yang Li : MARKYangL - Feature ------
                        try:
                            if ai_provider.lower() == "openai":
                                skills = ai_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "deepseek":
                                skills = deepseek_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "gemini":
                                skills = gemini_extract_skills(aiClient, description)
                            else:
                                skills = "In Development"
                            print_lg(f"Extracted skills using {ai_provider} AI")
                        except Exception as e:
                            print_lg("Failed to extract skills:", e)
                            skills = "Error extracting skills"
                        ##<

                    uploaded = False
                    external_link = None    # Set when a fallback below already opened the employer's application tab

                    # LinkedIn caps how many applications an account can submit per day. Past the
                    # cap every apply button is rendered disabled, which used to be recorded as
                    # "didn't find Apply button" against every remaining job. Stop instead: the
                    # cap is account wide, so no later job in this run can succeed either.
                    if daily_limit_reached():
                        raise DailyLimitReached(DAILY_LIMIT_MESSAGE)

                    # LinkedIn briefly pauses applying when submissions come in too fast. Every
                    # apply during that window fails, so back off instead of spending the run
                    # on failures - and keep the pace under the threshold to begin with.
                    if soft_block_active(): handle_soft_block()
                    pacer.wait_for_slot()

                    # Case 0: LinkedIn's AI search - a different apply flow entirely, so it is
                    # handled before any of the classic detection below is attempted.
                    if is_new_ui(driver):
                        try:
                            applied, resume, questions_list, new_date = easy_apply_new_ui(job_id, work_location, description)
                        except Exception as e:
                            print_lg("Failed to apply through the new apply flow!")
                            if soft_block_active():
                                apply_flow.discard(driver)
                                handle_soft_block()
                                continue
                            critical_error_log("In new UI apply flow", e)
                            failed_job(job_id, job_link, resume, date_listed, "Problem in new apply flow", e, application_link, screenshot_name)
                            failed_count += 1
                            apply_flow.discard(driver)
                            continue
                        if applied:
                            date_applied = new_date
                        else:
                            # No on-LinkedIn apply button, so this job applies on the employer's site
                            if not collect_external_links:
                                print_lg("Skipping this external job, `collect_external_links` is turned off!")
                                skip_count += 1
                                continue
                            external_button = find_external_apply_button(driver)
                            if external_button:
                                tabs_before = len(driver.window_handles)
                                try: external_button.click()
                                except Exception: driver.execute_script("arguments[0].click();", external_button)
                                buffer(click_gap)
                                application_link = capture_external_link(tabs_before) or "Unknown"
                                print_lg(f'External apply, got the application link "{application_link}"')
                            else:
                                print_lg("No apply button of either kind on this job, skipping it.")
                                skip_count += 1
                                continue
                    else:
                        # Case 1: Easy Apply Button
                        # The aria-label reads "LinkedIn Apply to <job title>" - it does not
                        # contain the word "Easy", so matching on that missed every Easy Apply job.
                        is_easy_apply = try_xp(driver, ".//button[contains(@class,'jobs-apply-button') and (contains(@aria-label, 'Easy') or contains(@aria-label, 'LinkedIn Apply') or normalize-space()='Easy Apply')]")
                        # Fallback 1: check if apply link contains Easy Apply URL pattern
                        if not is_easy_apply:
                            try:
                                apply_link_el = driver.find_element(By.XPATH, ".//a[contains(@href, 'openSDUIApplyFlow=true')]")
                                if apply_link_el:
                                    apply_link_el.click()
                                    is_easy_apply = True
                                    print_lg("Detected Easy Apply via URL pattern (openSDUIApplyFlow)")
                            except:
                                pass
                        # Fallback 2: click any Apply button and check if Easy Apply modal appears
                        if not is_easy_apply:
                            try:
                                apply_btn = driver.find_element(By.XPATH, ".//button[contains(@class,'jobs-apply-button')]")
                                if apply_btn:
                                    tabs_before = len(driver.window_handles)
                                    apply_btn.click()
                                    buffer(click_gap)
                                    tabs_after = len(driver.window_handles)
                                    if tabs_after > tabs_before:
                                        # New tab opened — external apply, capture the employer's link before going back
                                        external_link = capture_external_link(tabs_before)
                                        print_lg('External apply detected via new tab, got the application link "{}"'.format(external_link))
                                    else:
                                        try:
                                            find_by_class(driver, "jobs-easy-apply-modal")
                                            is_easy_apply = True
                                            print_lg("Detected Easy Apply via modal appearance after click")
                                        except:
                                            # Modal didn't appear — dismiss
                                            try: actions.send_keys(Keys.ESCAPE).perform()
                                            except: pass
                            except:
                                pass
                        if is_easy_apply:
                            try: 
                                try:
                                    errored = ""
                                    modal = find_by_class(driver, "jobs-easy-apply-modal")
                                    wait_span_click(modal, "Next", 1)
                                    # if description != "Unknown":
                                    #     resume = create_custom_resume(description)
                                    resume = "Previous resume"
                                    next_button = True
                                    questions_list = set()
                                    next_counter = 0
                                    while next_button:
                                        next_counter += 1
                                        if next_counter >= 15: 
                                            if pause_at_failed_question:
                                                screenshot(driver, job_id, "Needed manual intervention for failed question")
                                                pyautogui.alert("Couldn't answer one or more questions.\nPlease click \"Continue\" once done.\nDO NOT CLICK Back, Next or Review button in LinkedIn.\n\n\n\n\nYou can turn off \"Pause at failed question\" setting in config.py", "Help Needed", "Continue")
                                                next_counter = 1
                                                continue
                                            if questions_list: print_lg("Stuck for one or some of the following questions...", questions_list)
                                            screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                            errored = "stuck"
                                            raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")
                                        questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                        if useNewResume and not uploaded: uploaded, resume = upload_resume(modal, default_resume_path)
                                        try: next_button = modal.find_element(By.XPATH, './/span[normalize-space(.)="Review"]') 
                                        except NoSuchElementException:  next_button = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                                        try: next_button.click()
                                        except ElementClickInterceptedException: break    # Happens when it tries to click Next button in About Company photos section
                                        buffer(click_gap)

                                except NoSuchElementException: errored = "nose"
                                finally:
                                    if questions_list and errored != "stuck": 
                                        print_lg("Answered the following questions...", questions_list)
                                        print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                    wait_span_click(driver, "Review", 1, scrollTop=True)
                                    cur_pause_before_submit = pause_before_submit
                                    if errored != "stuck" and cur_pause_before_submit:
                                        decision = pyautogui.confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', "Confirm your information",["Disable Pause", "Discard Application", "Submit Application"])
                                        if decision == "Discard Application": raise Exception("Job application discarded by user!")
                                        pause_before_submit = False if "Disable Pause" == decision else True
                                        # try_xp(modal, ".//span[normalize-space(.)='Review']")
                                    follow_company(modal)
                                    if wait_span_click(driver, "Submit application", 2, scrollTop=True): 
                                        date_applied = datetime.now()
                                        if not wait_span_click(driver, "Done", 2): actions.send_keys(Keys.ESCAPE).perform()
                                    elif errored != "stuck" and cur_pause_before_submit and "Yes" in pyautogui.confirm("You submitted the application, didn't you 😒?", "Failed to find Submit Application!", ["Yes", "No"]):
                                        date_applied = datetime.now()
                                        wait_span_click(driver, "Done", 2)
                                    else:
                                        print_lg("Since, Submit Application failed, discarding the job application...")
                                        # if screenshot_name == "Not Available":  screenshot_name = screenshot(driver, job_id, "Failed to click Submit application")
                                        # else:   screenshot_name = [screenshot_name, screenshot(driver, job_id, "Failed to click Submit application")]
                                        if errored == "nose": raise Exception("Failed to click Submit application 😑")


                            except Exception as e:
                                print_lg("Failed to Easy apply!")
                                # print_lg(e)
                                # The rate-limit pause surfaces as an ordinary Easy Apply failure, so
                                # check for it here before writing the job off as failed.
                                if soft_block_active():
                                    discard_job()
                                    handle_soft_block()
                                    continue
                                critical_error_log("Somewhere in Easy Apply process",e)
                                failed_job(job_id, job_link, resume, date_listed, "Problem in Easy Applying", e, application_link, screenshot_name)
                                failed_count += 1
                                discard_job()
                                continue
                        elif external_link:
                            # Case 2a: Apply button already opened the employer's site above, just record the link
                            if not collect_external_links:
                                print_lg("Skipping this external job, `collect_external_links` is turned off!")
                                skip_count += 1
                                continue
                            application_link = external_link
                        else:
                            # Case 2b: Apply externally
                            skip, application_link, tabs_count = external_apply(pagination_element, job_id, job_link, resume, date_listed, application_link, screenshot_name)
                            if dailyEasyApplyLimitReached:
                                print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                                return
                            if skip: continue

                    submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required, skills, hr_name, hr_link, resume, reposted, date_listed, date_applied, job_link, application_link, questions_list, connect_request)
                    if uploaded:   useNewResume = False

                    print_lg(f'Successfully saved "{title} | {company}" job. Job ID: {job_id} info')
                    current_count += 1
                    if application_link == "Easy Applied":
                        easy_applied_count += 1
                        pacer.record_application()  # Only submissions count towards LinkedIn's rate
                    else:   external_jobs_count += 1
                    applied_jobs.add(job_id)



                # Switching to next page
                # The AI search has no artdeco pagination bar at all, so `pagination_element`
                # is always None there and every search used to stop after its first page.
                if is_new_ui(driver):
                    dismiss_modal_overlay()
                    if not go_to_next_page(driver):
                        print_lg("\n>-> No next page button. At the end of the results!\n")
                        break
                    print_lg("\n>-> Now on the next page \n")
                    continue
                if pagination_element == None:
                    print_lg("Couldn't find pagination element, probably at the end page of results!")
                    break
                # A leftover "discard application?" modal covers the pagination bar and makes
                # the click land on the overlay instead. Left alone it blocks every later
                # action until the browser stops responding and the whole run is abandoned.
                dismiss_modal_overlay()
                try:
                    next_page_button = pagination_element.find_element(By.XPATH, f"//button[@aria-label='Page {current_page+1}']")
                    try:
                        next_page_button.click()
                    except ElementClickInterceptedException:
                        print_lg("Pagination click was intercepted, clearing the overlay and retrying.")
                        dismiss_modal_overlay()
                        next_page_button.click()
                    print_lg(f"\n>-> Now on Page {current_page+1} \n")
                except NoSuchElementException:
                    print_lg(f"\n>-> Didn't find Page {current_page+1}. Probably at the end page of results!\n")
                    break

        except ApplyPaused as e:
            # Account wide like the daily cap, so later searches would hit the same pause.
            print_lg(f"\n{'='*70}\n{e}\nStopping the run to let the account cool off.\n"
                     f"Lower `max_applications_per_hour` or raise the gap settings in config/settings.py "
                     f"before the next run.\n{'='*70}\n")
            break
        except DailyLimitReached as e:
            # Account wide, so no further search or location can apply either today.
            print_lg(f"\n{'='*70}\n{e}\nStopping the run - remaining searches would all be blocked.\n"
                     f"Applications reset after about 24 hours.\n{'='*70}\n")
            break
        except TimeoutException as e:
            # TimeoutException subclasses WebDriverException, so it used to be swallowed by the
            # handler below and logged as a bare "Message:" with nothing after it. The page state
            # is what actually says whether this is a rename, a logout or an empty search.
            log_no_job_cards(searchTerm, current_search_location)
            critical_error_log("In Applier - no job listings", e)
            continue
        except (NoSuchWindowException, WebDriverException) as e:
            # ElementClickInterceptedException & friends are WebDriverException subclasses, so
            # confirm the session is actually dead before writing off the whole run.
            try:
                driver.current_url
                browser_alive = True
            except Exception:
                browser_alive = False
            if not browser_alive:
                print_lg("Browser window closed or session is invalid. Ending application process.", e)
                raise e # Re-raise to be caught by main
            print_lg("Recoverable browser error, moving on to the next search term!", e)
            critical_error_log("In Applier", e)
        except Exception as e:
            print_lg("Failed to find Job listings!")
            critical_error_log("In Applier", e)
            try:
                print_lg(driver.page_source, pretty=True)
            except Exception as page_source_error:
                print_lg(f"Failed to get page source, browser might have crashed. {page_source_error}")
            # print_lg(e)

        
def run(total_runs: int) -> int:
    if dailyEasyApplyLimitReached:
        return total_runs
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for jobs posted within '{date_posted}' and sorting them by '{sort_by}'")
    apply_to_jobs(search_terms)
    print_lg("########################################################################################################################\n")
    if not dailyEasyApplyLimitReached:
        print_lg("Sleeping for 10 min...")
        sleep(300)
        print_lg("Few more min... Gonna start with in next 5 min...")
        sleep(300)
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def main() -> None:
    # Logged rather than shown as a dialog. It carries no setting and nothing depends on the
    # answer, but as a modal it blocked the whole run behind one click - and under WSL/WSLg the
    # tk dialog draws as its own unparented window while Chrome stays unmapped, so that click
    # often never lands and the run looks frozen with no browser and no further log output.
    print_lg("\nPlease consider sponsoring this project at:\n\nhttps://github.com/sponsors/GodsScion\n")
    total_runs = 1
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient
        alert_title = "Error Occurred. Closing Browser!"
        validate_config()
        
        if not os.path.exists(default_resume_path):
            print_lg('Your default resume "{}" is missing! Please update its folder path "default_resume_path" in config/questions.py, or add a resume with that exact name and path. For now the bot will continue using your previous upload from LinkedIn.'.format(default_resume_path))
            useNewResume = False
        
        # Login to LinkedIn
        tabs_count = len(driver.window_handles)
        driver.get("https://www.linkedin.com/login")
        if not is_logged_in_LN(): login_LN()
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         driver.get("https://chat.openai.com/")
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if use_AI:
            if ai_provider == "openai":
                aiClient = ai_create_openai_client()
            ##> ------ Yang Li : MARKYangL - Feature ------
            # Create DeepSeek client
            elif ai_provider == "deepseek":
                aiClient = deepseek_create_client()
            elif ai_provider == "gemini":
                aiClient = gemini_create_client()
            ##<

            try:
                about_company_for_ai = " ".join([word for word in (first_name+" "+last_name).split() if len(word) > 3])
                print_lg(f"Extracted about company info for AI: '{about_company_for_ai}'")
            except Exception as e:
                print_lg("Failed to extract about company info!", e)
        
        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                global date_posted
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if dailyEasyApplyLimitReached:
                break
        

    except (NoSuchWindowException, WebDriverException) as e:
        print_lg("Browser window closed or session is invalid. Exiting.", e)
    except Exception as e:
        # critical_error_log already writes this to log.txt, and as a modal it left a crashed
        # run hanging on a click instead of closing the browser and freeing the profile.
        critical_error_log(alert_title, e)
    finally:
        summary = "Total runs: {}\nJobs Easy Applied: {}\nExternal job links collected: {}\nTotal applied or collected: {}\nFailed jobs: {}\nIrrelevant jobs skipped: {}\n".format(total_runs,easy_applied_count,external_jobs_count,easy_applied_count + external_jobs_count,failed_count,skip_count)
        print_lg(summary)
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        quotes = choice([
            "Never quit. You're one step closer than before. - Sai Vignesh Golla", 
            "All the best with your future interviews, you've got this. - Sai Vignesh Golla", 
            "Keep up with the progress. You got this. - Sai Vignesh Golla", 
            "If you're tired, learn to take rest but never give up. - Sai Vignesh Golla",
            "Success is not final, failure is not fatal, It is the courage to continue that counts. - Winston Churchill (Not a sponsor)",
            "Believe in yourself and all that you are. Know that there is something inside you that is greater than any obstacle. - Christian D. Larson (Not a sponsor)",
            "Every job is a self-portrait of the person who does it. Autograph your work with excellence. - Jessica Guidobono (Not a sponsor)",
            "The only way to do great work is to love what you do. If you haven't found it yet, keep looking. Don't settle. - Steve Jobs (Not a sponsor)",
            "Opportunities don't happen, you create them. - Chris Grosser (Not a sponsor)",
            "The road to success and the road to failure are almost exactly the same. The difference is perseverance. - Colin R. Davis (Not a sponsor)",
            "Obstacles are those frightful things you see when you take your eyes off your goal. - Henry Ford (Not a sponsor)",
            "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt (Not a sponsor)",
            ])
        sponsors = "Be the first to have your name here!"
        timeSaved = (easy_applied_count * 80) + (external_jobs_count * 20) + (skip_count * 10)
        timeSavedMsg = ""
        if timeSaved > 0:
            timeSaved += 60
            timeSavedMsg = f"In this run, you saved approx {round(timeSaved/60)} mins ({timeSaved} secs), please consider supporting the project."
        msg = f"{quotes}\n\n\n{timeSavedMsg}\nYou can also get your quote and name shown here, or prioritize your bug reports by supporting the project at:\n\nhttps://github.com/sponsors/GodsScion\n\n\nSummary:\n{summary}\n\n\nBest regards,\nSai Vignesh Golla\nhttps://www.linkedin.com/in/saivigneshgolla/\n\nTop Sponsors:\n{sponsors}"
        # Was a modal that held the process open at the end of a run, after the work was
        # already done. The identical text is logged on the next line either way.
        print_lg(msg,"Closing the browser...")
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            print_lg("\n"+msg)
        ##> ------ Yang Li : MARKYangL - Feature ------
        if use_AI and aiClient:
            try:
                if ai_provider.lower() == "openai":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "deepseek":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "gemini":
                    pass # Gemini client does not need to be closed
                print_lg(f"Closed {ai_provider} AI client.")
            except Exception as e:
                print_lg("Failed to close AI client:", e)
        ##<
        try:
            if driver:
                driver.quit()
        except WebDriverException as e:
            print_lg("Browser already closed.", e)
        except Exception as e: 
            critical_error_log("When quitting...", e)


if __name__ == "__main__":
    main()
