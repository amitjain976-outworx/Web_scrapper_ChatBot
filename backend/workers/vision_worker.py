import asyncio
from uuid import UUID
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from db.database import AsyncSessionLocal
from db import models
from utils.logger import get_logger
from services.vision_service import image_to_text as vision_service_image_to_text
from services.vector_service import VectorService

logger = get_logger(__name__)

# Limit concurrent vision processing (GPU / CPU safety)
vision_semaphore = asyncio.Semaphore(1)

# Initialize VectorService once (Chroma is local + sync)
vector_service = VectorService()


class VisionWorker:
    """
    Vision pipeline worker:
    ScreenshotChunk → Image-to-Text → Vector DB (Chroma)
    """

    # =========================
    # PUBLIC ENTRYPOINT
    # =========================

    @staticmethod
    async def process_page(page_id: UUID) -> None:
        logger.info(f"[VisionWorker] Started processing page {page_id}")

        async with AsyncSessionLocal() as db:
            page = await VisionWorker._fetch_page(db, page_id)

            if not page:
                logger.warning(f"[VisionWorker] Page {page_id} not found")
                return

            if not page.screenshots:
                logger.warning(f"[VisionWorker] No screenshots for page {page_id}")
                return

            for chunk in page.screenshots:
                try:
                    async with vision_semaphore:
                        await VisionWorker._process_chunk(db, page, chunk)
                except Exception as e:
                    logger.error(
                        f"[VisionWorker] Error processing chunk {chunk.id}: {e}",
                        exc_info=True,
                    )

            await db.commit()

        logger.info(f"[VisionWorker] Completed processing page {page_id}")

    # =========================
    # INTERNAL HELPERS
    # =========================

    @staticmethod
    async def _fetch_page(
        db: AsyncSession,
        page_id: UUID,
    ) -> models.CrawlPage | None:
        result = await db.execute(
            select(models.CrawlPage)
            .where(models.CrawlPage.id == page_id)
            .options(selectinload(models.CrawlPage.screenshots))
        )
        return result.scalars().first()

    # =========================
    # CHUNK PIPELINE
    # =========================

    @staticmethod
    async def _process_chunk(
        db: AsyncSession,
        page: models.CrawlPage,
        chunk: models.ScreenshotChunk,
    ) -> None:
        if not chunk.image_path:
            return

        image_path = Path(chunk.image_path)

        if not image_path.exists():
            logger.warning(f"[VisionWorker] Image not found: {image_path}")
            return

        logger.info(
            f"[VisionWorker] Processing chunk {chunk.chunk_index} | page={page.id}"
        )

        # 1️⃣ Image → Text
        extracted_text = await vision_service_image_to_text(str(image_path))

        if not extracted_text:
            logger.warning(f"[VisionWorker] Empty text for chunk {chunk.id}")
            return

        chunk.extracted_text = extracted_text

        # embedding = await VisionWorker._create_embedding(extracted_text)

        # 2️⃣ Store in Vector DB (Chroma auto-embeds)
        try:
            vector_id = vector_service.upsert_text(
                text=extracted_text,
                payload={
                    "crawl_job_id": str(page.crawl_job_id),
                    "page_id": str(page.id),
                    "chunk_id": str(chunk.id),
                    "url": page.url,
                    "depth": page.depth,
                    "chunk_index": chunk.chunk_index,
                    "source": "vision", 
                },
            )

            chunk.vector_id = vector_id
            db.add(chunk)

        except Exception as e:
            logger.error(
                f"[VisionWorker] Failed to store vector for chunk {chunk.id}: {e}",
                exc_info=True,
            )
