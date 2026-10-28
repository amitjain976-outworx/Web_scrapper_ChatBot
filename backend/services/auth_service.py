import os
from typing import Optional

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from browser.playwright_manager import PlaywrightManager
from db.models import CrawlJob
from utils.logger import get_logger

logger = get_logger(__name__)


class LoginFailedError(Exception):
    """Raised when login attempt fails"""


class AuthService:
    """
    Handles authenticated login for crawl jobs using Playwright.
    """

    @staticmethod
    async def perform_login(job: CrawlJob) -> Optional[str]:
        """
        Perform login for a crawl job.
        Returns path to storage_state.json if successful.
        Raises LoginFailedError on failure.
        """

        if not job.requires_login:
            logger.info(f"Crawl job {job.id} does not require login")
            return None

        logger.info(f"Starting login for crawl job {job.id}")

        # =========================
        # PREPARE STORAGE PATH
        # =========================

        os.makedirs("storage/auth", exist_ok=True)
        storage_path = f"storage/auth/{job.id}.json"

        # =========================
        # CREATE CONTEXT (NO AUTH)
        # =========================

        context = await PlaywrightManager.new_context()
        page: Page = await context.new_page()

        try:
            # =========================
            # LOAD LOGIN PAGE
            # =========================

            await page.goto(job.login_url, wait_until="domcontentloaded")

            # =========================
            # FILL LOGIN FORM
            # =========================

            await page.fill(job.username_selector, job.username)
            await page.fill(job.password_selector, job.password)

            # Submit login form
            await page.click(job.submit_selector)

            # =========================
            # VERIFY POST-LOGIN STATE
            # =========================

            try:
                if job.post_login_selector:
                    # Best: wait for known post-login element
                    await page.wait_for_selector(
                        job.post_login_selector,
                        timeout=15000,
                    )
                else:
                    # Fallback: ensure URL changed from login page
                    await page.wait_for_function(
                        "loginUrl => !window.location.href.includes(loginUrl)",
                        job.login_url,
                        timeout=15000,
                    )

            except PlaywrightTimeoutError:
                raise LoginFailedError(
                    "Post-login condition not met (still unauthenticated)"
                )

            # =========================
            # VERIFY AUTH COOKIES
            # =========================

            cookies = await context.cookies()
            if not cookies:
                raise LoginFailedError("No cookies found after login")

            logger.info(
                f"Auth cookies detected: {[c['name'] for c in cookies]}"
            )

            # =========================
            # SAVE AUTH STATE
            # =========================

            await PlaywrightManager.save_storage_state(
                context,
                storage_path,
            )

            logger.info(f"Login successful for crawl job {job.id}")
            return storage_path

        except PlaywrightTimeoutError:
            logger.exception("Login timed out")
            raise LoginFailedError("Login timed out")

        except LoginFailedError:
            raise

        except Exception as e:
            logger.exception(f"Login failed: {e}")
            raise LoginFailedError(str(e))

        finally:
            await PlaywrightManager.close_context(context)
