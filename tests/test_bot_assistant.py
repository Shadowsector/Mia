"""Tests for PmOsAssistant orchestrator."""

from types import SimpleNamespace

import pytest

from app.modules.llm.llama_cpp_client import LlamaCppError


class FakeLlama:
    def __init__(self, reply="ответ модели", error=None):
        self.reply = reply
        self.error = error
        self.calls = []
        self.messages_seen = []

    def chat(self, messages, **kwargs):
        self.messages_seen.append(messages)
        self.calls.append(("chat", messages[-1]["content"]))
        if self.error:
            raise self.error
        return self.reply

    def complete(self, system, user, **kwargs):
        self.calls.append((system, user))
        if self.error:
            raise self.error
        return self.reply


class FakeDelegation:
    def __init__(
        self,
        pending=None,
        intercept=False,
        request=None,
        candidates=None,
        user="auto",
        question_id=42,
    ):
        self._pending = pending or []
        self._intercept = intercept
        self._request = request
        self._candidates = candidates if candidates is not None else []
        self._user = user
        self._question_id = question_id
        self.delegated = []

    def get_pending_questions(self, user_id=None):
        return self._pending

    def intercept_answer(self, message, question_id):
        return self._intercept

    def try_parse_delegation(self, text, context=""):
        return self._request

    def find_user_by_name(self, name, object_id):
        return self._candidates

    def resolve_ambiguous_user(self, candidates, context):
        if self._user == "auto":
            return candidates[0] if candidates else None
        return self._user

    def delegate_question(self, request, user):
        self.delegated.append((request, user))
        return self._question_id


def _request():
    return SimpleNamespace(
        target_name="Света",
        question_context="когда будет смета по объекту X",
        object_id="OBJ-1",
    )


@pytest.fixture()
def assistant():
    from app.bot.assistant import PmOsAssistant

    llama = FakeLlama()
    delegation = FakeDelegation()
    return (
        PmOsAssistant(llm=llama, delegation=delegation, router=None),
        llama,
        delegation,
    )


class TestChat:
    def test_empty_text(self, assistant):
        a, _, _ = assistant
        assert a.handle_text("   ") == "Я на связи! Чем помочь?"

    def test_plain_chat(self, assistant):
        a, llama, _ = assistant
        assert a.handle_text("привет", chat_id=1) == "ответ модели"
        assert llama.calls

    def test_llm_error_fallback(self):
        from app.bot.assistant import PmOsAssistant

        a = PmOsAssistant(llm=FakeLlama(error=LlamaCppError("down")), delegation=None)
        assert "llama.cpp" in a.handle_text("привет")

    def test_no_delegation_engine(self):
        from app.bot.assistant import PmOsAssistant

        a = PmOsAssistant(llm=FakeLlama(reply="ок"), delegation=None)
        assert a.handle_text("что нового?") == "ок"


class TestDelegation:
    def test_delegates_when_request_parsed(self):
        from app.bot.assistant import PmOsAssistant

        d = FakeDelegation(request=_request(), candidates=[{"user_id": 7}])
        a = PmOsAssistant(llm=FakeLlama(), delegation=d)
        reply = a.handle_text("спроси у Светы, когда смета", chat_id=1)
        assert "Передала вопрос Света" in reply
        assert len(d.delegated) == 1

    def test_ambiguous_user_message(self):
        from app.bot.assistant import PmOsAssistant

        d = FakeDelegation(request=_request(), candidates=[], user=None)
        a = PmOsAssistant(llm=FakeLlama(), delegation=d)
        reply = a.handle_text("спроси у Светы", chat_id=1)
        assert "Inbox" in reply
        assert d.delegated == []

    def test_not_delegation_falls_to_chat(self, assistant):
        a, _, d = assistant
        d._request = None
        assert a.handle_text("просто сообщение") == "ответ модели"

    def test_parse_error_falls_to_chat(self):
        from app.bot.assistant import PmOsAssistant

        class Boom(FakeDelegation):
            def try_parse_delegation(self, text, context=""):
                raise RuntimeError("llm down")

        a = PmOsAssistant(llm=FakeLlama(reply="ответ"), delegation=Boom())
        assert a.handle_text("спроси у Светы") == "ответ"


