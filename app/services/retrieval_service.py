from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

import numpy as np

from app.core.config import Settings, get_settings
from app.repositories.document_repository import DocumentRepository
from app.schemas.common import Citation
from app.services.embedding_service import EmbeddingService
from app.services.ollama_service import OllamaService
from app.services.vector_store import LocalVectorStore
from app.utils.text import format_date


@dataclass(slots=True)
class SearchResult:
    chunk_id: int
    document_id: int
    chunk_index: int
    title: str
    content: str
    section_path: str | None
    token_count: int
    keywords: str | None
    embedding_path: str | None
    source_url: str | None
    source_type: str | None
    region: str | None
    industry: str | None
    doc_type: str | None
    publish_date: date | str | None
    keyword_score: float = 0.0
    semantic_score: float = 0.0
    region_score: float = 0.0
    freshness_score: float = 0.0
    final_score: float = 0.0

    def to_citation(self) -> Citation:
        return Citation(
            chunk_id=self.chunk_id,
            document_id=self.document_id,
            title=self.title,
            source_url=self.source_url,
            source_type=self.source_type,
            section_path=self.section_path,
            publish_date=format_date(self._publish_date_value()),
            region=self.region,
            score=round(self.final_score, 4),
        )

    def _publish_date_value(self) -> date | None:
        if isinstance(self.publish_date, date):
            return self.publish_date
        if isinstance(self.publish_date, str) and self.publish_date:
            try:
                return date.fromisoformat(self.publish_date)
            except ValueError:
                return None
        return None


