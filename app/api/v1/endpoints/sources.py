from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.source import KnowledgeSourceCreate, KnowledgeSourceRead, SyncJobRead
from app.services.sync_service import SyncService


router = APIRouter()


@router.get("", response_model=list[KnowledgeSourceRead])
def list_sources(session: Session = Depends(get_session)) -> list[KnowledgeSourceRead]:
    service = SyncService(session)
    return [KnowledgeSourceRead.model_validate(item) for item in service.list_sources()]


@router.post("", response_model=KnowledgeSourceRead)
def create_source(payload: KnowledgeSourceCreate, session: Session = Depends(get_session)) -> KnowledgeSourceRead:
    service = SyncService(session)
    source = service.create_source(payload)
    return KnowledgeSourceRead.model_validate(source)


@router.post("/{source_id}/sync", response_model=SyncJobRead)
def sync_source(source_id: int, session: Session = Depends(get_session)) -> SyncJobRead:
    service = SyncService(session)
    try:
        job = service.sync_source(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SyncJobRead.model_validate(job)
