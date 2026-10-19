"""Tests for the Safe Tool Generation Layer (Job #6.10)."""

import pytest

from app.core.safe_tool_layer import (
    MiaTool,
    SafeToolLayer,
    ToolPermission,
    get_safe_tool_layer,
    ReadFileTool,
    WriteFileTool,
    SearchObjectsTool,
    GetObjectEventsTool,
    GetHealthScoreTool,
    SearchMessagesTool,
)
from app.modules.storage.database import (
    initialize_database,
    get_db_connection,
)


@pytest.fixture(scope="module")
def layer():
    initialize_database()
    return SafeToolLayer()


@pytest.fixture()
def db():
    initialize_database()
    with get_db_connection() as conn:
        yield conn


class TestToolRegistration:
    def test_builtin_tools_registered(self, layer):
        names = set(layer.tools.keys())
        assert {
            "search_objects",
            "get_object_events",
            "get_health_score",
            "search_messages",
            "read_file",
            "write_file",
        } <= names

    def test_no_raw_sql_tool(self, layer):
        assert "query_database" not in layer.tools

    def test_all_builtins_read_only_or_write_safe(self, layer):
        for tool in layer.tools.values():
            assert tool.permission in (ToolPermission.READ_ONLY, ToolPermission.WRITE_SAFE)

    def test_global_singleton(self):
        a = get_safe_tool_layer()
        b = get_safe_tool_layer()
        assert a is b

    def test_schema_shape(self, layer):
        schemas = layer.get_tool_schemas()
        assert all("name" in s and "parameters" in s and "permission" in s for s in schemas)


class TestParameterValidation:
    def test_missing_required_parameter(self, layer):
        result = layer.execute_tool("search_objects", {})
        assert not result["success"]
        assert "query" in result["error"]

    def test_type_conversion(self, layer):
        tool = SearchObjectsTool()
        ok, err = tool.validate_parameters({"query": "x", "limit": "5"})
        assert ok, err
        assert isinstance(tool.parameters["limit"], dict)

    def test_invalid_type_rejected(self):
        tool = GetHealthScoreTool()
        ok, err = tool.validate_parameters({})
        assert not ok
        assert "object_id" in err

    def test_custom_validation_rejected(self):
        class T(MiaTool):
            def __init__(self):
                super().__init__("t", "t", ToolPermission.READ_ONLY)
                self.define_parameter(
                    "x", int, True, "", validation=lambda v: (False, "nope")
                )

            def execute(self, params):
                return {}

        ok, err = T().validate_parameters({"x": 1})
        assert not ok
        assert "nope" in err


class TestPermissions:
    def test_unknown_tool(self, layer):
        result = layer.execute_tool("does_not_exist", {})
        assert not result["success"]
        assert "not found" in result["error"]

    def test_forbidden_tool_blocked(self, layer):
        class Evil(MiaTool):
            def __init__(self):
                super().__init__("evil", "evil", ToolPermission.FORBIDDEN)

            def execute(self, params):
                return {"pwned": True}

        layer.register_tool(Evil())
        result = layer.execute_tool("evil", {})
        assert not result["success"]
        assert "forbidden" in result["error"]
        del layer.tools["evil"]

    def test_dangerous_requires_approval(self, layer):
        class Danger(MiaTool):
            def __init__(self):
                super().__init__("danger", "danger", ToolPermission.DANGEROUS)

            def execute(self, params):
                return {"done": True}

        layer.register_tool(Danger())
        try:
            # No callback
            result = layer.execute_tool("danger", {})
            assert not result["success"]
            # Declined
            result = layer.execute_tool("danger", {}, approval_callback=lambda n, p: False)
            assert not result["success"]
            # Approved
            result = layer.execute_tool("danger", {}, approval_callback=lambda n, p: True)
            assert result["success"]
        finally:
            del layer.tools["danger"]

    def test_write_file_approval_flow(self, layer, tmp_path):
        target = tmp_path / "out.txt"
        # WRITE_SAFE executes without approval callback (only DANGEROUS gates)
        result = layer.execute_tool(
            "write_file", {"file_path": str(target), "content": "hi"}
        )
        assert not result["success"]  # path outside C:\mia rejected
        assert "C:\\mia" in result["error"]


