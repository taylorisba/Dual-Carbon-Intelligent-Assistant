from __future__ import annotations

from sqlmodel import Session, select

from app.models.db_models import KnowledgeSource


class SourceRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_sources(self) -> list[KnowledgeSource]:
        statement = select(KnowledgeSource).order_by(KnowledgeSource.updated_at.desc())
        return list(self.session.exec(statement).all())

    def list_enabled_sources(self) -> list[KnowledgeSource]:
        statement = select(KnowledgeSource).where(KnowledgeSource.enabled.is_(True))
        return list(self.session.exec(statement).all())

    def get_source(self, source_id: int) -> KnowledgeSource | None:
        return self.session.get(KnowledgeSource, source_id)

    def add_source(self, source: KnowledgeSource) -> KnowledgeSource:
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source

    def save(self, source: KnowledgeSource) -> KnowledgeSource:
        self.session.add(source)
        self.session.commit()
        self.session.refresh(source)
        return source
