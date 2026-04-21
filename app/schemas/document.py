from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    id: int
    title: str
    source_url: str | None = None
    source_type: str
    region: str | None = None
    industry: str | None = None
    doc_type: str
    publish_date: str | None = None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0


class DocumentUploadResponse(BaseModel):
    created: bool
    message: str
    document: DocumentRead
