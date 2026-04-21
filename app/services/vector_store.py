from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import Settings, get_settings


class LocalVectorStore:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_dir = Path(self.settings.vector_store_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()) or "default"

    def build_namespace(self, *, model_name: str | None = None, profile_name: str | None = None) -> str:
        provider = self._sanitize(self.settings.embedding_provider)
        profile = self._sanitize(profile_name or self.settings.embedding_profile)
        model = self._sanitize(model_name or self.settings.embedding_model)
        return f"{provider}__{profile}__{model}"

    def save_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        *,
        model_name: str | None = None,
        profile_name: str | None = None,
    ) -> str:
        namespace_dir = self.base_dir / self.build_namespace(model_name=model_name, profile_name=profile_name)
        namespace_dir.mkdir(parents=True, exist_ok=True)
        path = namespace_dir / f"{chunk_id}.npy"
        array = np.array(embedding, dtype=np.float32)
        np.save(path, array)
        metadata = {
            "provider": self.settings.embedding_provider,
            "profile_name": profile_name or self.settings.embedding_profile,
            "model": model_name or self.settings.embedding_model,
            "dimensions": int(array.shape[0]),
        }
        path.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return str(path)

    def load_embedding(self, embedding_path: str | None) -> np.ndarray | None:
        if not embedding_path:
            return None
        path = Path(embedding_path)
        if not path.exists():
            return None
        return np.load(path)

    def load_metadata(self, embedding_path: str | None) -> dict[str, Any] | None:
        if not embedding_path:
            return None
        meta_path = Path(embedding_path).with_suffix(".json")
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def is_compatible(
        self,
        embedding_path: str | None,
        *,
        model_name: str | None = None,
        profile_name: str | None = None,
        dimensions: int | None = None,
    ) -> bool:
        metadata = self.load_metadata(embedding_path)
        if not metadata:
            return True
        expected_model = (model_name or self.settings.embedding_model).strip().lower()
        expected_profile = (profile_name or self.settings.embedding_profile).strip().lower()
        actual_model = str(metadata.get("model", "")).strip().lower()
        actual_profile = str(metadata.get("profile_name", "")).strip().lower()
        actual_dimensions = metadata.get("dimensions")

        if expected_model and actual_model and expected_model != actual_model:
            return False
        if expected_profile and expected_profile != "auto" and actual_profile and expected_profile != actual_profile:
            return False
        if dimensions and actual_dimensions and int(actual_dimensions) != int(dimensions):
            return False
        return True

    @staticmethod
    def cosine_similarity(query_embedding: np.ndarray, doc_embedding: np.ndarray) -> float:
        query_norm = np.linalg.norm(query_embedding)
        doc_norm = np.linalg.norm(doc_embedding)
        if query_norm == 0 or doc_norm == 0:
            return 0.0
        return float(np.dot(query_embedding, doc_embedding) / (query_norm * doc_norm))
