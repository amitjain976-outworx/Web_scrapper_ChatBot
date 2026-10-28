from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from typing import Optional
import asyncio
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from utils.logger import get_logger

logger = get_logger(__name__)


class PlaywrightManager:
    """
    Manages Playwright browser lifecycle.
    Single browser instance, multiple isolated contexts.
    """

    _playwright = None
    _browser: Optional[Browser] = None
    _lock = asyncio.Lock()

    @classmethod
    async def launch_browser(cls) -> None:
        """
        Launch browser if not already running
        """
        async with cls._lock:
            if cls._browser:
                return

            logger.info("Launching Playwright browser")

            cls._playwright = await async_playwright().start()
            cls._browser = await cls._playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )

    @classmethod
    async def close_browser(cls) -> None:
        """
        Gracefully shutdown browser
        """
        async with cls._lock:
            if cls._browser:
                logger.info("Closing Playwright browser")
                await cls._browser.close()
                cls._browser = None

            if cls._playwright:
                await cls._playwright.stop()
                cls._playwright = None

    @classmethod
    async def new_context(cls) -> BrowserContext:
        if not cls._browser:
            await cls.launch_browser()

        context = await cls._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            ignore_https_errors=True,
        )

        # Global sane defaults
        context.set_default_navigation_timeout(30_000)
        context.set_default_timeout(30_000)

        return context

    @classmethod
    async def new_page(cls) -> Page:
        """
        Create new page in isolated context
        """
        context = await cls.new_context()
        page = await context.new_page()
        await page.set_viewport_size({"width": 1920, "height": 1080})
        return page

    @classmethod
    async def close_context(cls, context: BrowserContext) -> None:
        """
        Close a browser context
        """
        try:
            await context.close()
        except Exception as e:
            logger.warning(f"Failed to close browser context: {e}")

    @classmethod
    async def login(
        cls,
        context: BrowserContext,
        login_config,
        password: str
    ) -> None:
        """
    Perform login using provided selectors and credentials.
    Raises exception if login fails.
        """

        logger.info(f"Logging in via {login_config.login_url}")

        page = await context.new_page()

        try:
            await page.goto(login_config.login_url, wait_until="domcontentloaded")

        # Fill username
            await page.wait_for_selector(login_config.username_selector, timeout=10_000)
            await page.fill(login_config.username_selector, login_config.username)

        # Fill password
            await page.fill(login_config.password_selector, password)

        # Submit
            await page.click(login_config.submit_selector)

        # Wait for navigation / async auth
            await cls._assert_login_success(page, login_config)

            logger.info("Login successful")

        except Exception as e:
            logger.error(f"Login failed: {e}", exc_info=True)
            raise RuntimeError("Authentication failed")

        finally:
            await page.close()
    

    @classmethod
    async def _assert_login_success(cls, page: Page, login_config) -> None:
        """
    Validate login success via selector or URL fragment.
        """

        try:
        # Option 1: success selector exists (preferred)
            if login_config.success_check.startswith(("//", ".", "#", "[")):
                await page.wait_for_selector(
                    login_config.success_check,
                    timeout=15_000,
                )
                return

        # Option 2: success_check is URL fragment
            await page.wait_for_url(
                f"**{login_config.success_check}**",
                timeout=15_000,
            )

        except PlaywrightTimeoutError:
            raise RuntimeError("Login success condition not met")
