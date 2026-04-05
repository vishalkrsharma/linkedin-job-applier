"""
LinkedIn authentication module.
Handles automated login and 2FA wait if needed.
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.utils import human_delay, log_info, log_success, log_warning, log_error


LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"


def login(page: Page, email: str, password: str) -> bool:
    """
    Log into LinkedIn with the provided credentials.

    Returns True if login was successful, False otherwise.
    Handles 2FA by waiting for the user to complete it manually.
    """
    log_info("Navigating to LinkedIn login page...")
    page.goto(LINKEDIN_LOGIN_URL, wait_until="domcontentloaded")
    human_delay(2, 4)

    # Check if already logged in (session from previous run)
    if _is_logged_in(page):
        log_success("Already logged in to LinkedIn!")
        return True

    # Fill in credentials
    log_info("Entering credentials...")

    try:
        email_field = page.locator('input#username')
        email_field.wait_for(state="visible", timeout=10000)
        email_field.click()
        human_delay(0.3, 0.8)
        email_field.fill(email)
        human_delay(0.5, 1.0)

        password_field = page.locator('input#password')
        password_field.click()
        human_delay(0.3, 0.8)
        password_field.fill(password)
        human_delay(0.5, 1.5)

        # Click sign in
        sign_in_btn = page.locator('button[type="submit"], button[data-litms-control-urn="login-submit"]')
        sign_in_btn.click()
        log_info("Clicked Sign In, waiting for response...")

    except PlaywrightTimeout:
        log_error("Could not find login form elements. LinkedIn may have changed their layout.")
        return False

    human_delay(3, 5)

    # Check for security verification / 2FA
    if _is_security_check(page):
        log_warning("🔐 Security verification detected!")
        log_warning("Please complete the verification manually in the browser window.")
        log_warning("Waiting up to 120 seconds for you to complete it...")

        try:
            page.wait_for_url(
                "**/feed/**",
                timeout=120000,  # 2 minutes to complete verification
            )
            log_success("Verification completed!")
        except PlaywrightTimeout:
            # Check if we're on some other LinkedIn page (still logged in)
            if "linkedin.com" in page.url and "login" not in page.url:
                log_success("Appears to be logged in.")
            else:
                log_error("Verification timed out. Please try again.")
                return False

    # Verify login success
    human_delay(2, 3)
    if _is_logged_in(page):
        log_success("Successfully logged in to LinkedIn! 🎉")
        return True
    else:
        log_error("Login failed. Please check your credentials.")
        return False


def _is_logged_in(page: Page) -> bool:
    """Check if we're currently logged in by looking for feed indicators."""
    url = page.url
    if any(path in url for path in ["/feed", "/jobs", "/mynetwork", "/messaging"]):
        return True

    # Check for nav elements that only appear when logged in
    try:
        nav = page.locator('nav.global-nav, [data-test-global-nav], header.global-nav')
        return nav.is_visible(timeout=3000)
    except Exception:
        return False


def _is_security_check(page: Page) -> bool:
    """Check if LinkedIn is showing a security/verification challenge."""
    url = page.url.lower()
    security_indicators = [
        "checkpoint",
        "challenge",
        "security-verification",
        "two-step-verification",
        "verify",
    ]
    if any(indicator in url for indicator in security_indicators):
        return True

    # Check page content for verification prompts
    try:
        body_text = page.locator("body").inner_text(timeout=3000).lower()
        text_indicators = [
            "security verification",
            "verify your identity",
            "two-step verification",
            "let's do a quick security check",
            "enter the code",
        ]
        return any(indicator in body_text for indicator in text_indicators)
    except Exception:
        return False
