from __future__ import annotations

import json
import time

from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.models.db_models import QALog
from app.repositories.qa_log_repository import QALogRepository
from app.schemas.chat import ChatQueryResponse, RetrievedChunkDebug
from app.services.ollama_service import OllamaService, OllamaServiceError
from app.services.retrieval_service import RetrievalService, SearchResult
from app.utils.text import parse_json_object


INSUFFICIENT_ANSWER = "依据不足，无法判断。"


class QAService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        retrieval_service: RetrievalService | None = None,
        ollama_service: OllamaService | None = None,
    ):
        self.session = session
        self.settings = settings or get_settings()
        self.retrieval_service = retrieval_service or RetrievalService(session, self.settings)
        self.ollama_service = ollama_service or OllamaService(self.settings)
        self.log_repository = QALogRepository(session)

    def answer_question(
        self,
        *,
        question: str,
        region: str | None = None,
        industry: str | None = None,
        use_query_rewrite: bool = True,
        include_debug: bool = True,
    ) -> ChatQueryResponse:
        start = time.perf_counter()
        rewritten_question = self._rewrite_question(question, region, industry) if use_query_rewrite else question
        results = self.retrieval_service.hybrid_search(rewritten_question, region=region, industry=industry)

        if not results or results[0].final_score < self.settings.min_answerable_score:
            response = ChatQueryResponse(
                answer=INSUFFICIENT_ANSWER,
                citations=[item.to_citation() for item in results[: self.settings.max_citations]],
                confidence="low",
                risk_note="当前知识库证据不足，请补充地区、行业或导入更具体的政策文件。",
                debug=self._build_debug_payload(results) if include_debug else None,
            )
            self._log(question, rewritten_question, response, results, start)
            return response

        context = self.retrieval_service.build_context(results)
        response = self._answer_with_model(question, rewritten_question, context, results, include_debug)
        self._log(question, rewritten_question, response, results, start)
        return response

    def _rewrite_question(self, question: str, region: str | None, industry: str | None) -> str:
        if not self.settings.query_rewrite_enabled:
            return question
        parts = [question.strip()]
        if region and region not in question:
            parts.append(f"地区：{region}")
        if industry and industry not in question:
            parts.append(f"行业：{industry}")
        return " | ".join(parts)

    def _answer_with_model(
        self,
        question: str,
        rewritten_question: str,
        context: str,
        results: list[SearchResult],
        include_debug: bool,
    ) -> ChatQueryResponse:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是企业双碳政策问答助手。"
                    "只能依据提供的检索证据回答，不允许编造。"
                    "如果证据不足，根据材料酌情分析。"
                    "请输出 JSON，字段为 answer、confidence、risk_note。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：{question}\n"
                    f"检索后的问题：{rewritten_question}\n"
                    f"证据上下文：\n{context}\n\n"
                    "请严格依据上述证据生成结论，不要引用未提供的政策。"
                ),
            },
        ]

        citations = [item.to_citation() for item in results[: self.settings.max_citations]]
        try:
            raw_text = self.ollama_service.chat(messages)
            parsed = parse_json_object(raw_text) or {}
            answer = str(parsed.get("answer") or raw_text or "").strip()
            confidence = str(parsed.get("confidence") or self._confidence_from_score(results[0].final_score)).lower()
            risk_note = str(parsed.get("risk_note") or "回答仅基于已检索到的政策片段，请结合原文复核。")
        except OllamaServiceError:
            answer = self._build_fallback_answer(results)
            confidence = self._confidence_from_score(results[0].final_score)
            risk_note = "模型服务不可用，已返回基于检索证据的摘要，请在 Ollama 就绪后再生成正式答案。"

        if INSUFFICIENT_ANSWER in answer:
            confidence = "low"

        return ChatQueryResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            risk_note=risk_note,
            debug=self._build_debug_payload(results) if include_debug else None,
        )

    def _build_fallback_answer(self, results: list[SearchResult]) -> str:
        lines = []
        for item in results[:2]:
            lines.append(f"《{item.title}》{item.section_path or '正文'}提到：{item.content[:120]}。")
        return "根据当前检索到的政策依据，可参考以下要点：\n" + "\n".join(lines)

    def _confidence_from_score(self, score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.55:
            return "medium"
        return "low"

    def _build_debug_payload(self, results: list[SearchResult]) -> dict[str, list[RetrievedChunkDebug]]:
        return {
            "retrieved_chunks": [
                RetrievedChunkDebug(
                    chunk_id=item.chunk_id,
                    document_id=item.document_id,
                    title=item.title,
                    section_path=item.section_path,
                    content_preview=item.content[:180],
                    keyword_score=round(item.keyword_score, 4),
                    semantic_score=round(item.semantic_score, 4),
                    final_score=round(item.final_score, 4),
                )
                for item in results
            ]
        }

    def _log(
        self,
        question: str,
        rewritten_question: str,
        response: ChatQueryResponse,
        results: list[SearchResult],
        start: float,
    ) -> None:
        latency_ms = int((time.perf_counter() - start) * 1000)
        log = QALog(
            question=question,
            rewritten_question=rewritten_question,
            answer=response.answer,
            retrieved_chunk_ids=json.dumps([item.chunk_id for item in results], ensure_ascii=False),
            latency_ms=latency_ms,
            confidence=response.confidence,
            risk_note=response.risk_note,
        )
        self.log_repository.create_log(log)
