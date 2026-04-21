from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EmbeddingConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    embedding_provider: str
    embedding_model: str
    embedding_profile: str
    embedding_api: str
    embedding_batch_size: int
    embedding_truncate: bool
    embedding_keep_alive: str
    embedding_dimensions: int
    embedding_query_prefix: str
    embedding_document_prefix: str
    hot_reload_applied: bool = True


class EmbeddingConfigUpdate(BaseModel):
    embedding_model: Literal["embeddinggemma", "bge-m3"]
    embedding_profile: str = Field(default="auto", min_length=1)
    embedding_api: Literal["auto", "embed", "embeddings"] = "auto"
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    embedding_truncate: bool = True
    embedding_keep_alive: str = Field(default="5m", min_length=1)
    embedding_dimensions: int = Field(default=0, ge=0)
    embedding_query_prefix: str = ""
    embedding_document_prefix: str = ""


class EmbeddingConfigUpdateResponse(BaseModel):
    message: str
    config: EmbeddingConfigRead


class EmbeddingRebuildResponse(BaseModel):
    message: str
    total_chunks: int
    updated_chunks: int
    failed_chunks: int
    profile_name: str
    model_name: str
