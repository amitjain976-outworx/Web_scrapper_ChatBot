from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
import enum

from db.models import UserRole, CrawlStatus


# =========================
# BASE CONFIG
# =========================

class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


# =========================
# AUTH / USER SCHEMAS
# =========================

class UserCreate(BaseSchema):
    username: str
    password: str
    role: UserRole


class UserLogin(BaseSchema):
    username: str
    password: str


class UserResponse(BaseSchema):
    id: UUID
    username: str
    role: UserRole
    is_active: bool
    created_at: datetime

# =========================
# LOGIN CONFIG SCHEMAS
# =========================

class LoginConfigCreate(BaseSchema):
    login_url: HttpUrl

    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)

    username_selector: str = Field(..., min_length=1, max_length=255)
    password_selector: str = Field(..., min_length=1, max_length=255)
    submit_selector: str = Field(..., min_length=1, max_length=255)
    success_check: str = Field(..., min_length=1, max_length=255)

class LoginConfigResponse(BaseSchema):
    login_url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    success_check: str


# =========================
# CRAWL JOB SCHEMAS
# =========================

class CrawlJobCreate(BaseSchema):
    start_url: str
    max_depth: int = Field(..., ge=0, le=10)
    max_pages: Optional[int] = Field(None, ge=1, le=10_000)
    login_config: Optional[LoginConfigCreate] = None

class CrawlJobResponse(BaseSchema):
    id: UUID
    start_url: str
    domain: str
    max_depth: int
    max_pages: Optional[int]
    status: CrawlStatus
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    has_login: bool = False


class CrawlJobStatusResponse(BaseSchema):
    id: UUID
    status: CrawlStatus
    pages_crawled: int
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]


# =========================
# CRAWLED PAGE SCHEMAS
# =========================

class CrawlPageResponse(BaseSchema):
    id: UUID
    url: str
    depth: int
    parent_url: Optional[str]
    http_status: Optional[int]
    is_success: bool
    created_at: datetime


# =========================
# SCREENSHOT CHUNK SCHEMAS
# =========================

class ScreenshotChunkResponse(BaseSchema):
    id: UUID
    image_path: str
    chunk_index: int
    extracted_text: Optional[str]
    vector_id: Optional[UUID]
    created_at: datetime


# =========================
# ADMIN DASHBOARD SCHEMAS
# =========================

class CrawlJobDetailResponse(CrawlJobResponse):
    pages: List[CrawlPageResponse] = []
    login_config: Optional[LoginConfigResponse] = None


# =========================
# CHATBOT (CUSTOMER)
# =========================

class ChatRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"

class ChatQueryRequest(BaseSchema):
    crawl_job_id: UUID
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: Optional[int] = 5
    session_id: Optional[UUID] = None

class ChatSource(BaseSchema):
    url: str
    snippet: str


class ChatSessionCreate(BaseSchema):
    crawl_job_id: UUID

class ChatSessionResponse(BaseSchema):
    id: UUID
    user_id: UUID
    crawl_job_id: UUID

    title: Optional[str]

    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseSchema):
    session_id: UUID
    role: ChatRole
    content: str = Field(..., min_length=1)
    sources: Optional[str] = None  # JSON string


class ChatMessageResponse(BaseSchema):
    id: UUID
    session_id: UUID
    role: ChatRole
    content: str
    sources: Optional[str]
    created_at: datetime


class ChatResponse(BaseSchema):
    session_id: UUID
    answer: str
    sources: List[ChatSource]
    messages: List[ChatMessageResponse]

class ChatHistoryResponse(BaseSchema):
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]

class ChatSessionListResponse(BaseSchema):
    sessions: List[ChatSessionResponse]


# =========================
# GENERIC RESPONSES
# =========================

class MessageResponse(BaseSchema):
    message: str

