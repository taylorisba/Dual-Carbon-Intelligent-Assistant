from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.system import EmbeddingConfigRead, EmbeddingConfigUpdate, EmbeddingConfigUpdateResponse, EmbeddingRebuildResponse
from app.services.system_config_service import SystemConfigService


router = APIRouter()


@router.get("/config", response_model=EmbeddingConfigRead)
def get_config() -> EmbeddingConfigRead:
    return SystemConfigService().get_embedding_config()


@router.post("/config/embedding", response_model=EmbeddingConfigUpdateResponse)
def update_embedding_config(payload: EmbeddingConfigUpdate) -> EmbeddingConfigUpdateResponse:
    config = SystemConfigService().update_embedding_config(payload)
    return EmbeddingConfigUpdateResponse(message="embedding 配置已更新", config=config)


@router.post("/rebuild-embeddings", response_model=EmbeddingRebuildResponse)
def rebuild_embeddings(session: Session = Depends(get_session)) -> EmbeddingRebuildResponse:
    return SystemConfigService().rebuild_embeddings(session)
