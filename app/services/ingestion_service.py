from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.models.db_models import Chunk, Document
from app.repositories.document_repository import DocumentRepository
from app.services.embedding_service import EmbeddingService
from app.services.ollama_service import OllamaService
from app.services.vector_store import LocalVectorStore
from app.utils.chunking import chunk_text
from app.utils.file_parsers import ParsedDocument, parse_local_file, parse_remote_file
from app.utils.text import clean_text, extract_first_date, extract_region
from app.utils.time import utc_now


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionResult:
    created: bool
    message: str
    document: Document


class IngestionService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        ollama_service: OllamaService | None = None,
        vector_store: LocalVectorStore | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self.session = session
        self.settings = settings or get_settings()
        self.repository = DocumentRepository(session)
        self.ollama_service = ollama_service or OllamaService(self.settings)
        self.vector_store = vector_store or LocalVectorStore(self.settings)
        self.embedding_service = embedding_service or EmbeddingService(
            self.settings,
            ollama_service=self.ollama_service,
            vector_store=self.vector_store,
        )

    def ingest_file(
        self,
        file_path: str | Path,
        *,
        region: str | None = None,
        industry: str | None = None,
        doc_type: str = "policy",
        publish_date: date | None = None,
    ) -> IngestionResult:
        parsed = parse_local_file(file_path)
        return self.ingest_parsed_document(
            parsed,
            source_type=Path(file_path).suffix.lower().lstrip(".") or "upload",
            local_path=str(Path(file_path).resolve()),
            region=region,
            industry=industry,
            doc_type=doc_type,
            publish_date=publish_date,
        )

    def ingest_remote_url(
        self,
        url: str,
        *,
        source_type: str,
        region: str | None = None,
        industry: str | None = None,
        doc_type: str = "policy",
    ) -> IngestionResult:
        parsed = parse_remote_file(
            url,
            timeout=self.settings.llm_request_timeout,
            user_agent=self.settings.default_sync_user_agent,
        )
        return self.ingest_parsed_document(
            parsed,
            source_type=source_type,
            source_url=url,
            region=region,
            industry=industry,
            doc_type=doc_type,
        )

    def ingest_parsed_document(
        self,
        parsed: ParsedDocument,
        *,
        source_type: str,
        source_url: str | None = None,
        local_path: str | None = None,
        region: str | None = None,
        industry: str | None = None,
        doc_type: str = "policy",
        publish_date: date | None = None,
        effective_date: date | None = None,
    ) -> IngestionResult:
        cleaned_text = clean_text(parsed.text)
        if not cleaned_text:
            raise ValueError("文档解析后内容为空")

        content_hash = sha256(cleaned_text.encode("utf-8")).hexdigest()
        duplicated = self.repository.find_active_by_hash(content_hash)
        if duplicated:
            return IngestionResult(created=False, message="文档已存在，按 hash 去重", document=duplicated)

        latest_by_source = self.repository.find_latest_by_source_url(source_url) if source_url else None
        version = 1
        if latest_by_source:
            version = latest_by_source.version + 1
            self.repository.mark_superseded_by_source_url(source_url)

        title = parsed.title.strip() or Path(local_path or source_url or "未命名文档").stem
        final_publish_date = publish_date or extract_first_date(cleaned_text)
        final_region = region or extract_region(cleaned_text)
        source_site = parsed.metadata.get("source_site") if parsed.metadata else None
        if not source_site and source_url:
            source_site = urlparse(source_url).netloc

        document = Document(
            title=title,
            source_url=source_url,
            source_site=source_site,
            source_type=source_type,
            local_path=local_path,
            region=final_region,
            industry=industry,
            doc_type=doc_type,
            publish_date=final_publish_date,
            effective_date=effective_date,
            status="active",
            content_hash=content_hash,
            version=version,
            raw_text=cleaned_text,
            summary=cleaned_text[:240],
            extra_metadata=json.dumps(parsed.metadata, ensure_ascii=False),
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.repository.add_document(document)

        chunks = chunk_text(
            cleaned_text,
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )
        profile = self.embedding_service.get_active_profile()
        chunk_records: list[Chunk] = []
        for item in chunks:
            chunk = Chunk(
                document_id=document.id,
                chunk_index=item.chunk_index,
                section_path=item.section_path,
                content=item.content,
                token_count=item.token_count,
                keywords=",".join(item.keywords),
            )
            self.repository.add_chunk(chunk)
            chunk_records.append(chunk)

        for index in range(0, len(chunk_records), self.settings.embedding_batch_size):
            batch = chunk_records[index:index + self.settings.embedding_batch_size]
            texts = [chunk.content for chunk in batch]
            try:
                embeddings = self.embedding_service.embed_texts(texts, input_type="document", model_name=profile.model_name)
            except Exception as exc:
                logger.warning("embedding 生成失败，继续仅使用关键词检索: %s", exc)
                continue

            for chunk, embedding in zip(batch, embeddings):
                chunk.embedding_path = self.vector_store.save_embedding(
                    chunk.id,
                    embedding,
                    model_name=profile.model_name,
                    profile_name=profile.profile_name,
                )
                self.session.add(chunk)

        self.repository.commit()
        self.session.refresh(document)
        return IngestionResult(created=True, message=f"导入完成，共生成 {len(chunks)} 个分块", document=document)
