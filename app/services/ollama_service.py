from __future__ import annotations

import time
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class OllamaServiceError(RuntimeError):
    pass


class OllamaService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.settings.llm_max_retries + 1):
            try:
                with httpx.Client(base_url=self.settings.ollama_base_url, timeout=self.settings.llm_request_timeout) as client:
                    response = client.post(path, json=payload)
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt >= self.settings.llm_max_retries:
                    break
                time.sleep(self.settings.llm_retry_backoff_seconds * (attempt + 1))
        raise OllamaServiceError(f"Ollama 调用失败: {last_error}")

    def chat(self, messages: list[dict[str, str]], model: str | None = None) -> str:
        payload = {
            "model": model or self.settings.chat_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.settings.llm_temperature,
                "num_ctx": self.settings.ollama_num_ctx,
                "top_k": self.settings.ollama_top_k,
            },
        }
        response = self._post("/api/chat", payload)
        return response.get("message", {}).get("content", "").strip()

    def generate(self, prompt: str, model: str | None = None) -> str:
        payload = {
            "model": model or self.settings.chat_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.settings.llm_temperature,
                "num_ctx": self.settings.ollama_num_ctx,
                "top_k": self.settings.ollama_top_k,
            },
        }
        response = self._post("/api/generate", payload)
        return response.get("response", "").strip()

    def embed(
        self,
        inputs: str | list[str],
        *,
        model: str | None = None,
        truncate: bool | None = None,
        keep_alive: str | None = None,
        dimensions: int | None = None,
    ) -> list[list[float]]:
        payload: dict[str, Any] = {
            "model": model or self.settings.embedding_model,
            "input": inputs,
            "truncate": self.settings.embedding_truncate if truncate is None else truncate,
            "keep_alive": keep_alive or self.settings.embedding_keep_alive,
        }
        if dimensions and dimensions > 0:
            payload["dimensions"] = dimensions

        response = self._post("/api/embed", payload)
        embeddings = response.get("embeddings")
        if not isinstance(embeddings, list):
            raise OllamaServiceError("/api/embed 响应格式不正确")
        if embeddings and all(isinstance(item, (int, float)) for item in embeddings):
            return [[float(item) for item in embeddings]]
        if not all(isinstance(item, list) for item in embeddings):
            raise OllamaServiceError("/api/embed embeddings 字段格式不正确")
        return [[float(value) for value in row] for row in embeddings]

    def legacy_embedding(self, text: str, model: str | None = None) -> list[float]:
        payload = {
            "model": model or self.settings.embedding_model,
            "prompt": text,
        }
        response = self._post("/api/embeddings", payload)
        embedding = response.get("embedding")
        if not isinstance(embedding, list):
            raise OllamaServiceError("/api/embeddings 响应格式不正确")
        return [float(item) for item in embedding]

    def embeddings(self, text: str, model: str | None = None) -> list[float]:
        try:
            return self.embed(text, model=model)[0]
        except OllamaServiceError:
            return self.legacy_embedding(text, model=model)

