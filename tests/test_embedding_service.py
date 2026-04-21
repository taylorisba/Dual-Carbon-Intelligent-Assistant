import pytest

pytest.importorskip("sqlmodel")
pytest.importorskip("pydantic_settings")

from app.core.config import Settings
from app.services.embedding_service import EmbeddingService
from app.services.ollama_service import OllamaServiceError


class LegacyFallbackOllamaService:
    def embed(self, *args, **kwargs):
        raise OllamaServiceError("embed endpoint unavailable")

    def legacy_embedding(self, text: str, model: str | None = None):
        return [float(len(text)), 1.0]


class PrefixAwareOllamaService:
    def embed(self, inputs, *args, **kwargs):
        if isinstance(inputs, str):
            inputs = [inputs]
        return [[float(len(text))] for text in inputs]

    def legacy_embedding(self, text: str, model: str | None = None):
        return [float(len(text))]



def test_auto_profile_detects_bge_m3():
    settings = Settings(_env_file=None, embedding_model="bge-m3", embedding_profile="auto")
    service = EmbeddingService(settings=settings, ollama_service=PrefixAwareOllamaService())

    profile = service.get_active_profile()
    assert profile.profile_name == "bge-m3"
    assert profile.model_name == "bge-m3"



def test_embed_texts_falls_back_to_legacy_endpoint():
    settings = Settings(_env_file=None, embedding_model="bge-m3", embedding_api="auto")
    service = EmbeddingService(settings=settings, ollama_service=LegacyFallbackOllamaService())

    result = service.embed_texts(["abc", "de"], input_type="document")
    assert result == [[3.0, 1.0], [2.0, 1.0]]



def test_query_prefix_is_applied_before_embedding():
    settings = Settings(
        _env_file=None,
        embedding_model="bge-m3",
        embedding_query_prefix="query: ",
        embedding_document_prefix="passage: ",
    )
    service = EmbeddingService(settings=settings, ollama_service=PrefixAwareOllamaService())

    query_vector = service.embed_text("江苏节能政策", input_type="query")
    doc_vector = service.embed_text("江苏节能政策", input_type="document")

    assert query_vector[0] > doc_vector[0]
