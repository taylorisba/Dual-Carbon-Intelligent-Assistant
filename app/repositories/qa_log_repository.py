from __future__ import annotations

from sqlmodel import Session

from app.models.db_models import QALog


class QALogRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_log(self, log: QALog) -> QALog:
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log
