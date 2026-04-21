from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel

from app.utils.time import utc_now


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    source_url: Optional[str] = Field(default=None, index=True)
    source_site: Optional[str] = None
    source_type: str = Field(default="upload", index=True)
    local_path: Optional[str] = None
    region: Optional[str] = Field(default=None, index=True)
    industry: Optional[str] = Field(default=None, index=True)
    doc_type: str = Field(default="policy", index=True)
    publish_date: Optional[date] = Field(default=None, index=True)
    effective_date: Optional[date] = None
    status: str = Field(default="active", index=True)
    content_hash: str = Field(index=True)
    version: int = Field(default=1)
    raw_text: str
    summary: Optional[str] = None
    extra_metadata: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Chunk(SQLModel, table=True):
    __tablename__ = "chunks"

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="documents.id", index=True)
    chunk_index: int = Field(index=True)
    section_path: Optional[str] = None
    content: str
    token_count: int
    keywords: Optional[str] = None
    embedding_path: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeSource(SQLModel, table=True):
    __tablename__ = "knowledge_sources"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    base_url: str
    source_type: str = Field(default="html", index=True)
    region: Optional[str] = Field(default=None, index=True)
    industry: Optional[str] = Field(default=None, index=True)
    crawl_config_json: Optional[str] = None
    enabled: bool = Field(default=True, index=True)
    last_sync_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class SyncJob(SQLModel, table=True):
    __tablename__ = "sync_jobs"

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[int] = Field(default=None, foreign_key="knowledge_sources.id", index=True)
    job_type: str = Field(default="manual", index=True)
    status: str = Field(default="running", index=True)
    message: Optional[str] = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)


class QALog(SQLModel, table=True):
    __tablename__ = "qa_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    rewritten_question: Optional[str] = None
    answer: str
    retrieved_chunk_ids: Optional[str] = None
    latency_ms: Optional[int] = None
    confidence: Optional[str] = None
    risk_note: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
