from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.db_models import Chunk, Document


class DocumentRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_documents(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        region: str | None = None,
        status: str | None = None,
    ) -> list[Document]:
        statement = select(Document)
        if region:
            statement = statement.where(Document.region.contains(region))
        if status:
            statement = statement.where(Document.status == status)
        statement = statement.order_by(Document.updated_at.desc()).offset(offset).limit(limit)
        return list(self.session.exec(statement).all())

    def get_document(self, document_id: int) -> Document | None:
        return self.session.get(Document, document_id)

    def find_active_by_hash(self, content_hash: str) -> Document | None:
        statement = select(Document).where(
            Document.content_hash == content_hash,
            Document.status == "active",
        )
        return self.session.exec(statement).first()

    def find_latest_by_source_url(self, source_url: str) -> Document | None:
        statement = (
            select(Document)
            .where(Document.source_url == source_url)
            .order_by(Document.version.desc(), Document.updated_at.desc())
        )
        return self.session.exec(statement).first()

    def mark_superseded_by_source_url(self, source_url: str) -> None:
        statement = select(Document).where(
            Document.source_url == source_url,
            Document.status == "active",
        )
        documents = list(self.session.exec(statement).all())
        for document in documents:
            document.status = "superseded"
            self.session.add(document)

    def add_document(self, document: Document) -> Document:
        self.session.add(document)
        self.session.flush()
        self.session.refresh(document)
        return document

    def add_chunk(self, chunk: Chunk) -> Chunk:
        self.session.add(chunk)
        self.session.flush()
        self.session.refresh(chunk)
        return chunk

    def count_chunks_by_document(self, document_id: int) -> int:
        statement = select(Chunk).where(Chunk.document_id == document_id)
        return len(list(self.session.exec(statement).all()))

    def list_chunks_by_document(self, document_id: int) -> list[Chunk]:
        statement = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
        return list(self.session.exec(statement).all())

    def list_active_chunk_rows(
        self,
        *,
        region: str | None = None,
        industry: str | None = None,
    ) -> list[dict[str, Any]]:
        statement = select(Chunk, Document).join(Document, Document.id == Chunk.document_id).where(Document.status == "active")
        if region:
            statement = statement.where((Document.region.is_(None)) | (Document.region.contains(region)))
        if industry:
            statement = statement.where((Document.industry.is_(None)) | (Document.industry.contains(industry)))

        rows: list[dict[str, Any]] = []
        for chunk, document in self.session.exec(statement).all():
            rows.append(
                {
                    "chunk_id": chunk.id,
                    "document_id": document.id,
                    "chunk_index": chunk.chunk_index,
                    "section_path": chunk.section_path,
                    "content": chunk.content,
                    "token_count": chunk.token_count,
                    "keywords": chunk.keywords,
                    "embedding_path": chunk.embedding_path,
                    "title": document.title,
                    "source_url": document.source_url,
                    "source_type": document.source_type,
                    "region": document.region,
                    "industry": document.industry,
                    "doc_type": document.doc_type,
                    "publish_date": document.publish_date,
                    "status": document.status,
                }
            )
        return rows

    def keyword_search(
        self,
        *,
        match_query: str,
        limit: int,
        region: str | None = None,
        industry: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.chunk_index,
            c.section_path,
            c.content,
            c.token_count,
            c.keywords,
            c.embedding_path,
            d.title,
            d.source_url,
            d.source_type,
            d.region,
            d.industry,
            d.doc_type,
            d.publish_date,
            bm25(chunks_fts) AS bm25_score
        FROM chunks_fts
        JOIN chunks c ON c.id = chunks_fts.chunk_id
        JOIN documents d ON d.id = c.document_id
        WHERE chunks_fts MATCH :match_query
          AND d.status = 'active'
        """
        params: dict[str, Any] = {"match_query": match_query, "limit": limit}

        if region:
            sql += " AND (d.region IS NULL OR d.region = '' OR d.region LIKE :region_like)"
            params["region_like"] = f"%{region}%"
        if industry:
            sql += " AND (d.industry IS NULL OR d.industry = '' OR d.industry LIKE :industry_like)"
            params["industry_like"] = f"%{industry}%"

        sql += " ORDER BY bm25_score LIMIT :limit"
        rows = self.session.execute(text(sql), params).mappings().all()
        return [dict(row) for row in rows]

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def delete_document_chunks(self, document_id: int) -> None:
        statement = select(Chunk).where(Chunk.document_id == document_id)
        for chunk in self.session.exec(statement).all():
            self.session.delete(chunk)
