from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Citation


class ReportBackgroundRequest(BaseModel):
    report_type: str = Field(..., min_length=2)
    region: str | None = None
    industry: str | None = None
    project_name: str = Field(..., min_length=2)
    project_summary: str = Field(..., min_length=10)
    mode: Literal["draft", "formal"] = "draft"


class ReportBackgroundResponse(BaseModel):
    mode: str
    content: str
    citations: list[Citation]
    risk_note: str
