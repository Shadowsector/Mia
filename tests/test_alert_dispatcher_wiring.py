"""Tests for bot alert-dispatcher wiring."""


class FakeSender:
    def send(self, recipient_id, message):
        return True


def test_disabled_returns_none():
    from app.bot.main import build_alert_dispatcher

    assert build_alert_dispatcher(FakeSender(), enabled=False, chat_id="1") is None


def test_enabled_without_chat_id_returns_none():
    from app.bot.main import build_alert_dispatcher

    assert build_alert_dispatcher(FakeSender(), enabled=True, chat_id="") is None


def test_enabled_with_chat_id_builds_dispatcher():
    from app.bot.main import build_alert_dispatcher
    from app.modules.temporal.alert_dispatcher import AlertDispatcher

    dispatcher = build_alert_dispatcher(FakeSender(), enabled=True, chat_id="-100500")
    assert isinstance(dispatcher, AlertDispatcher)
    assert dispatcher.admin_user_id == "-100500"
    assert dispatcher.health_engine is not None
    assert dispatcher.temporal_manager is not None


class TestBuildSender:
    def test_allowlist_disabled(self, monkeypatch):
        import config.settings as cfg
        from app.bot.main import build_sender

        monkeypatch.setattr(cfg, "TELEGRAM_ALLOWLIST_ONLY", False)
        assert build_sender().allowlist_enabled is False

    def test_allowlist_with_owner(self, monkeypatch):
        import config.settings as cfg
        from app.bot.main import build_sender

        monkeypatch.setattr(cfg, "TELEGRAM_ALLOWLIST_ONLY", True)
        monkeypatch.setattr(cfg, "TELEGRAM_OWNER_CHAT_ID", "123")
        sender = build_sender()
        assert sender.allowlist_enabled is True
        assert sender.is_allowed(123) is True
        assert sender.is_allowed(999) is False

    def test_allowlist_without_owner_blocks_all(self, monkeypatch):
        import config.settings as cfg
        from app.bot.main import build_sender

        monkeypatch.setattr(cfg, "TELEGRAM_ALLOWLIST_ONLY", True)
        monkeypatch.setattr(cfg, "TELEGRAM_OWNER_CHAT_ID", "")
        sender = build_sender()
        assert sender.allowlist_enabled is True
        assert sender.is_allowed(123) is False