class RetrievalService:
    def __init__(
        self,
        session,
        settings: Settings | None = None,
        ollama_service: OllamaService | None = None,
        vector_store: LocalVectorStore | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.settings = settings or get_settings()
        self.repository = DocumentRepository(session)
        self.ollama_service = ollama_service or OllamaService(self.settings)
        self.vector_store = vector_store or LocalVectorStore(self.settings)
        self.embedding_service = embedding_service or EmbeddingService(
            self.settings,
            ollama_service=self.ollama_service,
            vector_store=self.vector_store,
        )

    @staticmethod
    def build_fts_match_query(question: str) -> str:
        tokens = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,}", question)
        if not tokens:
            cleaned = question.replace('"', " ").strip()
            return cleaned or "双碳"
        return " OR ".join(f'"{token}"' for token in tokens[:10])

    @staticmethod
    def normalize_keyword_score(raw_bm25: float | int | None) -> float:
        if raw_bm25 is None:
            return 0.0
        value = max(float(raw_bm25), 0.0)
        return 1.0 / (1.0 + value)

    @staticmethod
    def compute_region_score(query_region: str | None, doc_region: str | None, query_industry: str | None = None, doc_industry: str | None = None) -> float:
        score = 0.5 if not query_region else 0.0
        if query_region and doc_region and (query_region in doc_region or doc_region in query_region):
            score = 1.0
        if query_industry and doc_industry and (query_industry in doc_industry or doc_industry in query_industry):
            score = min(1.0, score + 0.2)
        return score

    @staticmethod
    def compute_freshness_score(publish_date: date | str | None) -> float:
        if publish_date is None:
            return 0.4
        if isinstance(publish_date, str):
            try:
                publish_date = date.fromisoformat(publish_date)
            except ValueError:
                return 0.4

        days = (datetime.now(timezone.utc).date() - publish_date).days
        if days <= 365:
            return 1.0
        if days <= 365 * 3:
            return 0.8
        if days <= 365 * 5:
            return 0.6
        return 0.4

    @staticmethod
    def compute_final_score(keyword_score: float, semantic_score: float, region_score: float, freshness_score: float) -> float:
        return (
            0.40 * keyword_score
            + 0.35 * semantic_score
            + 0.15 * region_score
            + 0.10 * freshness_score
        )

    def hybrid_search(
        self,
        question: str,
        *,
        region: str | None = None,
        industry: str | None = None,
        limit: int | None = None,
    ) -> list[SearchResult]:
        final_limit = limit or self.settings.final_top_k
        merged: dict[int, SearchResult] = {}

        match_query = self.build_fts_match_query(question)
        try:
            keyword_rows = self.repository.keyword_search(
                match_query=match_query,
                limit=self.settings.keyword_top_k,
                region=region,
                industry=industry,
            )
        except Exception:
            keyword_rows = []

        for row in keyword_rows:
            result = SearchResult(
                chunk_id=int(row["chunk_id"]),
                document_id=int(row["document_id"]),
                chunk_index=int(row["chunk_index"]),
                title=row["title"],
                content=row["content"],
                section_path=row.get("section_path"),
                token_count=int(row["token_count"]),
                keywords=row.get("keywords"),
                embedding_path=row.get("embedding_path"),
                source_url=row.get("source_url"),
                source_type=row.get("source_type"),
                region=row.get("region"),
                industry=row.get("industry"),
                doc_type=row.get("doc_type"),
                publish_date=row.get("publish_date"),
                keyword_score=self.normalize_keyword_score(row.get("bm25_score")),
            )
            merged[result.chunk_id] = result

        semantic_rows = self._semantic_search(question, region=region, industry=industry)
        for result in semantic_rows:
            if result.chunk_id in merged:
                merged[result.chunk_id].semantic_score = result.semantic_score
            else:
                merged[result.chunk_id] = result

        for result in merged.values():
            result.region_score = self.compute_region_score(region, result.region, industry, result.industry)
            result.freshness_score = self.compute_freshness_score(result.publish_date)
            result.final_score = self.compute_final_score(
                result.keyword_score,
                result.semantic_score,
                result.region_score,
                result.freshness_score,
            )

        return sorted(merged.values(), key=lambda item: item.final_score, reverse=True)[:final_limit]

    def _semantic_search(
        self,
        question: str,
        *,
        region: str | None = None,
        industry: str | None = None,
    ) -> list[SearchResult]:
        profile = self.embedding_service.get_active_profile()
        try:
            query_embedding = np.array(
                self.embedding_service.embed_text(question, input_type="query", model_name=profile.model_name),
                dtype=np.float32,
            )
        except Exception:
            return []

        rows = self.repository.list_active_chunk_rows(region=region, industry=industry)
        results: list[SearchResult] = []
        for row in rows:
            embedding_path = row.get("embedding_path")
            if not self.vector_store.is_compatible(
                embedding_path,
                model_name=profile.model_name,
                profile_name=profile.profile_name,
                dimensions=int(query_embedding.shape[0]),
            ):
                continue

            embedding = self.vector_store.load_embedding(embedding_path)
            if embedding is None:
                continue
            if tuple(embedding.shape) != tuple(query_embedding.shape):
                continue

            semantic_score = max(0.0, self.vector_store.cosine_similarity(query_embedding, embedding))
            if semantic_score <= 0:
                continue
            results.append(
                SearchResult(
                    chunk_id=int(row["chunk_id"]),
                    document_id=int(row["document_id"]),
                    chunk_index=int(row["chunk_index"]),
                    title=row["title"],
                    content=row["content"],
                    section_path=row.get("section_path"),
                    token_count=int(row["token_count"]),
                    keywords=row.get("keywords"),
                    embedding_path=embedding_path,
                    source_url=row.get("source_url"),
                    source_type=row.get("source_type"),
                    region=row.get("region"),
                    industry=row.get("industry"),
                    doc_type=row.get("doc_type"),
                    publish_date=row.get("publish_date"),
                    semantic_score=semantic_score,
                )
            )

        results.sort(key=lambda item: item.semantic_score, reverse=True)
        return results[: self.settings.semantic_top_k]

    def build_context(self, results: list[SearchResult], max_chars: int | None = None) -> str:
        char_limit = max_chars or self.settings.context_max_chars
        blocks: list[str] = []
        total = 0
        for item in results:
            block = (
                f"[ChunkID={item.chunk_id}] 标题: {item.title}\n"
                f"地区: {item.region or '未标注'} | 发布时间: {format_date(item._publish_date_value()) or '未标注'}\n"
                f"章节: {item.section_path or '正文'}\n"
                f"内容: {item.content}\n"
            )
            if total + len(block) > char_limit:
                break
            blocks.append(block)
            total += len(block)
        return "\n".join(blocks)
