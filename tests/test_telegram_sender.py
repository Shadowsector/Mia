"""Tests for TelegramSender adapter."""

import pytest


class FakeBot:
    def __init__(self):
        self.sent = []
        self.raise_on_send = False

    def send_message(self, chat_id=None, text=None):
        if self.raise_on_send:
            raise RuntimeError("telegram down")
        self.sent.append((chat_id, text))


@pytest.fixture()
def sender():
    from app.modules.telegram import TelegramSender

    bot = FakeBot()
    return TelegramSender(bot=bot), bot


class TestSend:
    def test_send_to_recipient(self, sender):
        s, bot = sender
        assert s.send(123, "привет") is True
        assert bot.sent == [(123, "привет")]

    def test_send_uses_default_chat_id(self, sender):
        from app.modules.telegram import TelegramSender

        bot = FakeBot()
        s = TelegramSender(bot=bot, default_chat_id=-100)
        assert s.send(None, "hi") is True
        assert bot.sent == [(-100, "hi")]

    def test_send_without_chat_id_returns_false(self, sender):
        s, bot = sender
        assert s.send(None, "hi") is False
        assert bot.sent == []

    def test_send_invalid_recipient_returns_false(self, sender):
        s, bot = sender
        assert s.send("не-число", "hi") is False
        assert bot.sent == []

    def test_send_swallows_bot_errors(self, sender):
        s, bot = sender
        bot.raise_on_send = True
        assert s.send(1, "hi") is False


class TestPrivate:
    def test_unknown_user_returns_false(self, sender):
        s, _ = sender
        assert s.can_send_private(55) is False

    def test_registered_user_returns_true(self, sender):
        s, _ = sender
        s.register(55)
        assert s.can_send_private(55) is True

    def test_invalid_user_returns_false(self, sender):
        s, _ = sender
        assert s.can_send_private("x") is False


class TestConstruction:
    def test_missing_token_raises(self, monkeypatch):
        import config.settings as cfg
        from app.modules.telegram import TelegramSender, TelegramSenderError

        monkeypatch.setattr(cfg, "BOT_TOKEN", "")
        with pytest.raises(TelegramSenderError):
            TelegramSender()
