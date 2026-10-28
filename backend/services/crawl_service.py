import asyncio
from collections import deque
from typing import Set

from sqlalchemy.ext.asyncio import AsyncSession

from browser.playwright_manager import PlaywrightManager
from utils.url_utils import filter_and_normalize_links
from utils.file_utils import get_screenshot_path
from utils.logger import get_logger
from workers.vision_worker import VisionWorker

from db import models
from config import settings

logger = get_logger(__name__)


VISION_SEMAPHORE = asyncio.Semaphore(5)

async def limited_process_page(page_id):
    async with VISION_SEMAPHORE:
        await VisionWorker.process_page(page_id)

class CrawlService:
    """
    BFS-based crawler with depth control and screenshot capture
    """

    def __init__(self, db: AsyncSession, job: models.CrawlJob, login_config: models.LoginConfig | None = None, login_password: str | None = None):
        self.db = db
        self.job = job
        self.login_config = login_config
        self.login_password = login_password
        self.visited: Set[str] = set()
        self.failed_pages = 0
        self.pages_crawled = 0
        self.context = None
        self.vision_tasks: list[asyncio.Task] = []

    # =========================
    # ENTRYPOINT
    # =========================

    async def run(self) -> None:
        logger.info(f"Starting crawl job {self.job.id}")

        self.job.status = models.CrawlStatus.RUNNING
        await self.db.commit()

        await PlaywrightManager.launch_browser()

        self.context = await PlaywrightManager.new_context()

        # Perform login if configured
        if self.login_config:
            logger.info("Login config found. Attempting login.")
            await PlaywrightManager.login(
                context=self.context,
                login_config=self.login_config,
                password=self.login_password
            )

        queue = deque([(self.job.start_url, 0, None)])

        try:
            while queue:

                if self.pages_crawled >= self.job.max_pages:
                    logger.info("Max pages limit reached, stopping crawl")
                    break

                url, depth, parent_url = queue.popleft()

                if depth > self.job.max_depth:
                    continue

                if url in self.visited:
                    continue

                self.visited.add(url)

                try:
                    self.pages_crawled += 1
                    page_links = await self._crawl_page(url, depth, parent_url)
                    
                    for link in page_links:
                        if (
                            link not in self.visited
                            and self.pages_crawled < self.job.max_pages
                        ):
                            queue.append((link, depth + 1, url))

                except Exception:
                    self.failed_pages += 1
                    logger.exception(f"Failed crawling {url}")

        finally:
            if self.context:
                await PlaywrightManager.close_context(self.context)

        # Final job status
        self.job.status = (
            models.CrawlStatus.FAILED
            if self.failed_pages > 0
            else models.CrawlStatus.COMPLETED
        )

        if self.vision_tasks:
            await asyncio.gather(*self.vision_tasks, return_exceptions=True)

        await self.db.commit()
        logger.info(f"Crawl job {self.job.id} finished. Pages crawled: {self.pages_crawled}")

    # =========================
    # PAGE CRAWL
    # =========================

    async def _crawl_page(self, url: str, depth: int, parent_url: str | None) -> Set[str]:
        logger.debug(f"Crawling page: {url}")

        page = await self.context.new_page()

        crawl_page = models.CrawlPage(
            crawl_job_id=self.job.id,
            url=url,
            depth=depth,
            parent_url=parent_url,
        )

        self.db.add(crawl_page)
        await self.db.flush()  # get crawl_page.id

        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=settings.PAGE_TIMEOUT_MS)
            await page.wait_for_timeout(settings.SCREENSHOT_DELAY_MS)

            crawl_page.http_status = response.status if response else None
            crawl_page.is_success = bool(response and response.ok)

            # Screenshot
            screenshot_path = get_screenshot_path(
                job_id=self.job.id,
                page_id=crawl_page.id,
                chunk_index=1,
            )

            await page.screenshot(path=str(screenshot_path), full_page=True)

            logger.info(f"Captured screenshot for page {url} -> {screenshot_path}")

            screenshot_chunk = models.ScreenshotChunk(
                page_id=crawl_page.id,
                image_path=str(screenshot_path),
                chunk_index=1,
            )

            self.db.add(screenshot_chunk)

            await self.db.commit()

            task = asyncio.create_task(limited_process_page(crawl_page.id))
            self.vision_tasks.append(task)

            # Extract links
            raw_links = await page.eval_on_selector_all(
                "a",
                "els => els.map(e => e.getAttribute('href'))",
            )

            links = filter_and_normalize_links(
                base_url=url,
                links=set(raw_links),
                root_domain=self.job.start_url,
            )

            logger.debug(f"Extracted {len(links)} links from {url}")

            return links

        except Exception as e:
            crawl_page.is_success = False
            await self.db.commit()
            logger.warning(f"Page crawl failed but continuing: {url} | {e}")
            return set()

        finally:
            await page.close()
