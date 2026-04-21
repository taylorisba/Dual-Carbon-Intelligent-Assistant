from pydantic import BaseModel, Field

from app.schemas.common import Citation


class ChatQueryRequest(BaseModel):
    question: str = Field(..., min_length=2)
    region: str | None = None
    industry: str | None = None
    use_query_rewrite: bool = True
    include_debug: bool = True


class RetrievedChunkDebug(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    section_path: str | None = None
    content_preview: str
    keyword_score: float
    semantic_score: float
    final_score: float


class ChatQueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: str
    risk_note: str
    debug: dict[str, list[RetrievedChunkDebug]] | None = None
