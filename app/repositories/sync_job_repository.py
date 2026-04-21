from __future__ import annotations

from sqlmodel import Session

from app.models.db_models import SyncJob


class SyncJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_job(self, job: SyncJob) -> SyncJob:
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def save(self, job: SyncJob) -> SyncJob:
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job
