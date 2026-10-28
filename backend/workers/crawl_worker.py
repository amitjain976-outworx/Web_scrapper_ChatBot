import asyncio
from typing import Optional
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from db.database import AsyncSessionLocal
from db import models
from services.crawl_service import CrawlService
from utils.logger import get_logger
from utils.crypto import decrypt_secret

logger = get_logger(__name__)


class CrawlWorker:
    """
    Background worker for executing crawl jobs
    """

    @staticmethod
    async def run_job(job_id: UUID) -> None:
        """
        Entry point to execute a crawl job
        """
        logger.info(f"Worker started for crawl job {job_id}")

        async with AsyncSessionLocal() as db:
            job = await CrawlWorker._fetch_job(db, job_id)

            if not job:
                logger.error(f"Crawl job {job_id} not found")
                return

            login_password = None

            if job.login_config:
                login_password = decrypt_secret(
                    job.login_config.encrypted_password
                )

            if job.status != models.CrawlStatus.PENDING:

                logger.warning(
                    f"Crawl job {job_id} has invalid status {job.status}"
                )
                return

            try:
                job.status = models.CrawlStatus.RUNNING
                job.started_at = datetime.utcnow()
                await db.commit()

                crawler = CrawlService(db=db, job=job, login_config=job.login_config, login_password=login_password,)
                await crawler.run()

                job.finished_at = datetime.utcnow()
                await db.commit()

                logger.info(f"Crawl job {job_id} finished with status {job.status}")

            except Exception as e:
                logger.error(
                    f"Crawl job {job_id} failed: {e}",
                    exc_info=True,
                )
                job.status = models.CrawlStatus.FAILED
                job.error_message = str(e)
                job.finished_at = datetime.utcnow()
                await db.commit()

        logger.info(f"Worker finished for crawl job {job_id}")

    # =========================
    # HELPERS
    # =========================

    @staticmethod
    async def _fetch_job(
        db: AsyncSession,
        job_id: UUID,
    ) -> Optional[models.CrawlJob]:
        result = await db.execute(
            select(models.CrawlJob)
            .options(selectinload(models.CrawlJob.login_config))
            .where(models.CrawlJob.id == job_id)
        )
        return result.scalars().first()
