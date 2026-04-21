from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.report import ReportBackgroundRequest, ReportBackgroundResponse
from app.services.report_service import ReportService


router = APIRouter()


@router.post("/background", response_model=ReportBackgroundResponse)
def generate_background(payload: ReportBackgroundRequest, session: Session = Depends(get_session)) -> ReportBackgroundResponse:
    service = ReportService(session)
    return service.generate_background(payload)
