from sqlalchemy import (Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Enum, Index)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from .database import Base


# =========================
# ENUMS
# =========================

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"

class CrawlStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


# =========================
# USER MODEL
# =========================

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    crawl_jobs = relationship("CrawlJob", back_populates="created_by_user")


# =========================
# CRAWL JOB
# =========================

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    start_url = Column(Text, nullable=False)
    domain = Column(String(255), nullable=False)

    max_depth = Column(Integer, nullable=False)
    max_pages = Column(Integer, nullable=True)

    status = Column(Enum(CrawlStatus), default=CrawlStatus.PENDING, index=True)
    error_message = Column(Text, nullable=True)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    finished_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    created_by_user = relationship("User", back_populates="crawl_jobs")
    pages = relationship(
        "CrawlPage",
        back_populates="crawl_job",
        cascade="all, delete-orphan"
    )

    login_config = relationship(
        "LoginConfig",
        back_populates="crawl_job",
        uselist=False,
        cascade="all, delete-orphan"
    )


# =========================
# LOGIN CONFIG (OPTIONAL)
# =========================

class LoginConfig(Base):
    __tablename__ = "login_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    crawl_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    login_url = Column(Text, nullable=False)

    username_selector = Column(String(255), nullable=False)
    password_selector = Column(String(255), nullable=False)
    submit_selector = Column(String(255), nullable=False)
    success_check = Column(String(255), nullable=False)

    # Credentials (DO NOT store plaintext)
    username = Column(String(255), nullable=False)
    encrypted_password = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    crawl_job = relationship("CrawlJob", back_populates="login_config")


# =========================
# CRAWLED PAGE
# =========================

class CrawlPage(Base):
    __tablename__ = "crawl_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crawl_job_id = Column(UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False)

    url = Column(Text, nullable=False)
    depth = Column(Integer, nullable=False)
    parent_url = Column(Text, nullable=True)

    http_status = Column(Integer, nullable=True)
    is_success = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    crawl_job = relationship("CrawlJob", back_populates="pages")
    screenshots = relationship(
        "ScreenshotChunk",
        back_populates="page",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_crawl_job_url", "crawl_job_id", "url", unique=True),
    )


# =========================
# SCREENSHOT CHUNKS
# =========================

class ScreenshotChunk(Base):
    __tablename__ = "screenshot_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    page_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crawl_pages.id", ondelete="CASCADE"),
        nullable=False
    )

    image_path = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)

    extracted_text = Column(Text, nullable=True)

    # Reference to vector in Qdrant
    vector_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    page = relationship("CrawlPage", back_populates="screenshots")

    __table_args__ = (
        Index("idx_page_chunk", "page_id", "chunk_index", unique=True),
    )

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    crawl_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crawl_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user = relationship("User")
    crawl_job = relationship("CrawlJob")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(
        Enum("user", "assistant", name="chat_role"),
        nullable=False,
    )

    content = Column(Text, nullable=False)

    # Stored only for assistant messages
    sources = Column(
        Text,  # JSON string
        nullable=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
