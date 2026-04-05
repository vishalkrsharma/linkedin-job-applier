"""
Job search module — builds search URLs, navigates results, and extracts job listings.
"""

import re
import urllib.parse
from dataclasses import dataclass, field

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.utils import human_delay, log_info, log_warning, log_error


@dataclass
class JobListing:
    """Represents a single job listing from search results."""
    job_id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    is_easy_apply: bool = False
    is_promoted: bool = False


# LinkedIn filter value mappings
EXPERIENCE_LEVEL_MAP = {
    "internship": "1",
    "entry_level": "2",
    "associate": "3",
    "mid_senior": "4",
    "director": "5",
    "executive": "6",
}

JOB_TYPE_MAP = {
    "full_time": "F",
    "part_time": "P",
    "contract": "C",
    "temporary": "T",
    "internship": "I",
    "volunteer": "V",
    "other": "O",
}

REMOTE_MAP = {
    "on_site": "1",
    "remote": "2",
    "hybrid": "3",
}

DATE_POSTED_MAP = {
    "any_time": "",
    "past_month": "r2592000",
    "past_week": "r604800",
    "past_24_hours": "r86400",
}

SORT_MAP = {
    "most_relevant": "R",
    "most_recent": "DD",
}


def build_search_url(keywords: str, location: str, filters: dict, page_num: int = 0) -> str:
    """
    Build a LinkedIn job search URL with all configured filters.

    Args:
        keywords: Job search keywords
        location: Location string
        filters: Filter configuration dict
        page_num: Page number (0-indexed)

    Returns:
        Complete LinkedIn jobs search URL
    """
    base_url = "https://www.linkedin.com/jobs/search/"

    params = {
        "keywords": keywords,
        "location": location,
        "start": page_num * 25,  # LinkedIn shows 25 jobs per page
    }

    # Easy Apply filter
    if filters.get("easy_apply_only", True):
        params["f_AL"] = "true"

    # Experience level
    exp_levels = filters.get("experience_level", [])
    if exp_levels:
        values = [EXPERIENCE_LEVEL_MAP[lvl] for lvl in exp_levels if lvl in EXPERIENCE_LEVEL_MAP]
        if values:
            params["f_E"] = ",".join(values)

    # Job type
    job_types = filters.get("job_type", [])
    if job_types:
        values = [JOB_TYPE_MAP[jt] for jt in job_types if jt in JOB_TYPE_MAP]
        if values:
            params["f_JT"] = ",".join(values)

    # Remote preference
    remote_prefs = filters.get("remote", [])
    if remote_prefs:
        values = [REMOTE_MAP[r] for r in remote_prefs if r in REMOTE_MAP]
        if values:
            params["f_WT"] = ",".join(values)

    # Date posted
    date_posted = filters.get("date_posted", "")
    if date_posted and date_posted in DATE_POSTED_MAP and DATE_POSTED_MAP[date_posted]:
        params["f_TPR"] = DATE_POSTED_MAP[date_posted]

    # Sort by
    sort_by = filters.get("sort_by", "most_recent")
    if sort_by in SORT_MAP:
        params["sortBy"] = SORT_MAP[sort_by]

    query_string = urllib.parse.urlencode(params)
    return f"{base_url}?{query_string}"


def get_job_listings(page: Page, config: dict) -> list[JobListing]:
    """
    Navigate to job search results and extract all job listings from the current page.

    Returns a list of JobListing objects.
    """
    listings = []

    try:
        # Wait for job cards to load
        page.wait_for_selector(
            '.jobs-search-results-list, .jobs-search__results-list, [class*="jobs-search-results"]',
            timeout=15000,
        )
        human_delay(2, 3)

        # Scroll through the results to load all cards
        _scroll_job_list(page)

        # Find all job cards
        job_cards = page.locator(
            'li.jobs-search-results__list-item, '
            'li[class*="jobs-search-results"], '
            'div.job-card-container, '
            'div[data-job-id]'
        )

        count = job_cards.count()
        log_info(f"Found {count} job cards on this page")

        for i in range(count):
            try:
                card = job_cards.nth(i)
                listing = _extract_job_from_card(card, page)
                if listing and listing.job_id:
                    listings.append(listing)
            except Exception as e:
                log_warning(f"Could not parse job card {i}: {e}")
                continue

    except PlaywrightTimeout:
        log_error("Timed out waiting for job search results to load")
    except Exception as e:
        log_error(f"Error extracting job listings: {e}")

    return listings


