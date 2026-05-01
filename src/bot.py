"""
Main bot orchestrator — ties together search, applicant, and tracker.
Uses a dedicated browser profile with persistent LinkedIn session.
"""

import os
import re
import time

from playwright.sync_api import sync_playwright, Page
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
from src.job_search import (
    build_search_url,
    get_job_listings,
    click_job_card,
    has_next_page,
    go_to_next_page,
    JobListing,
)
from src.utils import should_apply
from src.applicant import Applicant
from src.tracker import Tracker
from src.utils import (
    human_delay,
    log_info,
    log_success,
    log_warning,
    log_error,
    log_step,
    format_job_info,
    ensure_dir,
    sanitize_filename,
)


# Dedicated profile directory — keeps the LinkedIn session separate from your real Chrome
PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "browser-profile",
)


class LinkedInBot:
    """Main bot that orchestrates the entire LinkedIn auto-apply process."""

    def __init__(self, config: dict):
        self.config = config
        self.tracker = Tracker()
        self.applied_count = 0
        self.max_applications = config.get("bot", {}).get("max_applications", 25)
        self.blacklist = config.get("blacklist", {})

    def run(self):
        """
        Main entry point. Launches browser with dedicated profile and applies.
        """
        bot_config = self.config.get("bot", {})
        headless = bot_config.get("headless", False)

        # Use a dedicated profile directory for the bot
        ensure_dir(PROFILE_DIR)
        is_first_run = not os.path.exists(os.path.join(PROFILE_DIR, "Default"))

        with sync_playwright() as p:
            if is_first_run:
                log_info("🆕 First run — you'll need to log in to LinkedIn once in the browser.")
                log_info("   Your session will be saved for future runs.")

            log_info("Launching browser...")

            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False if is_first_run else headless,  # Always visible on first run
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
                viewport={
                    "width": bot_config.get("viewport_width", 1280),
                    "height": bot_config.get("viewport_height", 900),
                },
                ignore_default_args=["--enable-automation"],
            )

            # Add stealth scripts to avoid detection
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                window.chrome = { runtime: {} };
            """)

            # Use existing page if one was opened, otherwise create one
            page = context.pages[0] if context.pages else context.new_page()

            try:
                # Step 1: Ensure LinkedIn session
                log_info("=" * 50)
                log_info("Step 1: Checking LinkedIn session")
                log_info("=" * 50)

                if not self._ensure_linkedin_session(page):
                    return

                human_delay(2, 4)

                # Step 2: Search and Apply
                log_info("=" * 50)
                log_info("Step 2: Searching and applying to jobs")
                log_info("=" * 50)

                self._search_and_apply(page)

            except KeyboardInterrupt:
                log_warning("\nInterrupted by user. Saving progress...")
            except Exception as e:
                log_error(f"Unexpected error: {e}")
                if bot_config.get("screenshot_on_error", True):
                    self._take_error_screenshot(page, "unexpected_error")
            finally:
                # Print summary
                self.tracker.print_summary()

                log_info("Closing browser...")
                context.close()

    def _ensure_linkedin_session(self, page: Page) -> bool:
        """
        Navigate to LinkedIn and ensure we have an active session.
        If credentials are configured, logs in automatically.
        Otherwise, waits for manual login in the browser.
        """
        log_info("Navigating to LinkedIn...")
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
        human_delay(3, 5)

        # Already logged in from a previous session?
        if self._is_logged_in(page):
            log_success("✅ LinkedIn session is active — already logged in!")
            return True

        # Not logged in — try auto-login if credentials are provided
        linkedin_config = self.config.get("linkedin", {})
        email = linkedin_config.get("email", "")
        password = linkedin_config.get("password", "")

        if email and password:
            log_info("Credentials found in config, attempting auto-login...")
            from src.auth import login
            success = login(page, email, password)
            if success:
                return True
            else:
                log_warning("Auto-login failed. Falling back to manual login...")

        # Manual login fallback
        log_warning("🔐 Please log in to LinkedIn manually in the browser window.")
        log_warning("   Waiting for you to complete login (up to 5 minutes)...")

        if "/login" not in page.url and "/authwall" not in page.url:
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")

        timeout = 300  # 5 minutes
        start = time.time()

        while time.time() - start < timeout:
            try:
                page.wait_for_timeout(3000)
                if self._is_logged_in(page):
                    log_success("✅ Login detected! Session saved for future runs.")
                    human_delay(2, 3)
                    return True
            except Exception:
                continue

        log_error("❌ Login timed out after 5 minutes. Please try again.")
        return False

    def _is_logged_in(self, page: Page) -> bool:
        """Check if we're currently logged into LinkedIn."""
        url = page.url

        # URL-based check
        if any(path in url for path in ["/feed", "/jobs", "/mynetwork", "/messaging"]):
            # Verify we're not being redirected — check for nav
            try:
                nav = page.locator(
                    'nav.global-nav, [data-test-global-nav], header.global-nav'
                )
                return nav.is_visible(timeout=3000)
            except Exception:
                # If nav check fails but URL looks right, still proceed
                return "/login" not in url and "/authwall" not in url

        return False

    def _search_and_apply(self, page: Page):
        """Core loop: search for jobs, iterate results, and apply."""
        search_config = self.config.get("search", {})
        bot_config = self.config.get("bot", {})
        filters = search_config.get("filters", {})
        max_pages = bot_config.get("max_pages", 10)

        raw_kw = search_config.get("keywords", ["Full Stack Developer"])
        keywords_list = [raw_kw] if isinstance(raw_kw, str) else raw_kw
        
        # Support both single location string and multiple locations list
        raw_loc = search_config.get("locations", search_config.get("location", ["Worldwide"]))
        locations = [raw_loc] if isinstance(raw_loc, str) else raw_loc

        import itertools
        search_combinations = list(itertools.product(keywords_list, locations))

        for current_keyword, current_location in search_combinations:
            if self.applied_count >= self.max_applications:
                break
                
            log_info(f"\n🌍 Starting search for '{current_keyword}' in '{current_location}'")

            for page_num in range(max_pages):
                if self.applied_count >= self.max_applications:
                    log_success(f"Reached max applications limit ({self.max_applications})")
                    break

                # Build search URL and navigate
                search_url = build_search_url(current_keyword, current_location, filters, page_num)
                log_info(f"\nNavigating to search page {page_num + 1} for '{current_keyword}' in {current_location}: {search_url[:80]}...")
                page.goto(search_url, wait_until="domcontentloaded")
                human_delay(1.5, 3.0)

                # Extract job listings
                listings = get_job_listings(page, self.config)

                if not listings:
                    log_warning("No job listings found on this page.")
                    break

                log_info(f"Found {len(listings)} jobs on page {page_num + 1}")

                # Process each job
                for idx, listing in enumerate(listings):
                    if self.applied_count >= self.max_applications:
                        break

                    log_step(
                        idx + 1,
                        len(listings),
                        format_job_info(listing.title, listing.company, listing.location),
                    )

                    # Skip checks
                    if self._should_skip(listing):
                        log_info(f"The title is skipped :{listing.title}")
                        continue

                    # Click on the job card to view details
                    if not click_job_card(page, listing):
                        log_warning(f"  Could not click job card, skipping")
                        continue
                    
                    human_delay(0.5, 1.0)

                    # Check if already applied on LinkedIn's side
                    if self._is_already_applied_on_page(page):
                        log_info("  Already applied (per LinkedIn), skipping")
                        self.tracker.record_skipped(
                            listing.job_id, listing.title, listing.company, "already_applied_linkedin"
                        )
                        continue

                    # Apply!
                    try:
                        applicant = Applicant(page, self.config)
                        success = applicant.apply(listing)

                        if success:
                            self.applied_count += 1
                            self.tracker.record_applied(
                                listing.job_id,
                                listing.title,
                                listing.company,
                                listing.location,
                                listing.url,
                            )
                            log_success(
                                f"  Applied! ({self.applied_count}/{self.max_applications})"
                            )

                            # Delay between applications
                            apply_delay_min = bot_config.get("apply_delay_min", 5.0)
                            apply_delay_max = bot_config.get("apply_delay_max", 15.0)
                            human_delay(apply_delay_min, apply_delay_max)
                        else:
                            self.tracker.record_failed(
                                listing.job_id, listing.title, listing.company,
                                "apply_flow_failed"
                            )
                            # Navigate back to search results so the next job card is clickable
                            self._recover_page(page, search_url)

                    except Exception as e:
                        log_error(f"  Error applying: {e}")
                        self.tracker.record_failed(
                            listing.job_id, listing.title, listing.company, str(e)
                        )
                        if bot_config.get("screenshot_on_error", True):
                            self._take_error_screenshot(page, f"apply_error_{listing.job_id}")
                        # Navigate back to search results so the next job card is clickable
                        self._recover_page(page, search_url)

                # Check for next page
                if page_num < max_pages - 1:
                    if not has_next_page(page):
                        log_info("No more pages available for this location.")
                        break
                    # Navigate to next page via URL (more reliable than clicking)
                    human_delay(0.5, 1.5)

    def _should_skip(self, listing: JobListing) -> bool:
        """Check if a job should be skipped based on blacklist and tracker."""
        bot_config = self.config.get("bot", {})

        # Skip if already tracked
        if bot_config.get("skip_already_applied", True):
            if self.tracker.is_already_applied(listing.job_id):
                log_info("  Already applied (per tracker), skipping")
                return True

        # Check company blacklist
        blacklisted_companies = [c.lower() for c in self.blacklist.get("companies", [])]
        if listing.company.lower() in blacklisted_companies:
            log_info(f"  Blacklisted company: {listing.company}, skipping")
            self.tracker.record_skipped(
                listing.job_id, listing.title, listing.company, "blacklisted_company"
            )
            return True

        # Check title keyword blacklist
        blacklisted_titles = [kw.lower() for kw in self.blacklist.get("title_keywords", [])]
        title_lower = listing.title.lower()
        for kw in blacklisted_titles:
            if kw in title_lower:
                log_info(f"  Blacklisted title keyword '{kw}', skipping")
                self.tracker.record_skipped(
                    listing.job_id, listing.title, listing.company,
                    f"blacklisted_title_keyword:{kw}"
                )
                return True

        return should_apply(title=title_lower)

    def _is_already_applied_on_page(self, page: Page) -> bool:
        """Check if LinkedIn shows 'Applied' status on the job details panel."""
        try:
            detail_panel = page.locator('.jobs-unified-top-card, .job-details-jobs-unified-top-card')
            if detail_panel.count() > 0:
                applied_in_panel = detail_panel.locator('span:has-text("Applied")')
                return applied_in_panel.count() > 0
            return False
        except Exception:
            return False

    def _recover_page(self, page: Page, search_url: str):
        """
        Navigate back to the search URL so the job list is restored after a
        failed or aborted apply. Without this the page can be stuck on a broken
        state (modal still open, wrong URL) causing the next job card click to
        trigger a full-page navigation instead of an in-place panel load.
        """
        try:
            current_url = page.url
            # Only reload if we've genuinely left the search results page
            if "linkedin.com/jobs/search" not in current_url:
                log_info("  Recovering: navigating back to search results...")
                page.goto(search_url, wait_until="domcontentloaded")
                human_delay(1.5, 2.5)
            else:
                # Still on the right page — just make sure no modal is lingering
                try:
                    page.keyboard.press("Escape")
                    human_delay(0.3, 0.6)
                except Exception:
                    pass
        except Exception as e:
            log_warning(f"  Could not recover page state: {e}")

    def _take_error_screenshot(self, page: Page, name: str):
        """Save a screenshot on error for debugging."""
        try:
            ensure_dir("data/screenshots")
            safe_name = sanitize_filename(name)
            path = f"data/screenshots/{safe_name}.png"
            page.screenshot(path=path, full_page=True)
            log_info(f"  Screenshot saved: {path}")
        except Exception:
            pass