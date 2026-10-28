import asyncio
from typing import List
from uuid import UUID

from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.database import get_db
from db import models, schemas
from auth.routes import require_admin
from workers.crawl_worker import CrawlWorker
from utils.logger import get_logger
from utils.crypto import encrypt_secret

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post(
    "/crawl/start",
    response_model=schemas.CrawlJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_crawl(
    payload: schemas.CrawlJobCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """
    Admin starts a new crawl job (optionally authenticated)
    """

    job = models.CrawlJob(
        start_url=str(payload.start_url),
        domain=urlparse(payload.start_url).netloc,
        max_depth=payload.max_depth,
        max_pages=payload.max_pages,
        status=models.CrawlStatus.PENDING,
        created_by=admin.id,
    )

    db.add(job)
    await db.flush()  # IMPORTANT: get job.id before commit

    # -----------------------------
    # OPTIONAL LOGIN CONFIG
    # -----------------------------
    if payload.login_config:
        encrypted_password = encrypt_secret(
            payload.login_config.password
        )

        login_config = models.LoginConfig(
            crawl_job_id=job.id,
            login_url=str(payload.login_config.login_url),
            username=payload.login_config.username,
            encrypted_password=encrypted_password,
            username_selector=payload.login_config.username_selector,
            password_selector=payload.login_config.password_selector,
            submit_selector=payload.login_config.submit_selector,
            success_check=payload.login_config.success_check,
        )

        db.add(login_config)

    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(CrawlWorker.run_job, job.id)

    logger.info(
        f"Admin {admin.id} started crawl job {job.id} "
        f"(login={'yes' if payload.login_config else 'no'})"
    )

    # Fire-and-forget background crawl
    # asyncio.create_task(CrawlWorker.run_job(job.id))

    return schemas.CrawlJobResponse(
        **job.__dict__,
        has_login=payload.login_config is not None
    )


@router.get(
    "/crawl/{job_id}",
    response_model=schemas.CrawlJobResponse,
)
async def get_crawl_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    result = await db.execute(
        select(models.CrawlJob).where(models.CrawlJob.id == job_id)
    )
    job = result.scalars().first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawl job not found",
        )

    return schemas.CrawlJobResponse(
        **job.__dict__,
        has_login=job.login_config is not None
    )

@router.get(
    "/crawls",
    response_model=List[schemas.CrawlJobResponse],
)
async def list_crawl_jobs(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    result = await db.execute(
        select(models.CrawlJob)
        .options(selectinload(models.CrawlJob.login_config))
        .order_by(models.CrawlJob.created_at.desc())
    )

    jobs = result.scalars().all()

    return [
        schemas.CrawlJobResponse(
            **job.__dict__,
            has_login=job.login_config is not None
        )
        for job in jobs
    ]

@router.post(
    "/crawl/{job_id}/stop",
    response_model=schemas.CrawlJobResponse,
)
async def stop_crawl(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    result = await db.execute(
        select(models.CrawlJob).where(models.CrawlJob.id == job_id)
    )
    job = result.scalars().first()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawl job not found",
        )

    if job.status in {
        models.CrawlStatus.COMPLETED,
        models.CrawlStatus.FAILED,
        models.CrawlStatus.STOPPED,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop job in status {job.status}",
        )

    job.status = models.CrawlStatus.STOPPED
    await db.commit()
    await db.refresh(job)

    logger.warning(f"Crawl job {job_id} stopped by admin {admin.id}")

    return job
