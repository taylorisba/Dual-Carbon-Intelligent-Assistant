from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import BASE_DIR, get_settings
from app.schemas.system import EmbeddingConfigRead, EmbeddingConfigUpdate, EmbeddingRebuildResponse
from app.services.embedding_service import EmbeddingService


ENV_LINE_PATTERN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


class SystemConfigService:
    def __init__(self, env_path: Path | None = None):
        self.env_path = env_path or (BASE_DIR / ".env")

    def get_embedding_config(self) -> EmbeddingConfigRead:
        settings = get_settings()
        return EmbeddingConfigRead(
            embedding_provider=settings.embedding_provider,
            embedding_model=settings.embedding_model,
            embedding_profile=settings.embedding_profile,
            embedding_api=settings.embedding_api,
            embedding_batch_size=settings.embedding_batch_size,
            embedding_truncate=settings.embedding_truncate,
            embedding_keep_alive=settings.embedding_keep_alive,
            embedding_dimensions=settings.embedding_dimensions,
            embedding_query_prefix=settings.embedding_query_prefix,
            embedding_document_prefix=settings.embedding_document_prefix,
            hot_reload_applied=True,
        )

    def update_embedding_config(self, payload: EmbeddingConfigUpdate) -> EmbeddingConfigRead:
        values = {
            "EMBEDDING_PROVIDER": "ollama",
            "EMBEDDING_MODEL": payload.embedding_model,
            "EMBEDDING_PROFILE": payload.embedding_profile,
            "EMBEDDING_API": payload.embedding_api,
            "EMBEDDING_BATCH_SIZE": payload.embedding_batch_size,
            "EMBEDDING_TRUNCATE": str(payload.embedding_truncate).lower(),
            "EMBEDDING_KEEP_ALIVE": payload.embedding_keep_alive,
            "EMBEDDING_DIMENSIONS": payload.embedding_dimensions,
            "EMBEDDING_QUERY_PREFIX": payload.embedding_query_prefix,
            "EMBEDDING_DOCUMENT_PREFIX": payload.embedding_document_prefix,
        }
        self._write_env_values(values)
        get_settings.cache_clear()
        return self.get_embedding_config()

    def rebuild_embeddings(self, session: Session) -> EmbeddingRebuildResponse:
        settings = get_settings()
        result = EmbeddingService(settings=settings).rebuild_all_embeddings(session)
        return EmbeddingRebuildResponse(
            message="embedding 重建完成",
            total_chunks=result.total_chunks,
            updated_chunks=result.updated_chunks,
            failed_chunks=result.failed_chunks,
            profile_name=result.profile_name,
            model_name=result.model_name,
        )

    def _write_env_values(self, updates: dict[str, Any]) -> None:
        lines = []
        if self.env_path.exists():
            lines = self.env_path.read_text(encoding="utf-8").splitlines()
        else:
            self.env_path.parent.mkdir(parents=True, exist_ok=True)

        normalized = {key: self._format_env_value(value) for key, value in updates.items()}
        remaining = dict(normalized)
        output_lines: list[str] = []

        for line in lines:
            match = ENV_LINE_PATTERN.match(line)
            if not match:
                output_lines.append(line)
                continue
            key = match.group(1)
            if key in remaining:
                output_lines.append(f"{key}={remaining.pop(key)}")
            else:
                output_lines.append(line)

        if output_lines and output_lines[-1].strip() != "":
            output_lines.append("")
        for key, value in remaining.items():
            output_lines.append(f"{key}={value}")

        self.env_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def _format_env_value(value: Any) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        return str(value)