def _extract_job_from_card(card, page: Page) -> JobListing | None:
    """Extract job information from a single job card element."""
    listing = JobListing()

    try:
        # Extract job ID
        job_id = card.get_attribute("data-job-id")
        if not job_id:
            # Try to find it from a nested link
            link = card.locator('a[href*="/jobs/view/"]').first
            if link.count() > 0:
                href = link.get_attribute("href") or ""
                match = re.search(r'/jobs/view/(\d+)', href)
                if match:
                    job_id = match.group(1)

        if not job_id:
            return None

        listing.job_id = job_id

        # Title
        title_el = card.locator(
            'a.job-card-list__title, '
            'a[class*="job-card-list__title"], '
            'strong, '
            'a[class*="job-card-container__link"]'
        ).first
        if title_el.count() > 0:
            listing.title = title_el.inner_text(timeout=3000).strip()

        # Company
        company_el = card.locator(
            'span.job-card-container__primary-description, '
            'a[class*="job-card-container__company-name"], '
            'span[class*="company-name"], '
            'a.job-card-container__company-name'
        ).first
        if company_el.count() > 0:
            listing.company = company_el.inner_text(timeout=3000).strip()

        # Location
        location_el = card.locator(
            'li.job-card-container__metadata-item, '
            'span[class*="job-card-container__metadata-item"], '
            'span[class*="job-card-search__location"]'
        ).first
        if location_el.count() > 0:
            listing.location = location_el.inner_text(timeout=3000).strip()

        # Check for Easy Apply badge
        easy_apply_badge = card.locator('li-icon[type="linkedin-bug"], span:has-text("Easy Apply")')
        listing.is_easy_apply = easy_apply_badge.count() > 0

        # Job URL
        listing.url = f"https://www.linkedin.com/jobs/view/{job_id}/"

    except Exception as e:
        log_warning(f"Partial extraction for job card: {e}")

    return listing


def click_job_card(page: Page, listing: JobListing) -> bool:
    """
    Click on a job card to open its details panel.

    Returns True if the card was successfully clicked.
    """
    try:
        # Try clicking by job ID
        card = page.locator(f'div[data-job-id="{listing.job_id}"], li[data-job-id="{listing.job_id}"]').first
        if card.count() > 0:
            card.scroll_into_view_if_needed()
            human_delay(0.5, 1.0)
            card.click()
            human_delay(1.5, 2.5)
            return True

        # Fallback: try clicking by job title link
        link = page.locator(f'a[href*="/jobs/view/{listing.job_id}"]').first
        if link.count() > 0:
            link.scroll_into_view_if_needed()
            human_delay(0.5, 1.0)
            link.click()
            human_delay(1.5, 2.5)
            return True

        log_warning(f"Could not find clickable element for job {listing.job_id}")
        return False

    except Exception as e:
        log_error(f"Error clicking job card: {e}")
        return False


def _scroll_job_list(page: Page):
    """Scroll the job list container to trigger lazy loading."""
    try:
        list_container = page.locator(
            '.jobs-search-results-list, '
            'div[class*="jobs-search-results-list"]'
        ).first

        if list_container.count() > 0:
            for _ in range(3):
                list_container.evaluate("el => el.scrollTop += el.clientHeight")
                human_delay(0.8, 1.2)

            # Scroll back to top
            list_container.evaluate("el => el.scrollTop = 0")
            human_delay(0.5, 1.0)
    except Exception:
        # Fallback: scroll the page itself
        page.evaluate("window.scrollBy(0, 1000)")
        human_delay(1, 2)
        page.evaluate("window.scrollTo(0, 0)")


def has_next_page(page: Page) -> bool:
    """Check if there's a next page of results."""
    try:
        next_btn = page.locator(
            'button[aria-label="View next page"], '
            'li.artdeco-pagination__indicator--number.active + li button'
        )
        return next_btn.count() > 0 and next_btn.first.is_enabled()
    except Exception:
        return False


def go_to_next_page(page: Page) -> bool:
    """Navigate to the next page of results."""
    try:
        next_btn = page.locator('button[aria-label="View next page"]').first
        if next_btn.count() > 0 and next_btn.is_enabled():
            next_btn.scroll_into_view_if_needed()
            human_delay(0.5, 1.0)
            next_btn.click()
            human_delay(2, 4)
            return True
    except Exception as e:
        log_error(f"Error navigating to next page: {e}")
    return False
