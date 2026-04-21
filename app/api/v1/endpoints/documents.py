from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from app.core.config import get_settings
from app.db.session import get_session
from app.repositories.document_repository import DocumentRepository
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services.ingestion_service import IngestionService
from app.utils.text import format_date


router = APIRouter()
settings = get_settings()



def to_document_read(document, session: Session) -> DocumentRead:
    repository = DocumentRepository(session)
    return DocumentRead(
        id=document.id,
        title=document.title,
        source_url=document.source_url,
        source_type=document.source_type,
        region=document.region,
        industry=document.industry,
        doc_type=document.doc_type,
        publish_date=format_date(document.publish_date),
        status=document.status,
        version=document.version,
        created_at=document.created_at,
        updated_at=document.updated_at,
        chunk_count=repository.count_chunks_by_document(document.id),
    )


@router.get("", response_model=list[DocumentRead])
def list_documents(
    region: str | None = None,
    status: str | None = "active",
    session: Session = Depends(get_session),
) -> list[DocumentRead]:
    repository = DocumentRepository(session)
    documents = repository.list_documents(region=region, status=status)
    return [to_document_read(document, session) for document in documents]


@router.post("/upload", response_model=DocumentUploadResponse)
def upload_document(
    file: UploadFile = File(...),
    region: str | None = Form(None),
    industry: str | None = Form(None),
    doc_type: str = Form("policy"),
    publish_date: str | None = Form(None),
    session: Session = Depends(get_session),
) -> DocumentUploadResponse:
    suffix = Path(file.filename or "upload.bin").suffix
    target_path = Path(settings.uploads_dir) / f"{uuid4().hex}{suffix}"
    with target_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    parsed_publish_date = None
    if publish_date:
        try:
            parsed_publish_date = date.fromisoformat(publish_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"publish_date 格式错误: {exc}") from exc

    try:
        result = IngestionService(session).ingest_file(
            target_path,
            region=region,
            industry=industry,
            doc_type=doc_type,
            publish_date=parsed_publish_date,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return DocumentUploadResponse(
        created=result.created,
        message=result.message,
        document=to_document_read(result.document, session),
    )
