import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("pydantic_settings")

from app.services.report_service import ReportService
from app.schemas.report import ReportBackgroundRequest


class FakeRetrievalService:
    def hybrid_search(self, *args, **kwargs):
        return []


class FakeOllamaService:
    def generate(self, *args, **kwargs):
        return ""



def test_report_service_returns_insufficient_template_when_no_evidence():
    service = ReportService(
        session=None,
        retrieval_service=FakeRetrievalService(),
        ollama_service=FakeOllamaService(),
    )
    response = service.generate_background(
        ReportBackgroundRequest(
            report_type="节能降碳改造项目",
            region="江苏省",
            industry="制造业",
            project_name="高效电机替换项目",
            project_summary="项目拟通过高效电机替换与能管系统建设降低综合能耗。",
            mode="draft",
        )
    )

    assert "依据不足" in response.content
    assert response.mode == "draft"