class TestToolCallParsing:
    def test_parse_dict_payload(self, layer):
        ok, name, params, err = layer.parse_tool_call(
            {"tool": "search_objects", "parameters": {"query": "x"}}
        )
        assert ok and name == "search_objects" and params == {"query": "x"}

    def test_parse_json_string(self, layer):
        ok, name, params, err = layer.parse_tool_call(
            '{"tool": "get_health_score", "parameters": {"object_id": "obj-1"}}'
        )
        assert ok and name == "get_health_score"
        assert params["object_id"] == "obj-1"

    def test_parse_alternate_keys(self, layer):
        ok, name, params, _ = layer.parse_tool_call(
            '{"tool_name": "search_objects", "arguments": {"query": "y"}}'
        )
        assert ok and name == "search_objects" and params == {"query": "y"}

    def test_parse_fenced_json(self, layer):
        payload = 'Вот вызов:\n```json\n{"tool": "search_objects", "parameters": {"query": "z"}}\n```'
        ok, name, params, _ = layer.parse_tool_call(payload)
        assert ok and name == "search_objects" and params == {"query": "z"}

    def test_parse_bare_parameters_ambiguous(self, layer):
        ok, _, _, err = layer.parse_tool_call('{"query": "x"}')
        # Several tools registered → name cannot be inferred
        assert not ok
        assert "cannot be inferred" in err

    def test_parse_invalid_json(self, layer):
        ok, _, _, err = layer.parse_tool_call("{broken json")
        assert not ok
        assert "not valid JSON" in err

    def test_parse_wrong_payload_type(self, layer):
        ok, _, _, err = layer.parse_tool_call(42)
        assert not ok
        assert "Unsupported" in err

    def test_execute_tool_call_end_to_end(self, layer, db):
        db.execute(
            "INSERT OR IGNORE INTO objects (object_name, object_id) VALUES (?, ?)",
            ("Тестовый объект Судаково", "test-obj-1"),
        )
        db.commit()
        result = layer.execute_tool_call(
            '{"tool": "search_objects", "parameters": {"query": "Судаково"}}'
        )
        assert result["success"]
        assert result["result"]["count"] >= 1

    def test_execute_tool_call_parse_failure(self, layer):
        result = layer.execute_tool_call("not json at all")
        assert not result["success"]
        assert "Invalid tool call" in result["error"]


class TestSemanticTools:
    def test_search_objects(self, layer, db):
        db.execute(
            "INSERT OR IGNORE INTO objects (object_name, object_id, customer) "
            "VALUES (?, ?, ?)",
            ("Профсоюзная 15", "test-obj-2", "ООО Ростелеком"),
        )
        db.commit()
        result = layer.execute_tool("search_objects", {"query": "Ростелеком"})
        assert result["success"]
        assert result["result"]["count"] >= 1

    def test_search_objects_limit_capped(self, layer):
        result = layer.execute_tool(
            "search_objects", {"query": "а", "limit": 100000}
        )
        assert result["success"]
        assert result["result"]["count"] <= 100

    def test_get_object_events_unknown_object(self, layer):
        result = layer.execute_tool("get_object_events", {"object_id": "no-such-object"})
        assert result["success"]
        assert result["result"]["count"] == 0
        assert "not found" in result["result"].get("error", "")

    def test_get_object_events_with_data(self, layer, db):
        db.execute(
            "INSERT OR IGNORE INTO objects (object_name, object_id) VALUES (?, ?)",
            ("Тестовый объект 3", "test-obj-3"),
        )
        diary_id = db.execute(
            "SELECT diary_id FROM objects WHERE object_id = ?", ("test-obj-3",)
        ).fetchone()[0]
        db.execute(
            "INSERT INTO diary_events (diary_id, event_type, event_timestamp, "
            "entity_type, entity_id, summary) VALUES (?, ?, ?, ?, ?, ?)",
            (diary_id, "contract_created", "2026-01-15T10:00:00",
             "contract", "c-1", "Подписан договор"),
        )
        db.commit()
        result = layer.execute_tool("get_object_events", {"object_id": "test-obj-3"})
        assert result["success"]
        assert result["result"]["count"] >= 1

    def test_get_health_score_missing(self, layer):
        result = layer.execute_tool("get_health_score", {"object_id": "nope"})
        assert result["success"]
        assert result["result"]["count"] == 0

    def test_get_health_score_with_data(self, layer, db):
        db.execute(
            "INSERT INTO health_scores (object_id, score, zone) VALUES (?, ?, ?)",
            ("test-obj-4", 91.0, "RED"),
        )
        db.commit()
        result = layer.execute_tool("get_health_score", {"object_id": "test-obj-4"})
        assert result["success"]
        assert result["result"]["row"]["zone"] == "RED"

    def test_search_messages(self, layer, db):
        db.execute(
            "INSERT INTO telegram_messages (telegram_chat_id, user_id, message_text) "
            "VALUES (?, ?, ?)",
            (777, 1, "Привезли кольца ККС на Судакова"),
        )
        db.commit()
        result = layer.execute_tool("search_messages", {"query": "кольца"})
        assert result["success"]
        assert result["result"]["count"] >= 1

    def test_search_messages_chat_filter(self, layer):
        result = layer.execute_tool(
            "search_messages", {"query": "кольца", "chat_id": 123456789}
        )
        assert result["success"]
        assert result["result"]["count"] == 0

    def test_sql_injection_is_inert(self, layer, db):
        # Parameterized queries: injection attempt must not match everything
        result = layer.execute_tool(
            "search_objects", {"query": "'; DROP TABLE objects; --"}
        )
        assert result["success"]
        # Table must still exist
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='objects'"
        ).fetchone()
        assert row is not None
