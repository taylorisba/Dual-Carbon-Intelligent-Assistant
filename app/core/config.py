from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Dual Carbon Intelligent Assistant"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    timezone: str = "Asia/Shanghai"

    sqlite_db_path: str = str(BASE_DIR / "data" / "app.db")
    data_dir: str = str(BASE_DIR / "data")
    documents_dir: str = str(BASE_DIR / "data" / "documents")
    uploads_dir: str = str(BASE_DIR / "data" / "uploads")
    vector_store_dir: str = str(BASE_DIR / "data" / "vector_store")

    ollama_base_url: str = "http://127.0.0.1:11434"
    chat_model: str = "deepseek-r1:8b"
    embedding_provider: str = "ollama"
    embedding_model: str = "embeddinggemma"
    embedding_profile: str = "auto"
    embedding_api: str = "auto"
    embedding_batch_size: int = 16
    embedding_truncate: bool = True
    embedding_keep_alive: str = "5m"
    embedding_dimensions: int = 0
    embedding_query_prefix: str = ""
    embedding_document_prefix: str = ""

    ollama_num_ctx: int = 4096
    ollama_top_k: int = 40
    llm_temperature: float = 0.1
    llm_request_timeout: int = 120
    llm_max_retries: int = 2
    llm_retry_backoff_seconds: float = 1.5
    context_max_chars: int = 6000
    query_rewrite_enabled: bool = True

    chunk_size: int = 500
    chunk_overlap: int = 80
    keyword_top_k: int = 8
    semantic_top_k: int = 8
    final_top_k: int = 6
    min_answerable_score: float = 0.32
    max_citations: int = 3

    scheduler_enabled: bool = True
    scheduler_interval_minutes: int = 720
    default_sync_user_agent: str = "dual-carbon-assistant/0.1"

    @property
    def database_url(self) -> str:
        db_path = Path(self.sqlite_db_path).resolve().as_posix()
        return f"sqlite:///{db_path}"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.documents_dir,
            self.uploads_dir,
            self.vector_store_dir,
        ):
            Path(path).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings

