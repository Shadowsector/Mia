"""Tests for the llama.cpp-backed ChromaDB embedding function."""

from app.modules.rag.llama_embeddings import LlamaCppEmbeddingFunction


class FakeClient:
    embed_base_url = "http://localhost:8081"
    embed_model = "bge-m3"

    def __init__(self):
        self.calls = []

    def get_embeddings(self, texts, model=None):
        self.calls.append(list(texts))
        return [[float(i), 0.0] for i, _ in enumerate(texts)]


def test_call_returns_embeddings():
    client = FakeClient()
    ef = LlamaCppEmbeddingFunction(client=client)
    assert ef(["a", "b"]) == [[0.0, 0.0], [1.0, 0.0]]
    assert client.calls == [["a", "b"]]


def test_embed_documents_and_query():
    client = FakeClient()
    ef = LlamaCppEmbeddingFunction(client=client)
    assert ef.embed_documents(["x"]) == [[0.0, 0.0]]
    assert ef.embed_query("one") == [[0.0, 0.0]]
    assert client.calls == [["x"], ["one"]]


def test_name_and_legacy():
    assert LlamaCppEmbeddingFunction.name() == "llama_cpp_embeddings"
    assert LlamaCppEmbeddingFunction.is_legacy() is False


def test_get_config_and_build_from_config():
    ef = LlamaCppEmbeddingFunction(client=FakeClient())
    config = ef.get_config()
    assert config == {"base_url": "http://localhost:8081", "model": "bge-m3"}
    rebuilt = LlamaCppEmbeddingFunction.build_from_config(config)
    assert isinstance(rebuilt, LlamaCppEmbeddingFunction)


def test_default_factory_llama(monkeypatch):
    import config.settings as cfg
    from app.modules.rag.chroma_manager import get_default_embedding_function

    monkeypatch.setattr(cfg, "EMBED_BACKEND", "llama")
    assert isinstance(get_default_embedding_function(), LlamaCppEmbeddingFunction)


def test_default_factory_ollama(monkeypatch):
    import config.settings as cfg
    from app.modules.rag.chroma_manager import get_default_embedding_function

    monkeypatch.setattr(cfg, "EMBED_BACKEND", "ollama")
    ef = get_default_embedding_function()
    assert ef.__class__.__name__ == "OllamaEmbeddingFunction"
