"""Tests for LLM clients (OllamaClient, PromptTemplates, LlamaCppManager)."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


class TestOllamaCache:
    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        import app.modules.llm.ollama_client as module

        monkeypatch.setattr(module.ollama, "Client", lambda host=None: SimpleNamespace())
        client = module.OllamaClient()
        client.cache_dir = tmp_path / "cache"
        client.cache_dir.mkdir(parents=True, exist_ok=True)
        return client

    def test_defaults(self, client):
        assert client.base_url == "http://localhost:11434"
        assert client.max_tokens_per_request == 4000
        assert client.max_time_per_request == 30
        assert client.models["embedding"] == "nomic-embed-text"
        assert isinstance(client.semaphore, asyncio.Semaphore)

    def test_cache_key_is_deterministic(self, client):
        first = client._generate_cache_key("prompt", "model", "json")
        second = client._generate_cache_key("prompt", "model", "json")
        third = client._generate_cache_key("other", "model", "json")

        assert first == second
        assert first != third
        assert len(first) == 64
        assert first != client._generate_cache_key("prompt", "model", None)

    def test_cache_roundtrip(self, client):
        key = client._generate_cache_key("p", "m", None)
        assert client._get_from_cache(key) is None

        client._save_to_cache(key, {"response": "ответ", "done": True})
        assert client._get_from_cache(key) == {"response": "ответ", "done": True}

    def test_cache_stats_and_clear(self, client):
        assert client.get_cache_stats()["cached_requests"] == 0

        client._save_to_cache("a", {"response": "1"})
        client._save_to_cache("b", {"response": "2"})
        stats = client.get_cache_stats()
        assert stats["cached_requests"] == 2
        assert stats["total_size_bytes"] > 0
        assert stats["cache_dir"] == str(client.cache_dir)

        client.clear_cache()
        assert client.get_cache_stats()["cached_requests"] == 0

    def test_corrupted_cache_returns_none(self, client):
        key = "broken"
        (client.cache_dir / f"{key}.json").write_text("{not json", encoding="utf-8")
        assert client._get_from_cache(key) is None

    def test_generate_uses_cache(self, client):
        key = client._generate_cache_key("prompt", "model", None)
        client._save_to_cache(key, {"response": "cached"})

        result = asyncio.run(client.generate("prompt", model="model", cache_key=key))
        assert result == {"response": "cached"}

    def test_generate_calls_client_and_caches(self, client):
        calls = []

        def generate(**kwargs):
            calls.append(kwargs)
            return {"response": "fresh"}

        client.client = SimpleNamespace(generate=generate)

        result = asyncio.run(
            client.generate(
                "prompt",
                model="model",
                format_type="json",
                temperature=0.2,
                num_predict=999999,
                cache_key="key1",
            )
        )

        assert result == {"response": "fresh"}
        assert calls[0]["model"] == "model"
        assert calls[0]["format"] == "json"
        assert calls[0]["options"]["temperature"] == 0.2
        assert calls[0]["options"]["num_predict"] == 4000
        assert calls[0]["options"]["num_ctx"] == 4096
        assert client._get_from_cache("key1") == {"response": "fresh"}

    def test_generate_json_parses_response(self, client):
        async def fake_generate(**kwargs):
            assert kwargs["format_type"] == "json"
            assert kwargs["temperature"] == 0.3
            assert "JSON Schema" in kwargs["prompt"]
            return {"response": '{"answer": 42}'}

        client.generate = fake_generate
        result = asyncio.run(client.generate_json("prompt", schema_hint='{"answer": "int"}'))
        assert result == {"answer": 42}

    def test_generate_json_handles_bad_json(self, client):
        async def fake_generate(**kwargs):
            return {"response": "not json"}

        client.generate = fake_generate
        result = asyncio.run(client.generate_json("prompt"))
        assert result["error"] == "Failed to parse JSON"
        assert result["raw_response"] == "not json"

    def test_get_embedding(self, client):
        client.client = SimpleNamespace(embed=lambda model, input: {"embeddings": [[0.1, 0.2]]})
        assert client.get_embedding("text") == [0.1, 0.2]

    def test_get_embedding_failure(self, client):
        def embed(**kwargs):
            raise RuntimeError("offline")

        client.client = SimpleNamespace(embed=embed)
        assert client.get_embedding("text") == []


class TestPromptTemplates:
    @pytest.fixture()
    def templates(self):
        from app.modules.llm.ollama_client import PromptTemplates

        return PromptTemplates

    def test_intent_classifier_prompt(self, templates):
        prompt = templates.intent_classifier_prompt("перевези кольца", "объект 5")
        assert "перевези кольца" in prompt
        assert "объект 5" in prompt
        assert "MOVE_MATERIAL" in prompt
        assert '"domain_intent"' in prompt

    def test_contract_extraction_prompt(self, templates):
        prompt = templates.contract_extraction_prompt("текст договора")
        assert "текст договора" in prompt
        assert '"contract_amount"' in prompt

    def test_temporal_context_prompt_month_boundaries(self, templates):
        # Regression: replace(day=+1) used to crash at the end of a month.
        prompt = templates.temporal_context_prompt(datetime(2024, 1, 31, 12, 0))
        assert '"Сегодня" = 2024-01-31' in prompt
        assert '"Завтра" = 2024-02-01' in prompt
        assert '"Вчера" = 2024-01-30' in prompt
        assert '"Позавчера" = 2024-01-29' in prompt

    def test_temporal_context_prompt_year_boundary(self, templates):
        prompt = templates.temporal_context_prompt(datetime(2024, 12, 31, 23, 59))
        assert '"Завтра" = 2025-01-01' in prompt
        assert '"Позавчера" = 2024-12-29' in prompt

    def test_few_shot_rag_prompt(self, templates):
        prompt = templates.few_shot_rag_prompt("спецификация", ["урок 1", "урок 2"])
        assert "урок 1\n\nурок 2" in prompt
        assert "спецификация" in prompt
        assert '"violations"' in prompt


class TestLlamaCppManager:
    @pytest.fixture()
    def manager(self):
        from app.modules.llm.llama_cpp_manager import LlamaCppManager

        return LlamaCppManager(exe_path=None, base_url="http://localhost:9999")

    def test_init_defaults(self, manager):
        assert manager.base_url == "http://localhost:9999"
        assert manager.process is None
        assert manager.models == []

    def test_find_llama_server_returns_path_or_none(self, manager):
        result = manager._find_llama_server()
        assert result is None or isinstance(result, str)

    def test_start_server_without_executable(self, manager):
        manager.exe_path = None
        assert manager.start_server("model.gguf") is False

    def test_start_server_missing_model(self, manager, tmp_path):
        exe = tmp_path / "llama-server.exe"
        exe.write_text("", encoding="utf-8")
        manager.exe_path = str(exe)

        assert manager.start_server(str(tmp_path / "missing.gguf")) is False

    def test_start_server_already_running(self, manager):
        manager.process = object()
        assert manager.start_server("model.gguf") is True

    def test_start_server_embedding_builds_pooling_flag(self, manager, tmp_path, monkeypatch):
        import app.modules.llm.llama_cpp_manager as module

        exe = tmp_path / "llama-server.exe"
        exe.write_text("", encoding="utf-8")
        model = tmp_path / "bge-m3.gguf"
        model.write_text("", encoding="utf-8")
        manager.exe_path = str(exe)

        captured = {}

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured["cmd"] = cmd
                self.pid = 1
                self.stderr = None

        monkeypatch.setattr(module.subprocess, "Popen", FakePopen)
        monkeypatch.setattr(manager, "check_connection", lambda: True)

        assert manager.start_server(
            str(model), port=8081, n_gpu_layers=0, embeddings=True, pooling="cls"
        ) is True

        cmd = captured["cmd"]
        assert "--embedding" in cmd
        assert cmd[cmd.index("--pooling") + 1] == "cls"

    def test_start_server_chat_has_no_pooling(self, manager, tmp_path, monkeypatch):
        import app.modules.llm.llama_cpp_manager as module

        exe = tmp_path / "llama-server.exe"
        exe.write_text("", encoding="utf-8")
        model = tmp_path / "chat.gguf"
        model.write_text("", encoding="utf-8")
        manager.exe_path = str(exe)

        captured = {}

        class FakePopen:
            def __init__(self, cmd, **kwargs):
                captured["cmd"] = cmd
                self.pid = 1
                self.stderr = None

        monkeypatch.setattr(module.subprocess, "Popen", FakePopen)
        monkeypatch.setattr(manager, "check_connection", lambda: True)

        assert manager.start_server(str(model), embeddings=False, pooling="cls") is True
        assert "--embedding" not in captured["cmd"]
        assert "--pooling" not in captured["cmd"]

    def test_stop_server_without_process(self, manager):
        assert manager.stop_server() is True

    def test_stop_server_terminates(self, manager):
        class FakeProcess:
            def __init__(self):
                self.terminated = False
                self.waited = False

            def terminate(self):
                self.terminated = True

            def wait(self, timeout=None):
                self.waited = True

        process = FakeProcess()
        manager.process = process
        assert manager.stop_server() is True
        assert process.terminated and process.waited
        assert manager.process is None

    def test_stop_server_kills_on_timeout(self, manager):
        import subprocess

        class FakeProcess:
            def __init__(self):
                self.killed = False

            def terminate(self):
                pass

            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired(cmd="llama", timeout=timeout)

            def kill(self):
                self.killed = True

        process = FakeProcess()
        manager.process = process
        assert manager.stop_server() is True
        assert process.killed is True
        assert manager.process is None

    def test_check_connection_health(self, manager, monkeypatch):
        class Response:
            status_code = 200

        monkeypatch.setattr(
            "app.modules.llm.llama_cpp_manager.requests.get", lambda *a, **k: Response()
        )
        assert manager.check_connection() is True

    def test_check_connection_falls_back_to_props(self, manager, monkeypatch):
        calls = []

        class Response:
            def __init__(self, status):
                self.status_code = status

        def fake_get(url, timeout=None):
            calls.append(url)
            return Response(404 if url.endswith("/health") else 200)

        monkeypatch.setattr("app.modules.llm.llama_cpp_manager.requests.get", fake_get)
        assert manager.check_connection() is True
        assert len(calls) == 2

    def test_check_connection_failure(self, manager, monkeypatch):
        def fake_get(url, timeout=None):
            raise ConnectionError("down")

        monkeypatch.setattr("app.modules.llm.llama_cpp_manager.requests.get", fake_get)
        assert manager.check_connection() is False

    def test_get_model_info(self, manager, monkeypatch):
        class Response:
            status_code = 200

            def json(self):
                return {"model": "qwen"}

        monkeypatch.setattr(
            "app.modules.llm.llama_cpp_manager.requests.get", lambda *a, **k: Response()
        )
        assert manager.get_model_info() == {"model": "qwen"}

    def test_get_model_info_failure(self, manager, monkeypatch):
        def fake_get(*a, **k):
            raise RuntimeError("down")

        monkeypatch.setattr("app.modules.llm.llama_cpp_manager.requests.get", fake_get)
        assert manager.get_model_info() == {}

    def test_generate_success(self, manager, monkeypatch):
        calls = []

        class Response:
            status_code = 200
            text = ""

            def json(self):
                return {"content": "Сгенерированный текст"}

        def fake_post(url, json=None, timeout=None, stream=False):
            calls.append((url, json))
            return Response()

        monkeypatch.setattr("app.modules.llm.llama_cpp_manager.requests.post", fake_post)

        result = manager.generate("prompt", max_tokens=64, temperature=0.1, top_p=0.8, top_k=10)
        assert result == "Сгенерированный текст"

        completion = [c for c in calls if c[0].endswith("/completion")][0]
        assert completion[1]["prompt"] == "prompt"
        assert completion[1]["n_predict"] == 64
        assert completion[1]["temperature"] == 0.1
        assert completion[1]["top_p"] == 0.8
        assert completion[1]["top_k"] == 10
        assert completion[1]["stream"] is False

    def test_generate_non_200(self, manager, monkeypatch):
        class Response:
            status_code = 500
            text = "server error"

        monkeypatch.setattr(
            "app.modules.llm.llama_cpp_manager.requests.post",
            lambda *a, **k: Response(),
        )
        assert manager.generate("prompt") == ""

    def test_generate_exception(self, manager, monkeypatch):
        def fake_post(*a, **k):
            raise ConnectionError("down")

        monkeypatch.setattr("app.modules.llm.llama_cpp_manager.requests.post", fake_post)
        assert manager.generate("prompt") == ""

    def test_generate_stream(self, manager, monkeypatch):
        lines = [b'{"content": "a"}', b"", b'{"content": "b"}', b"bad json"]

        class Response:
            def iter_lines(self):
                return iter(lines)

        monkeypatch.setattr(
            "app.modules.llm.llama_cpp_manager.requests.post",
            lambda *a, **k: Response(),
        )
        assert list(manager.generate_stream("prompt")) == ["a", "b"]

    def test_generate_stream_exception(self, manager, monkeypatch):
        def fake_post(*a, **k):
            raise ConnectionError("down")

        monkeypatch.setattr("app.modules.llm.llama_cpp_manager.requests.post", fake_post)
        assert list(manager.generate_stream("prompt")) == []

    def test_recommended_models_registry(self):
        from app.modules.llm.llama_cpp_manager import RECOMMENDED_MODELS

        assert "qwen2.5-14b-instruct-q4" in RECOMMENDED_MODELS
        for info in RECOMMENDED_MODELS.values():
            assert info["url"].endswith(".gguf")
            assert info["description"]

    def test_download_model_unknown(self, tmp_path):
        from app.modules.llm.llama_cpp_manager import download_model

        with pytest.raises(ValueError):
            download_model("unknown", str(tmp_path))

    def test_download_model_already_exists(self, tmp_path):
        from app.modules.llm.llama_cpp_manager import RECOMMENDED_MODELS, download_model

        name = "qwen2.5-14b-instruct-q4"
        filename = RECOMMENDED_MODELS[name]["url"].split("/")[-1]
        (tmp_path / filename).write_bytes(b"gguf")

        assert download_model(name, str(tmp_path)) == str(tmp_path / filename)

    def test_download_model_success(self, tmp_path, monkeypatch):
        from app.modules.llm.llama_cpp_manager import RECOMMENDED_MODELS, download_model

        name = "qwen2.5-14b-instruct-q4"
        filename = RECOMMENDED_MODELS[name]["url"].split("/")[-1]

        class Response:
            headers = {"content-length": "4"}

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size):
                return iter([b"gg", b"uf"])

        monkeypatch.setattr(
            "app.modules.llm.llama_cpp_manager.requests.get", lambda *a, **k: Response()
        )

        path = download_model(name, str(tmp_path))
        assert Path(path).read_bytes() == b"gguf"
        assert Path(path).name == filename
