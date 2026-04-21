from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.chat import ChatQueryRequest, ChatQueryResponse
from app.services.qa_service import QAService


router = APIRouter()


@router.post("/query", response_model=ChatQueryResponse)
def query_chat(payload: ChatQueryRequest, session: Session = Depends(get_session)) -> ChatQueryResponse:
    service = QAService(session)
    return service.answer_question(
        question=payload.question,
        region=payload.region,
        industry=payload.industry,
        use_query_rewrite=payload.use_query_rewrite,
        include_debug=payload.include_debug,
    )
