from pydantic import BaseModel


class Citation(BaseModel):
    chunk_id: int
    document_id: int
    title: str
    source_url: str | None = None
    source_type: str | None = None
    section_path: str | None = None
    publish_date: str | None = None
    region: str | None = None
    score: float | None = None
