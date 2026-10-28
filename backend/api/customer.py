from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
import json

from db.database import get_db
from db import models, schemas
from auth.routes import get_current_user
from services.vector_service import VectorService
from services.rag_service import RAGService
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/customer", tags=["Customer"])

@router.post(
    "/chat",
    response_model=schemas.ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat_with_website(
    payload: schemas.ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # -----------------------------
    # Validate input
    # -----------------------------
    if not payload.question or not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty",
        )

    logger.info(
        f"Customer {user.id} querying crawl_job={payload.crawl_job_id}, session={payload.session_id}"
    )

    # -----------------------------
    # Validate crawl job
    # -----------------------------
    job = await db.get(models.CrawlJob, payload.crawl_job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Crawl job not found",
        )

    if job.status != models.CrawlStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crawl job is not completed yet",
        )

    # -----------------------------
    # Validate chat session
    # -----------------------------
    session = await db.get(models.ChatSession, payload.session_id)

    if not session or session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )

    # -----------------------------
    # Save user message
    # -----------------------------
    user_message = models.ChatMessage(
        session_id=session.id,
        role="user",
        content=payload.question,
        sources=None,
    )
    db.add(user_message)
    await db.commit()

    # -----------------------------
    # Vector search
    # -----------------------------
    vector_service = VectorService()

    search_results = vector_service.search(
        query_text=payload.question,
        limit=payload.top_k or 5,
        metadata_filter={"crawl_job_id": str(payload.crawl_job_id)},
    )

    # -----------------------------
    # Debug logging: inspect retrieved vectors
    # -----------------------------
    logger.info(f"Retrieved {len(search_results)} vectors")

    for i, ctx in enumerate(search_results):
        logger.info(
            f"[{i}] url={ctx.get('payload', {}).get('url', 'unknown')} | "
            f"text_preview={ctx.get('text', '')[:200]}"
        )

    # -----------------------------
    # No results → fallback response
    # -----------------------------
    if not search_results:
        fallback_text = (
            "I could not find relevant information from the crawled website."
        )

        assistant_message = models.ChatMessage(
            session_id=session.id,
            role="assistant",
            content=fallback_text,
            sources=json.dumps([]),
        )
        db.add(assistant_message)
        await db.commit()

        result = await db.execute(
            select(models.ChatMessage)
            .where(models.ChatMessage.session_id == session.id)
            .order_by(models.ChatMessage.created_at)
        )

        messages = result.scalars().all()

        return schemas.ChatResponse(
            session_id=session.id,
            answer=fallback_text,
            sources=[],
            messages=messages,
        )

    # -----------------------------
    # RAG answer generation
    # -----------------------------
    rag_service = RAGService()

    raw_answer = await rag_service.generate_answer(
        query=payload.question,
        contexts=search_results,
    )

    answer_text = (
        raw_answer.get("answer", "No answer found.")
        if isinstance(raw_answer, dict)
        else str(raw_answer)
    )

    # -----------------------------
    # Build sources
    # -----------------------------
    sources: List[schemas.ChatSource] = []

    for ctx in search_results:
        payload_meta = ctx.get("payload", {})
        text = ctx.get("text", "")

        sources.append(
            schemas.ChatSource(
                url=payload_meta.get("url", "unknown"),
                snippet=text.replace("\n", " ").strip()[:300],
            )
        )

    # -----------------------------
    # Save assistant message
    # -----------------------------
    assistant_message = models.ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_text,
        sources=json.dumps([s.model_dump() for s in sources]),
    )

    db.add(assistant_message)
    await db.commit()

    # -----------------------------
    # Fetch full message history
    # -----------------------------
    result = await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.session_id == session.id)
        .order_by(models.ChatMessage.created_at)
    )

    messages = result.scalars().all()

    # -----------------------------
    # API response
    # -----------------------------
    return schemas.ChatResponse(
        session_id=session.id,
        answer=answer_text,
        sources=sources,
        messages=messages,
    )

@router.get(
    "/crawl-jobs",
    response_model=List[schemas.CrawlJobResponse],
)
async def list_available_crawls(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    List completed crawl jobs available for customer chat
    """

    result = await db.execute(
        select(models.CrawlJob).options(
            selectinload(models.CrawlJob.login_config)
        )
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
    "/chat-sessions",
    response_model=schemas.ChatSessionResponse,
    status_code=201,
)
async def create_chat_session(
    crawl_job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    job = await db.get(models.CrawlJob, crawl_job_id)

    if not job or job.status != models.CrawlStatus.COMPLETED:
        raise HTTPException(400, "Invalid or incomplete crawl job")

    session = models.ChatSession(
        user_id=user.id,
        crawl_job_id=crawl_job_id,
        title=f"Chat for {job.domain}",
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session


@router.get(
    "/chat-sessions",
    response_model=List[schemas.ChatSessionResponse],
)
async def list_chat_sessions(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(models.ChatSession)
        .where(models.ChatSession.user_id == user.id)
        .order_by(models.ChatSession.created_at.desc())
    )
    return result.scalars().all()


@router.get(
    "/chat-sessions/{session_id}/messages",
    response_model=List[schemas.ChatMessageResponse],
)
async def get_chat_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    session = await db.get(models.ChatSession, session_id)

    if not session or session.user_id != user.id:
        raise HTTPException(404, "Chat session not found")

    result = await db.execute(
        select(models.ChatMessage)
        .where(models.ChatMessage.session_id == session_id)
        .order_by(models.ChatMessage.created_at)
    )
    return result.scalars().all()

