from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session, select

from app.core.config import Settings, get_settings
from app.models.db_models import Chunk, Document
from app.services.ollama_service import OllamaService, OllamaServiceError
from app.services.vector_store import LocalVectorStore


logger = logging.getLogger(__name__)
EmbeddingInputType = Literal["query", "document"]


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    profile_name: str
    model_name: str
    endpoint_preference: str
    query_prefix: str = ""
    document_prefix: str = ""


@dataclass(slots=True)
class EmbeddingRebuildResult:
    total_chunks: int
    updated_chunks: int
    failed_chunks: int
    profile_name: str
    model_name: str


class EmbeddingService:
    def __init__(
        self,
        settings: Settings | None = None,
        ollama_service: OllamaService | None = None,
        vector_store: LocalVectorStore | None = None,
    ):
        self.settings = settings or get_settings()
        self.ollama_service = ollama_service or OllamaService(self.settings)
        self.vector_store = vector_store or LocalVectorStore(self.settings)

    def get_active_profile(self, model_name: str | None = None) -> EmbeddingProfile:
        selected_model = (model_name or self.settings.embedding_model).strip()
        configured_profile = (self.settings.embedding_profile or "auto").strip().lower()
        profile_name = self._resolve_profile_name(selected_model, configured_profile)
        return EmbeddingProfile(
            profile_name=profile_name,
            model_name=selected_model,
            endpoint_preference=(self.settings.embedding_api or "auto").strip().lower(),
            query_prefix=self.settings.embedding_query_prefix,
            document_prefix=self.settings.embedding_document_prefix,
        )

    def embed_text(self, text: str, *, input_type: EmbeddingInputType = "document", model_name: str | None = None) -> list[float]:
        results = self.embed_texts([text], input_type=input_type, model_name=model_name)
        if not results:
            raise OllamaServiceError("embedding 结果为空")
        return results[0]

    def embed_texts(
        self,
        texts: list[str],
        *,
        input_type: EmbeddingInputType = "document",
        model_name: str | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []

        profile = self.get_active_profile(model_name)
        prepared_inputs = [self._format_text(text, input_type=input_type, profile=profile) for text in texts]
        endpoint = profile.endpoint_preference
        errors: list[Exception] = []

        if endpoint in {"auto", "embed"}:
            try:
                return self.ollama_service.embed(
                    prepared_inputs,
                    model=profile.model_name,
                    truncate=self.settings.embedding_truncate,
                    keep_alive=self.settings.embedding_keep_alive,
                    dimensions=self.settings.embedding_dimensions or None,
                )
            except OllamaServiceError as exc:
                errors.append(exc)
                if endpoint == "embed":
                    raise

        if endpoint in {"auto", "embeddings"}:
            try:
                return [self.ollama_service.legacy_embedding(text, model=profile.model_name) for text in prepared_inputs]
            except OllamaServiceError as exc:
                errors.append(exc)

        raise OllamaServiceError("embedding 调用失败: " + " | ".join(str(err) for err in errors))

    def rebuild_all_embeddings(
        self,
        session: Session,
        *,
        only_active: bool = True,
        batch_size: int | None = None,
        document_id: int | None = None,
    ) -> EmbeddingRebuildResult:
        statement = select(Chunk, Document).join(Document, Document.id == Chunk.document_id)
        if only_active:
            statement = statement.where(Document.status == "active")
        if document_id is not None:
            statement = statement.where(Chunk.document_id == document_id)
        statement = statement.order_by(Chunk.id)
        rows = list(session.exec(statement).all())
        profile = self.get_active_profile()

        updated_chunks = 0
        failed_chunks = 0
        effective_batch_size = max(1, batch_size or self.settings.embedding_batch_size)

        for batch in self._batched(rows, effective_batch_size):
            chunk_records = [chunk for chunk, _ in batch if chunk.content.strip()]
            if not chunk_records:
                continue
            texts = [chunk.content for chunk in chunk_records]
            try:
                embeddings = self.embed_texts(texts, input_type="document", model_name=profile.model_name)
            except OllamaServiceError as exc:
                logger.warning("批量重建 embedding 失败，批次大小=%s: %s", len(chunk_records), exc)
                failed_chunks += len(chunk_records)
                continue

            for chunk, embedding in zip(chunk_records, embeddings):
                chunk.embedding_path = self.vector_store.save_embedding(
                    chunk.id,
                    embedding,
                    model_name=profile.model_name,
                    profile_name=profile.profile_name,
                )
                session.add(chunk)
                updated_chunks += 1
            session.commit()

        return EmbeddingRebuildResult(
            total_chunks=len(rows),
            updated_chunks=updated_chunks,
            failed_chunks=failed_chunks,
            profile_name=profile.profile_name,
            model_name=profile.model_name,
        )

    @staticmethod
    def _resolve_profile_name(model_name: str, configured_profile: str) -> str:
        if configured_profile and configured_profile != "auto":
            if configured_profile in {"bge_m3", "bgem3"}:
                return "bge-m3"
            return configured_profile

        lowered = model_name.strip().lower()
        if "bge-m3" in lowered or "bge_m3" in lowered or lowered.startswith("bge"):
            return "bge-m3"
        if "embeddinggemma" in lowered:
            return "embeddinggemma"
        return "custom"

    @staticmethod
    def _format_text(text: str, *, input_type: EmbeddingInputType, profile: EmbeddingProfile) -> str:
        normalized = text.strip()
        prefix = profile.query_prefix if input_type == "query" else profile.document_prefix
        return f"{prefix}{normalized}" if prefix else normalized

    @staticmethod
    def _batched(items: list[tuple[Chunk, Document]], batch_size: int) -> list[list[tuple[Chunk, Document]]]:
        return [items[index:index + batch_size] for index in range(0, len(items), batch_size)]
