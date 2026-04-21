from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(..., min_length=2)
    base_url: str = Field(..., min_length=5)
    source_type: str = "html"
    region: str | None = None
    industry: str | None = None
    crawl_config_json: str | None = None
    enabled: bool = True


class KnowledgeSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    source_type: str
    region: str | None = None
    industry: str | None = None
    crawl_config_json: str | None = None
    enabled: bool
    last_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SyncJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None = None
    job_type: str
    status: str
    message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
