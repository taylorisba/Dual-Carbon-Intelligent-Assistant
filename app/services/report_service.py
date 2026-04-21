from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.schemas.report import ReportBackgroundRequest, ReportBackgroundResponse
from app.services.ollama_service import OllamaService, OllamaServiceError
from app.services.retrieval_service import RetrievalService, SearchResult
from app.utils.text import parse_json_object


class ReportService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        retrieval_service: RetrievalService | None = None,
        ollama_service: OllamaService | None = None,
    ):
        self.settings = settings or get_settings()
        self.retrieval_service = retrieval_service or RetrievalService(session, self.settings)
        self.ollama_service = ollama_service or OllamaService(self.settings)
        template_dir = Path(__file__).resolve().parents[1] / "templates"
        self.templates = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def generate_background(self, request: ReportBackgroundRequest) -> ReportBackgroundResponse:
        query = " ".join(
            item for item in [request.report_type, request.region, request.industry, request.project_name, request.project_summary] if item
        )
        results = self.retrieval_service.hybrid_search(query, region=request.region, industry=request.industry)
        citations = [item.to_citation() for item in results[: self.settings.max_citations]]

        if not results or results[0].final_score < self.settings.min_answerable_score:
            content = self._render_output(
                request=request,
                policy_background="依据不足，无法判断当前项目在本地区、本行业的直接政策背景，请先补充知识库。",
                necessity="当前知识库证据不足，建议补充地方政策、专项通知和行业标准后再生成正式版本。",
                policy_basis_summary="暂无足够政策依据。",
                citations=citations,
            )
            return ReportBackgroundResponse(
                mode=request.mode,
                content=content,
                citations=citations,
                risk_note="当前报告背景基于有限证据生成，不能替代正式政策审查。",
            )

        sections = self._generate_sections(request, results)
        draft_content = self._render_output(
            request=request,
            policy_background=sections["policy_background"],
            necessity=sections["necessity"],
            policy_basis_summary=sections["policy_basis_summary"],
            citations=citations,
        )

        if request.mode == "formal":
            try:
                polished = self._polish_report(draft_content, request)
                return ReportBackgroundResponse(
                    mode=request.mode,
                    content=polished,
                    citations=citations,
                    risk_note="正式版已按书面表达进行润色，使用前仍建议核对原始政策。",
                )
            except OllamaServiceError:
                return ReportBackgroundResponse(
                    mode=request.mode,
                    content=draft_content,
                    citations=citations,
                    risk_note="润色阶段模型服务不可用，已返回初稿版本。",
                )

        return ReportBackgroundResponse(
            mode=request.mode,
            content=draft_content,
            citations=citations,
            risk_note="初稿已基于检索证据生成，建议结合企业实际情况继续编辑。",
        )

    def _generate_sections(self, request: ReportBackgroundRequest, results: list[SearchResult]) -> dict[str, str]:
        evidence_lines = [
            f"- 《{item.title}》{item.section_path or '正文'}：{item.content[:180]}"
            for item in results[: self.settings.max_citations + 1]
        ]
        prompt = self.templates.get_template("report_generation_prompt.jinja2").render(
            report_type=request.report_type,
            region=request.region or "未指定地区",
            industry=request.industry or "未指定行业",
            project_name=request.project_name,
            project_summary=request.project_summary,
            evidence_lines=evidence_lines,
        )
        try:
            raw = self.ollama_service.generate(prompt)
            parsed = parse_json_object(raw) or {}
        except OllamaServiceError:
            parsed = {}

        if parsed.get("policy_background") and parsed.get("necessity"):
            return {
                "policy_background": str(parsed["policy_background"]),
                "necessity": str(parsed["necessity"]),
                "policy_basis_summary": str(parsed.get("policy_basis_summary") or "\n".join(evidence_lines)),
            }

        return {
            "policy_background": f"结合已检索政策，{request.region or '相关地区'}正持续推进节能降碳、绿色制造与高质量发展，{request.project_name}与当前双碳导向具有较强一致性。",
            "necessity": f"从项目特征看，{request.project_name}围绕{request.report_type}展开，结合{request.industry or '所在行业'}节能降碳要求，具备明确的政策驱动和实施必要性。",
            "policy_basis_summary": "\n".join(evidence_lines),
        }

    def _polish_report(self, draft_content: str, request: ReportBackgroundRequest) -> str:
        prompt = self.templates.get_template("report_polish_prompt.jinja2").render(
            project_name=request.project_name,
            report_type=request.report_type,
            draft_content=draft_content,
        )
        polished = self.ollama_service.generate(prompt)
        return polished or draft_content

    def _render_output(
        self,
        *,
        request: ReportBackgroundRequest,
        policy_background: str,
        necessity: str,
        policy_basis_summary: str,
        citations,
    ) -> str:
        template = self.templates.get_template("report_background.jinja2")
        return template.render(
            report_type=request.report_type,
            region=request.region or "未指定地区",
            industry=request.industry or "未指定行业",
            project_name=request.project_name,
            project_summary=request.project_summary,
            policy_background=policy_background,
            necessity=necessity,
            policy_basis_summary=policy_basis_summary,
            citations=citations,
        )
