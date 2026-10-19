"""Tests for LlamaCppClient (OpenAI-совместимый клиент llama.cpp)."""

import asyncio
import json

import pytest


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import app.modules.llm.llama_cpp_client as module

    calls = {"post": [], "get": []}
    responses = {
        "post": FakeResponse(payload={"choices": [{"message": {"content": "  ок  "}}]}),
        "get": FakeResponse(payload={"data": [{"id": "model-a"}, {"id": "model-b"}]}),
    }

    class FakeRequests:
        RequestException = module.requests.RequestException

        @staticmethod
        def post(url, json=None, timeout=None):
            calls["post"].append({"url": url, "json": json, "timeout": timeout})
            return responses["post"]

        @staticmethod
        def get(url, timeout=None):
            calls["get"].append({"url": url, "timeout": timeout})
            return responses["get"]

    monkeypatch.setattr(module, "requests", FakeRequests)

    c = module.LlamaCppClient(base_url="http://localhost:8080", cache_dir=str(tmp_path / "cache"))
    c._calls = calls
    c._responses = responses
    return c


class TestDefaults:
    def test_default_config(self, client):
        assert client.base_url == "http://localhost:8080"
        assert client.default_model
        assert client.embed_model == client.default_model

    def test_embed_model_override(self, tmp_path):
        import app.modules.llm.llama_cpp_client as module

        c = module.LlamaCppClient(embed_model="bge-m3", cache_dir=str(tmp_path))
        assert c.embed_model == "bge-m3"


class TestChat:
    def test_chat_strips_and_returns(self, client):
        out = client.chat([{"role": "user", "content": "hi"}])
        assert out == "ок"
        assert client._calls["post"][0]["url"].endswith("/v1/chat/completions")

    def test_chat_json_mode_sets_response_format(self, client):
        client.chat([{"role": "user", "content": "hi"}], json_mode=True)
        assert client._calls["post"][0]["json"]["response_format"] == {"type": "json_object"}

    def test_chat_non_200_raises(self, client):
        import app.modules.llm.llama_cpp_client as module

        client._responses["post"] = FakeResponse(status_code=500, text="boom")
        with pytest.raises(module.LlamaCppError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_chat_request_error_raises(self, client, monkeypatch):
        import app.modules.llm.llama_cpp_client as module

        def boom(*a, **k):
            raise module.requests.RequestException("no server")

        monkeypatch.setattr(module.requests, "post", boom)
        with pytest.raises(module.LlamaCppError):
            client.chat([{"role": "user", "content": "hi"}])

    def test_complete_builds_system_and_user(self, client):
        client.complete("SYS", "USER")
        messages = client._calls["post"][0]["json"]["messages"]
        assert messages == [
            {"role": "system", "content": "SYS"},
            {"role": "user", "content": "USER"},
        ]

    def test_empty_choices_returns_empty(self, client):
        client._responses["post"] = FakeResponse(payload={})
        assert client.chat([{"role": "user", "content": "hi"}]) == ""


class TestEmbeddings:
    def test_get_embedding(self, client):
        client._responses["post"] = FakeResponse(payload={"data": [{"embedding": [0.1, 0.2]}]})
        assert client.get_embedding("текст") == [0.1, 0.2]
        assert client._calls["post"][0]["url"].endswith("/v1/embeddings")

    def test_get_embedding_501_raises(self, client):
        import app.modules.llm.llama_cpp_client as module

        client._responses["post"] = FakeResponse(status_code=501, text="not implemented")
        with pytest.raises(module.LlamaCppError):
            client.get_embedding("текст")


class TestAvailability:
    def test_is_available_true(self, client):
        assert client.is_available() is True

    def test_is_available_false(self, client):
        client._responses["get"] = FakeResponse(status_code=503)
        assert client.is_available() is False

    def test_list_models_sorted(self, client):
        assert client.list_models() == ["model-a", "model-b"]

    def test_list_models_error_returns_empty(self, client):
        client._responses["get"] = FakeResponse(status_code=500)
        assert client.list_models() == []


class TestGenerateJson:
    def test_generate_json_parses(self, client):
        client._responses["post"] = FakeResponse(
            payload={"choices": [{"message": {"content": json.dumps({"x": 1})}}]}
        )
        assert asyncio.run(client.generate_json("q")) == {"x": 1}

    def test_generate_json_strips_fence(self, client):
        fenced = "```json\n{\"x\": 2}\n```"
        client._responses["post"] = FakeResponse(
            payload={"choices": [{"message": {"content": fenced}}]}
        )
        assert asyncio.run(client.generate_json("q")) == {"x": 2}

    def test_generate_json_invalid_returns_error(self, client):
        client._responses["post"] = FakeResponse(
            payload={"choices": [{"message": {"content": "не json"}}]}
        )
        result = asyncio.run(client.generate_json("q"))
        assert result["error"] == "Failed to parse JSON"
        assert "raw_response" in result

    def test_generate_json_schema_hint_in_prompt(self, client):
        client._responses["post"] = FakeResponse(
            payload={"choices": [{"message": {"content": "{}"}}]}
        )
        asyncio.run(client.generate_json("q", schema_hint="{\"type\":\"object\"}"))
        sent = client._calls["post"][0]["json"]["messages"][0]["content"]
        assert "JSON Schema" in sent


class TestCache:
    def test_cache_key_deterministic(self, client):
        a = client._generate_cache_key("p", "m", "json")
        b = client._generate_cache_key("p", "m", "json")
        c = client._generate_cache_key("p", "m", None)
        assert a == b and a != c and len(a) == 64

    def test_generate_uses_cache(self, client):
        key = client._generate_cache_key("p", "m", None)
        client._save_to_cache(key, {"response": "cached"})
        result = asyncio.run(client.generate("p", model="m", cache_key=key))
        assert result == {"response": "cached"}
        assert client._calls["post"] == []

    def test_generate_writes_cache(self, client):
        key = client._generate_cache_key("p", "m", None)
        asyncio.run(client.generate("p", model="m", cache_key=key))
        assert client._get_from_cache(key) == {"response": "ок", "model": "m"}

    def test_corrupted_cache_returns_none(self, client):
        (client.cache_dir / "broken.json").write_text("{not json", encoding="utf-8")
        assert client._get_from_cache("broken") is None

    def test_stats_and_clear(self, client):
        client._save_to_cache("a", {"response": "1"})
        client._save_to_cache("b", {"response": "2"})
        assert client.get_cache_stats()["cached_requests"] == 2
        client.clear_cache()
        assert client.get_cache_stats()["cached_requests"] == 0
