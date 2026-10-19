"""Tests for PmOsAssistant orchestrator."""

from types import SimpleNamespace

import pytest

from app.modules.llm.llama_cpp_client import LlamaCppError


class FakeLlama:
    def __init__(self, reply="ответ модели", error=None):
        self.reply = reply
        self.error = error
        self.calls = []

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
    return PmOsAssistant(llm=llama, delegation=delegation), llama, delegation


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