class TestIntercept:
    def test_intercept_true_short_circuits(self):
        from app.bot.assistant import PmOsAssistant

        d = FakeDelegation(pending=[{"question_id": 5}], intercept=True)
        llama = FakeLlama()
        a = PmOsAssistant(llm=llama, delegation=d)
        reply = a.handle_text("да, будет в пятницу", user_id=99)
        assert "записала ответ" in reply.lower()
        assert llama.calls == []

    def test_intercept_false_falls_through(self):
        from app.bot.assistant import PmOsAssistant

        d = FakeDelegation(pending=[{"question_id": 5}], intercept=False)
        a = PmOsAssistant(llm=FakeLlama(reply="ответ"), delegation=d)
        assert a.handle_text("это мем", user_id=99) == "ответ"

    def test_no_user_id_skips_intercept(self, assistant):
        a, _, d = assistant
        d._pending = [{"question_id": 5}]
        d._intercept = True
        assert a.handle_text("что-то", user_id=None) == "ответ модели"


class TestConversationMemory:
    def test_trim_by_turns(self):
        from app.bot.assistant import ConversationMemory

        m = ConversationMemory(max_turns=2, max_chars=100000)
        for i in range(5):
            m.append("c", f"u{i}", f"a{i}")
        turns = m.get("c")
        assert len(turns) == 4
        assert turns[0]["content"] == "u3"
        assert turns[-1]["content"] == "a4"

    def test_trim_by_chars(self):
        from app.bot.assistant import ConversationMemory

        m = ConversationMemory(max_turns=50, max_chars=20)
        m.append("c", "x" * 15, "y" * 15)
        m.append("c", "z", "w")
        turns = m.get("c")
        assert [t["content"] for t in turns] == ["z", "w"]

    def test_clear(self):
        from app.bot.assistant import ConversationMemory

        m = ConversationMemory()
        m.append("c", "u", "a")
        m.clear("c")
        assert m.get("c") == []


class TestHistory:
    def test_history_passed_to_llm(self):
        from app.bot.assistant import PmOsAssistant

        llama = FakeLlama()
        a = PmOsAssistant(llm=llama, delegation=None)
        a.handle_text("привет", chat_id=1)
        a.handle_text("а помнишь?", chat_id=1)
        second = llama.messages_seen[-1]
        assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
        assert second[1]["content"] == "привет"
        assert second[2]["content"] == "ответ модели"

    def test_history_scoped_per_chat(self):
        from app.bot.assistant import PmOsAssistant

        llama = FakeLlama()
        a = PmOsAssistant(llm=llama, delegation=None)
        a.handle_text("привет", chat_id=1)
        a.handle_text("другой чат", chat_id=2)
        assert llama.messages_seen[-1][1]["content"] == "другой чат"
        assert len(llama.messages_seen[-1]) == 2

    def test_error_not_stored_in_history(self):
        from app.bot.assistant import PmOsAssistant

        llama = FakeLlama(error=LlamaCppError("down"))
        a = PmOsAssistant(llm=llama, delegation=None)
        a.handle_text("привет", chat_id=1)
        assert a.memory.get("1") == []

    def test_clear_history(self):
        from app.bot.assistant import PmOsAssistant

        llama = FakeLlama()
        a = PmOsAssistant(llm=llama, delegation=None)
        a.handle_text("привет", chat_id=1)
        a.clear_history(1)
        a.handle_text("снова привет", chat_id=1)
        assert len(llama.messages_seen[-1]) == 2

    def test_fallback_when_no_chat_method(self):
        from app.bot.assistant import PmOsAssistant

        class OnlyComplete:
            def complete(self, system, user, **kwargs):
                return "ok"

        a = PmOsAssistant(llm=OnlyComplete(), delegation=None)
        assert a.handle_text("привет", chat_id=1) == "ok"


class FakeRouter:
    def __init__(self, reply="ОТВЕТ РОУТЕРА", match="потрачено"):
        self.reply = reply
        self.match = match

    def query(self, text):
        return self.reply if self.match in text else None


class TestRouting:
    def test_router_answer_used(self):
        from app.bot.assistant import PmOsAssistant

        a = PmOsAssistant(llm=FakeLlama(), delegation=None, router=FakeRouter())
        assert a.handle_text("сколько потрачено по объекту X") == "ОТВЕТ РОУТЕРА"

    def test_router_none_falls_to_chat(self):
        from app.bot.assistant import PmOsAssistant

        a = PmOsAssistant(llm=FakeLlama(reply="ок"), delegation=None, router=FakeRouter())
        assert a.handle_text("привет") == "ок"

    def test_delegation_takes_priority_over_router(self):
        from app.bot.assistant import PmOsAssistant

        d = FakeDelegation(request=_request(), candidates=[{"user_id": 7}])
        a = PmOsAssistant(llm=FakeLlama(), delegation=d, router=FakeRouter())
        reply = a.handle_text("спроси у Светы, сколько потрачено")
        assert "Передала вопрос Света" in reply
        assert len(d.delegated) == 1
