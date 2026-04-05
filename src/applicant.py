"""
Applicant module — handles the Easy Apply flow:
filling forms, uploading resumes, and submitting applications.
"""

import os
import re

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from src.utils import human_delay, match_answer, log_info, log_success, log_warning, log_error
from src.job_search import JobListing


class Applicant:
    """Handles the LinkedIn Easy Apply flow for a single job."""

    def __init__(self, page: Page, config: dict):
        self.page = page
        self.config = config
        self.answers = config.get("answers", {})
        self.resume_path = config.get("resume_path", "")
        self.dry_run = config.get("bot", {}).get("dry_run", False)

    def apply(self, listing: JobListing) -> bool:
        """
        Attempt to apply to a job via Easy Apply.

        Returns True if the application was submitted (or would be in dry run).
        """
        page = self.page

        # Click the Easy Apply button
        if not self._click_easy_apply():
            return False

        human_delay(0.5, 1.0)

        # Process each step of the multi-step form
        max_steps = 10  # Safety limit
        for step in range(max_steps):
            log_info(f"  Processing form step {step + 1}...")

            # Fill out the current form page
            self._fill_current_form()
            human_delay(0.5, 1.0)

            # Check if we're on the review/submit page
            if self._is_review_page():
                log_info("  Reached review page")
                if self.dry_run:
                    log_warning("  DRY RUN — skipping submission")
                    self._dismiss_modal()
                    return True
                else:
                    return self._submit_application()

            # Check if there's a "Next" button
            if self._has_next_button():
                self._click_next()
                human_delay(0.5, 1.0)

                # Check for validation errors
                if self._has_form_errors():
                    log_warning("  Form has validation errors, attempting to fix...")
                    self._try_fix_errors()
                    human_delay(0.4, 0.8)

                    # Try clicking next again
                    if self._has_form_errors():
                        log_error("  Could not resolve form errors, skipping this job")
                        self._dismiss_modal()
                        return False
            else:
                # No next button and not review page — probably a single page form
                if self.dry_run:
                    log_warning("  DRY RUN — skipping submission")
                    self._dismiss_modal()
                    return True
                return self._submit_application()

        log_error("  Exceeded max form steps, aborting")
        self._dismiss_modal()
        return False

    def _click_easy_apply(self) -> bool:
        """Find and click the Easy Apply button on the job detail panel."""
        page = self.page

        try:
            # The job details panel can take a moment to load
            human_delay(0.5, 1.0)

            # Look for buttons that specifically say "Easy Apply"
            # We want to avoid external "Apply" buttons
            easy_apply_btn = page.locator(
                'div.jobs-details__main-content button:has-text("Easy Apply"), '
                'div.job-view-layout button:has-text("Easy Apply"), '
                '.jobs-apply-button--top-card button:has-text("Easy Apply")'
            ).first

            # Wait for the button to appear in the DOM and be visible
            try:
                easy_apply_btn.wait_for(state="visible", timeout=5000)
            except PlaywrightTimeout:
                # If the specific container selector fails, let's try a broader one
                easy_apply_btn = page.locator('button:has-text("Easy Apply")').first
                easy_apply_btn.wait_for(state="visible", timeout=3000)

            if easy_apply_btn.is_visible():
                easy_apply_btn.scroll_into_view_if_needed()
                human_delay(0.5, 1.0)
                easy_apply_btn.click()
                log_info("  Clicked Easy Apply button")
                return True
            else:
                log_warning("  Easy Apply button not found or not visible")
                return False

        except PlaywrightTimeout:
            log_warning("  Timed out looking for Easy Apply button (might be an external Apply)")
            return False
        except Exception as e:
            log_error(f"  Error clicking Easy Apply: {e}")
            return False

    def _fill_current_form(self):
        """Fill all form fields on the current Easy Apply form step."""
        page = self.page

        # Fill text input fields
        self._fill_text_inputs()

        # Handle text areas
        self._fill_textareas()

        # Handle dropdowns / select elements
        self._fill_dropdowns()

        # Handle radio buttons
        self._fill_radio_buttons()

        # Handle checkboxes
        self._fill_checkboxes()

        # Handle file uploads (resume)
        self._handle_file_upload()

    def _fill_text_inputs(self):
        """Fill text input fields based on their labels."""
        page = self.page

        # Find form groups with labels and inputs
        form_groups = page.locator(
            'div.jobs-easy-apply-form-section__grouping, '
            'div[class*="jobs-easy-apply-form-element"], '
            'div.fb-dash-form-element'
        )

        for i in range(form_groups.count()):
            group = form_groups.nth(i)

            try:
                # Find the label
                label = group.locator('label, span[class*="label"], legend').first
                if label.count() == 0:
                    continue

                label_text = label.inner_text(timeout=2000).strip()
                if not label_text:
                    continue

                # Find the input
                input_field = group.locator(
                    'input[type="text"], input[type="number"], input[type="tel"], '
                    'input[type="email"], input[type="url"], input:not([type="hidden"]):not([type="file"]):not([type="checkbox"]):not([type="radio"])'
                ).first

                if input_field.count() == 0 or not input_field.is_visible():
                    continue

                # Check if already filled
                current_value = input_field.input_value()
                if current_value and len(current_value.strip()) > 0:
                    continue

                # Try to find an answer
                answer = match_answer(label_text, self.answers)
                if answer:
                    input_field.click()
                    human_delay(0.2, 0.5)
                    input_field.fill(answer)
                    log_info(f"    Filled '{label_text}' → '{answer}'")
                    human_delay(0.3, 0.7)
                else:
                    log_warning(f"    No answer for: '{label_text}'")

            except Exception as e:
                continue

    def _fill_textareas(self):
        """Fill textarea fields."""
        page = self.page

        textareas = page.locator(
            'div.jobs-easy-apply-form-section__grouping textarea, '
            'div[class*="jobs-easy-apply-form-element"] textarea, '
            'div.fb-dash-form-element textarea'
        )

        for i in range(textareas.count()):
            try:
                textarea = textareas.nth(i)
                if not textarea.is_visible():
                    continue

                current_value = textarea.input_value()
                if current_value and len(current_value.strip()) > 0:
                    continue

                # Try to find the associated label
                parent_group = textarea.locator('xpath=ancestor::div[contains(@class, "form-section") or contains(@class, "form-element")]').first
                label_text = ""
                if parent_group.count() > 0:
                    label_el = parent_group.locator('label, span[class*="label"]').first
                    if label_el.count() > 0:
                        label_text = label_el.inner_text(timeout=2000).strip()

                answer = match_answer(label_text, self.answers) if label_text else None

                if answer:
                    textarea.click()
                    human_delay(0.2, 0.5)
                    textarea.fill(answer)
                    log_info(f"    Filled textarea '{label_text}' → '{answer[:50]}...'")
                else:
                    log_warning(f"    No answer for textarea: '{label_text}'")

            except Exception:
                continue

    def _fill_dropdowns(self):
        """Handle select/dropdown elements."""
        page = self.page

        selects = page.locator(
            'div.jobs-easy-apply-form-section__grouping select, '
            'div[class*="jobs-easy-apply-form-element"] select, '
            'div.fb-dash-form-element select'
        )

        for i in range(selects.count()):
            try:
                select = selects.nth(i)
                if not select.is_visible():
                    continue

                # Check if already selected (not on the default/placeholder)
                current = select.input_value()
                if current and current != "" and current != "Select an option":
                    continue

                # Get the label
                parent = select.locator('xpath=ancestor::div[contains(@class, "form-section") or contains(@class, "form-element")]').first
                label_text = ""
                if parent.count() > 0:
                    label_el = parent.locator('label, span[class*="label"]').first
                    if label_el.count() > 0:
                        label_text = label_el.inner_text(timeout=2000).strip()

                answer = match_answer(label_text, self.answers) if label_text else None

                if answer:
                    # Try to find a matching option
                    options = select.locator('option')
                    best_option = None

                    for j in range(options.count()):
                        opt_text = options.nth(j).inner_text(timeout=1000).strip().lower()
                        opt_value = options.nth(j).get_attribute("value") or ""

                        if answer.lower() in opt_text or opt_text in answer.lower():
                            best_option = opt_value or opt_text
                            break

                    if best_option:
                        select.select_option(value=best_option)
                        log_info(f"    Selected '{label_text}' → '{best_option}'")
                    else:
                        # Just select the first non-empty option
                        for j in range(options.count()):
                            opt_value = options.nth(j).get_attribute("value") or ""
                            if opt_value and opt_value != "":
                                select.select_option(value=opt_value)
                                opt_text = options.nth(j).inner_text(timeout=1000).strip()
                                log_info(f"    Selected first option for '{label_text}' → '{opt_text}'")
                                break
                else:
                    # Select first non-empty option as fallback
                    options = select.locator('option')
                    for j in range(options.count()):
                        opt_value = options.nth(j).get_attribute("value") or ""
                        if opt_value and opt_value != "":
                            select.select_option(value=opt_value)
                            opt_text = options.nth(j).inner_text(timeout=1000).strip()
                            log_warning(f"    Auto-selected '{opt_text}' for '{label_text}'")
                            break

            except Exception:
                continue

    def _fill_radio_buttons(self):
        """Handle radio button groups."""
        page = self.page

        # Find fieldsets or radio groups
        radio_groups = page.locator(
            'fieldset[data-test-form-builder-radio-button-form-component], '
            'div.jobs-easy-apply-form-section__grouping:has(input[type="radio"]), '
            'div.fb-dash-form-element:has(input[type="radio"])'
        )

        for i in range(radio_groups.count()):
            try:
                group = radio_groups.nth(i)

                # Check if any radio is already selected
                checked = group.locator('input[type="radio"]:checked')
                if checked.count() > 0:
                    continue

                # Get the legend/question text
                legend = group.locator('legend, span[class*="label"], label').first
                question_text = ""
                if legend.count() > 0:
                    question_text = legend.inner_text(timeout=2000).strip()

                answer = match_answer(question_text, self.answers) if question_text else None

                radio_options = group.locator('input[type="radio"]')

                if answer:
                    # Try to match the answer to a radio option
                    for j in range(radio_options.count()):
                        radio = radio_options.nth(j)
                        radio_label = group.locator(f'label[for="{radio.get_attribute("id")}"]')
                        if radio_label.count() > 0:
                            radio_text = radio_label.inner_text(timeout=1000).strip().lower()
                            if answer.lower() in radio_text or radio_text in answer.lower():
                                radio.check()
                                log_info(f"    Selected radio '{question_text}' → '{radio_text}'")
                                break
                    else:
                        # If no match found, select first option
                        if radio_options.count() > 0:
                            radio_options.first.check()
                            log_warning(f"    Auto-selected first radio for '{question_text}'")
                else:
                    # Default: select first option
                    if radio_options.count() > 0:
                        radio_options.first.check()
                        log_warning(f"    Auto-selected first radio for '{question_text}'")

            except Exception:
                continue

    def _fill_checkboxes(self):
        """Handle checkbox fields (usually terms/agreements)."""
        page = self.page

        # Look for unchecked required checkboxes
        checkboxes = page.locator(
            'div.jobs-easy-apply-form-section__grouping input[type="checkbox"]:not(:checked), '
            'div.fb-dash-form-element input[type="checkbox"]:not(:checked)'
        )

        for i in range(checkboxes.count()):
            try:
                cb = checkboxes.nth(i)
                if cb.is_visible():
                    # Check if it looks like a terms/follow checkbox
                    cb_id = cb.get_attribute("id") or ""
                    label = page.locator(f'label[for="{cb_id}"]')
                    label_text = ""
                    if label.count() > 0:
                        label_text = label.inner_text(timeout=2000).strip().lower()

                    # Auto-check terms and follow checkboxes
                    if any(kw in label_text for kw in ["terms", "agree", "acknowledge", "certif", "follow"]):
                        cb.check()
                        log_info(f"    Checked: '{label_text[:60]}'")
            except Exception:
                continue

    def _handle_file_upload(self):
        """Handle resume/document file uploads."""
        page = self.page

        # Read config to see if we should upload at all
        bot_config = self.config.get("bot", {})
        if not bot_config.get("upload_resume", False):  # Default to false to completely skip
            return

        if not self.resume_path or not os.path.exists(self.resume_path):
            return

        try:
            # Find file input elements
            file_inputs = page.locator('input[type="file"]')

            for i in range(file_inputs.count()):
                file_input = file_inputs.nth(i)

                # Check labels to see if this is a resume upload
                parent = file_input.locator('xpath=ancestor::div[contains(@class, "form-section") or contains(@class, "form-element") or contains(@class, "jobs-document-upload")]').first

                is_resume_upload = False
                if parent.count() > 0:
                    parent_text = parent.inner_text(timeout=3000).lower()
                    if any(kw in parent_text for kw in ["resume", "cv", "upload"]):
                        is_resume_upload = True
                        
                        # Check if a resume is ALREADY attached or pre-selected by LinkedIn
                        # Look for common indicators: Remove buttons, Delete buttons, selected cards
                        has_existing = parent.locator(
                            'button[aria-label*="Remove"], '
                            'button[aria-label*="Delete"], '
                            '[aria-checked="true"], '
                            '.jobs-document-upload-rs-card, '
                            'span:has-text("Uploaded on")'
                        )
                        
                        # Only if elements are actually visible/present
                        for j in range(has_existing.count()):
                            if has_existing.nth(j).is_visible():
                                log_info("    Resume already attached/selected. Using existing to avoid re-upload.")
                                is_resume_upload = False  # Cancel upload
                                break

                if is_resume_upload:
                    abs_path = os.path.abspath(self.resume_path)
                    file_input.set_input_files(abs_path)
                    log_success(f"    Uploaded resume: {os.path.basename(abs_path)}")
                    human_delay(1, 2)

        except Exception as e:
            log_warning(f"    Could not upload resume: {e}")

    def _is_review_page(self) -> bool:
        """Check if we're on the final review/submit page or if it's a 1-page form."""
        page = self.page
        try:
            # Look for review header
            review_header = page.locator(
                'h3:has-text("Review"), '
                'h3:has-text("review"), '
                'span:has-text("Review your application")'
            )
            # Look for submit button
            submit_btn = page.locator(
                'button[aria-label="Submit application"], '
                'button[aria-label="Submit"], '
                'button:has-text("Submit application"), '
                'button:has-text("Submit")'
            ).locator('visible=true')
            
            return review_header.count() > 0 or submit_btn.count() > 0
        except Exception:
            return False

    def _has_next_button(self) -> bool:
        """Check if there's a Next button on the current form step."""
        try:
            next_btn = self.page.locator(
                'button[aria-label="Continue to next step"], '
                'button:has-text("Next"), '
                'button:has-text("Review")'
            )
            return next_btn.count() > 0
        except Exception:
            return False

    def _click_next(self):
        """Click the Next button to advance the form."""
        try:
            next_btn = self.page.locator(
                'button[aria-label="Continue to next step"], '
                'button:has-text("Next"), '
                'button:has-text("Review")'
            ).first
            if next_btn.count() > 0:
                next_btn.click()
                log_info("    Clicked Next")
        except Exception as e:
            log_error(f"    Error clicking Next: {e}")

    def _has_form_errors(self) -> bool:
        """Check if the form has visible validation errors."""
        try:
            # LinkedIn uses specific classes for actual validation feedback
            errors = self.page.locator(
                'div.artdeco-inline-feedback--error, '
                'span.artdeco-inline-feedback--error, '
                'p.artdeco-inline-feedback--error, '
                'div[data-test-form-element-error-message]'
            )
            # Only count errors that are actually visible on the screen
            for i in range(errors.count()):
                if errors.nth(i).is_visible():
                    return True
            return False
        except Exception:
            return False

    def _try_fix_errors(self):
        """Attempt to fix form validation errors by filling required fields."""
        # Re-run all fill functions which will target empty required fields
        self._fill_current_form()

    def _submit_application(self) -> bool:
        """Click the submit button on the final review page."""
        page = self.page

        try:
            submit_btn = page.locator(
                'button[aria-label="Submit application"], '
                'button[aria-label="Submit"], '
                'button:has-text("Submit application"), '
                'button:has-text("Submit")'
            ).locator('visible=true').first

            if submit_btn.count() > 0:
                submit_btn.scroll_into_view_if_needed()
                human_delay(0.5, 1.0)
                submit_btn.click()
                log_success("    ✅ Application submitted!")
                human_delay(2, 3)

                # Dismiss any post-submit modal
                self._dismiss_post_submit()
                return True
            else:
                log_error("    Submit button not found")
                return False

        except Exception as e:
            log_error(f"    Error submitting: {e}")
            return False

    def _dismiss_modal(self):
        """Dismiss the Easy Apply modal (e.g., when aborting)."""
        page = self.page

        try:
            # Click dismiss / X button
            dismiss_btn = page.locator(
                'button[aria-label="Dismiss"], '
                'button[data-test-modal-close-btn], '
                'button.artdeco-modal__dismiss'
            ).first

            if dismiss_btn.count() > 0:
                dismiss_btn.click()
                human_delay(0.5, 1.0)

                # Handle "Discard application?" confirmation
                discard_btn = page.locator(
                    'button[data-test-dialog-primary-btn], '
                    'button:has-text("Discard"), '
                    'button:has-text("Yes, discard")'
                ).first

                if discard_btn.count() > 0 and discard_btn.is_visible():
                    discard_btn.click()
                    human_delay(0.5, 1.0)

        except Exception:
            pass

    def _dismiss_post_submit(self):
        """Dismiss any modal that appears after successful submission."""
        page = self.page

        try:
            human_delay(1, 2)
            dismiss_btn = page.locator(
                'button[aria-label="Dismiss"], '
                'button:has-text("Done"), '
                'button:has-text("Not now"), '
                'button.artdeco-modal__dismiss'
            ).first

            if dismiss_btn.count() > 0 and dismiss_btn.is_visible():
                dismiss_btn.click()
                human_delay(0.5, 1.0)
        except Exception:
            pass
