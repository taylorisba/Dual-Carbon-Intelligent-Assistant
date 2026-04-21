from __future__ import annotations

import json
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.models.db_models import KnowledgeSource, SyncJob
from app.repositories.source_repository import SourceRepository
from app.repositories.sync_job_repository import SyncJobRepository
from app.services.ingestion_service import IngestionService
from app.utils.time import utc_now


class SyncService:
    def __init__(self, session: Session, settings: Settings | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.source_repository = SourceRepository(session)
        self.job_repository = SyncJobRepository(session)
        self.ingestion_service = IngestionService(session, self.settings)

    def list_sources(self) -> list[KnowledgeSource]:
        return self.source_repository.list_sources()

    def create_source(self, payload) -> KnowledgeSource:
        source = KnowledgeSource(
            name=payload.name,
            base_url=payload.base_url,
            source_type=payload.source_type,
            region=payload.region,
            industry=payload.industry,
            crawl_config_json=payload.crawl_config_json,
            enabled=payload.enabled,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        return self.source_repository.add_source(source)

    def sync_source(self, source_id: int, *, job_type: str = "manual") -> SyncJob:
        source = self.source_repository.get_source(source_id)
        if source is None:
            raise ValueError(f"知识源不存在: {source_id}")
        return self._sync_source_record(source, job_type=job_type)

    def sync_all_enabled_sources(self) -> list[SyncJob]:
        jobs: list[SyncJob] = []
        for source in self.source_repository.list_enabled_sources():
            jobs.append(self._sync_source_record(source, job_type="scheduled"))
        return jobs

    def _sync_source_record(self, source: KnowledgeSource, *, job_type: str) -> SyncJob:
        job = self.job_repository.create_job(
            SyncJob(
                source_id=source.id,
                job_type=job_type,
                status="running",
                message="同步开始",
                started_at=utc_now(),
                created_at=utc_now(),
            )
        )
        try:
            processed = 0
            if source.source_type in {"html", "pdf", "txt", "markdown"}:
                self.ingestion_service.ingest_remote_url(
                    source.base_url,
                    source_type=source.source_type,
                    region=source.region,
                    industry=source.industry,
                )
                processed = 1
            elif source.source_type == "html_list":
                links = self._discover_links(source)
                for link in links:
                    self.ingestion_service.ingest_remote_url(
                        link,
                        source_type="html",
                        region=source.region,
                        industry=source.industry,
                    )
                processed = len(links)
            else:
                raise ValueError(f"暂不支持的知识源类型: {source.source_type}")

            source.last_sync_at = utc_now()
            source.updated_at = utc_now()
            self.source_repository.save(source)

            job.status = "success"
            job.message = f"同步完成，处理 {processed} 个文档"
        except Exception as exc:
            self.session.rollback()
            job.status = "failed"
            job.message = f"同步失败: {exc}"
        job.finished_at = utc_now()
        return self.job_repository.save(job)

    def _discover_links(self, source: KnowledgeSource) -> list[str]:
        config = json.loads(source.crawl_config_json or "{}")
        selector = config.get("link_selector", "a")
        max_links = int(config.get("max_links", 20))
        include_patterns: list[str] = config.get("include_patterns", [])

        response = requests.get(
            source.base_url,
            timeout=self.settings.llm_request_timeout,
            headers={"User-Agent": self.settings.default_sync_user_agent},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        links: list[str] = []
        for node in soup.select(selector):
            href = node.get("href")
            if not href:
                continue
            absolute_link = urljoin(source.base_url, href)
            if include_patterns and not any(pattern in absolute_link for pattern in include_patterns):
                continue
            if absolute_link not in links:
                links.append(absolute_link)
            if len(links) >= max_links:
                break
        return links
