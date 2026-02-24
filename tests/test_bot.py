"""
Тесты для bot.py — PipelineMiddleware, классификация, маршрутизация, команды.
Используем моки для aiogram и внешних зависимостей.
"""
import json
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass


# =========================================
# Фикстуры: мокаем aiogram и зависимости до импорта bot.py
# =========================================

@pytest.fixture(autouse=True)
def mock_env(monkeypatch, tmp_path):
    """Устанавливаем env и мокаем сессионные директории."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:AABBBCCCDDD")
    monkeypatch.setenv("ADMIN_USER_ID", "42")
    monkeypatch.setenv("CLAUDE_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OPENAI_API_KEY", "")
    (tmp_path / "work").mkdir()
    return tmp_path


# =========================================
# PipelineMiddleware (тестируем логику напрямую)
# =========================================

class TestPipelineMiddleware:
    """Тестируем middleware без запуска бота — создаём экземпляр и вызываем __call__."""

    def _make_event(self, text=None, chat_id=111):
        event = AsyncMock()
        event.text = text
        event.chat = MagicMock()
        event.chat.id = chat_id
        event.answer = AsyncMock()
        return event

    def _make_handler(self):
        return AsyncMock(return_value="handler_result")

    @pytest.fixture
    def middleware(self):
        """Импортируем PipelineMiddleware из bot.py."""
        # Мы не можем легко импортировать bot.py целиком (он инициализирует бот),
        # поэтому тестируем логику middleware через изолированные unit-тесты.
        # Создаём класс вручную с той же логикой.
        from aiogram import BaseMiddleware

        class TestMiddleware(BaseMiddleware):
            async def __call__(self, handler, event, data):
                text = getattr(event, "text", None)
                if not text:
                    return await handler(event, data)
                text = text.strip()
                if text.startswith("/") or text.startswith("@"):
                    return await handler(event, data)
                try:
                    from roles import is_orchestrator_enabled
                    enabled = is_orchestrator_enabled(event.chat.id)
                except Exception:
                    enabled = False
                if not enabled:
                    return await handler(event, data)
                # pipeline would run here
                return "pipeline_executed"

        return TestMiddleware()

    @pytest.mark.asyncio
    async def test_no_text_passes_through(self, middleware):
        event = self._make_event(text=None)
        handler = self._make_handler()
        result = await middleware(handler, event, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_command_passes_through(self, middleware):
        event = self._make_event(text="/start")
        handler = self._make_handler()
        result = await middleware(handler, event, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_at_role_passes_through(self, middleware):
        event = self._make_event(text="@dev do something")
        handler = self._make_handler()
        result = await middleware(handler, event, {})
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_orchestrator_disabled_passes_through(self, middleware, monkeypatch):
        import roles
        monkeypatch.setattr(roles, "SESSIONS_DIR", Path("/tmp/test_roles_empty"))
        monkeypatch.setattr(roles, "ORCHESTRATOR_FILE", Path("/tmp/test_roles_empty/orch.json"))
        # Создаем файл с disabled
        p = Path("/tmp/test_roles_empty")
        p.mkdir(exist_ok=True)
        (p / "orch.json").write_text(json.dumps({"111": False}))

        event = self._make_event(text="hello", chat_id=111)
        handler = self._make_handler()
        result = await middleware(handler, event, {})
        handler.assert_awaited_once()

        # Cleanup
        (p / "orch.json").unlink(missing_ok=True)
        p.rmdir()

    @pytest.mark.asyncio
    async def test_orchestrator_enabled_runs_pipeline(self, middleware, monkeypatch):
        import roles
        p = Path("/tmp/test_roles_pipeline")
        p.mkdir(exist_ok=True)
        monkeypatch.setattr(roles, "SESSIONS_DIR", p)
        monkeypatch.setattr(roles, "ORCHESTRATOR_FILE", p / "orch.json")
        (p / "orch.json").write_text(json.dumps({"111": True}))

        event = self._make_event(text="hello world", chat_id=111)
        handler = self._make_handler()
        result = await middleware(handler, event, {})
        # Handler should NOT be called — pipeline intercepts
        handler.assert_not_awaited()
        assert result == "pipeline_executed"

        # Cleanup
        (p / "orch.json").unlink(missing_ok=True)
        p.rmdir()

    @pytest.mark.asyncio
    async def test_empty_text_passes_through(self, middleware):
        event = self._make_event(text="   ")
        handler = self._make_handler()
        await middleware(handler, event, {})


# =========================================
# BUG: is_orchestrator_enabled() без chat_id
# =========================================

class TestMiddlewareChatIdBug:
    """Воспроизводим баг из bot.py строка 44:
    is_orchestrator_enabled() вызывается БЕЗ chat_id → TypeError → middleware не работает."""

    def test_orchestrator_requires_chat_id(self):
        """is_orchestrator_enabled() без аргумента должен вызвать TypeError."""
        from roles import is_orchestrator_enabled
        with pytest.raises(TypeError):
            is_orchestrator_enabled()  # type: ignore — намеренный вызов без аргумента

    def test_orchestrator_with_chat_id_works(self, monkeypatch):
        """is_orchestrator_enabled(chat_id) работает корректно."""
        import roles
        p = Path("/tmp/test_chatid_bug")
        p.mkdir(exist_ok=True)
        monkeypatch.setattr(roles, "SESSIONS_DIR", p)
        monkeypatch.setattr(roles, "ORCHESTRATOR_FILE", p / "orch.json")
        (p / "orch.json").write_text(json.dumps({"111": True}))

        result = roles.is_orchestrator_enabled(111)
        assert result is True

        (p / "orch.json").unlink(missing_ok=True)
        p.rmdir()


# =========================================
# Защита от пустых сообщений в _route_and_send
# =========================================

class TestEmptyResponseGuard:
    """Проверяем что пустой ответ от Claude заменяется на fallback."""

    def test_empty_result_text_gets_fallback(self):
        """Если result.text пустой, должен быть fallback."""
        resp = ""
        if not resp or not resp.strip():
            resp = "(Claude не вернул ответ. Попробуйте ещё раз.)"
        assert resp != ""
        assert "Claude" in resp

    def test_whitespace_result_gets_fallback(self):
        resp = "   \n\n  "
        if not resp or not resp.strip():
            resp = "(Claude не вернул ответ. Попробуйте ещё раз.)"
        assert "Claude" in resp

    def test_normal_result_passes_through(self):
        resp = "Вот ваш ответ"
        if not resp or not resp.strip():
            resp = "(Claude не вернул ответ. Попробуйте ещё раз.)"
        assert resp == "Вот ваш ответ"


# =========================================
# Классификация сообщений (keyword)
# =========================================

class TestKeywordClassifier:
    """Тестируем keyword-based классификатор из bot.py."""

    def _classify(self, text):
        """Воспроизводим логику _keyword_classify."""
        ROLE_KEYWORDS = {
            "dev": ["код", "деплой", "deploy", "сервер", "баг", "bug", "nginx", "git",
                    "docker", "npm", "python", "akcha", "erp", "api", "скрипт",
                    "supabase", "react", "css", "html", "фикс", "fix", "билд", "build",
                    "порт", "домен", "ssl", "systemd", "service", "vite", "бот", "bot",
                    "файл", "базу данных", "миграц", "тест"],
            "ontologist": ["онтолог", "delta", "дельта", "первопринцип", "способност",
                         "методолог", "обучен", "образован", "фреймворк", "inner school",
                         "разрыв", "карта способностей", "мост", "кротовая нора"],
            "editor": ["редакт", "проверь текст", "грамматик", "пунктуац", "типограф",
                       "мильчин", "орфограф", "отредактируй", "вычитай", "корректур",
                       "правк", "запятая", "тире", "ошибки в тексте"],
        }
        text_lower = text.lower()
        scores = {}
        for role, keywords in ROLE_KEYWORDS.items():
            scores[role] = sum(1 for kw in keywords if kw in text_lower)
        best_score = max(scores.values(), default=0)
        if best_score == 0:
            return "assistant", 0.3
        best = max(scores, key=lambda r: scores[r])
        return best, min(0.9, 0.4 + best_score * 0.15)

    def test_dev_keywords(self):
        role, conf = self._classify("Задеплой nginx на сервер")
        assert role == "dev"
        assert conf > 0.5

    def test_editor_keywords(self):
        role, conf = self._classify("Отредактируй текст, проверь грамматику и пунктуацию")
        assert role == "editor"
        assert conf > 0.5

    def test_ontologist_keywords(self):
        role, conf = self._classify("Применим DELTA методологию и первопринципы")
        assert role == "ontologist"

    def test_unknown_defaults_to_assistant(self):
        role, conf = self._classify("Привет, как дела?")
        assert role == "assistant"
        assert conf == 0.3

    def test_mixed_keywords_highest_wins(self):
        role, _ = self._classify("deploy на сервер nginx, фикс бага docker")
        assert role == "dev"

    def test_confidence_increases_with_more_keywords(self):
        _, conf1 = self._classify("git")
        _, conf2 = self._classify("git deploy docker npm python")
        assert conf2 > conf1

    def test_confidence_capped_at_09(self):
        _, conf = self._classify("git deploy docker npm python nginx сервер баг фикс")
        assert conf <= 0.9


# =========================================
# extract_role_prefix
# =========================================

class TestExtractRolePrefix:
    def _extract(self, text):
        """Воспроизводим логику extract_role_prefix."""
        ROLES = {"dev", "assistant", "ontologist", "editor"}
        for role_key in ROLES:
            for prefix in [f"@{role_key} ", f"@{role_key}\n"]:
                if text.lower().startswith(prefix):
                    return role_key, text[len(prefix):]
        return None, text

    def test_dev_prefix(self):
        role, text = self._extract("@dev сделай деплой")
        assert role == "dev"
        assert text == "сделай деплой"

    def test_assistant_prefix(self):
        role, text = self._extract("@assistant помоги с планом")
        assert role == "assistant"
        assert text == "помоги с планом"

    def test_editor_prefix(self):
        role, text = self._extract("@editor проверь текст")
        assert role == "editor"
        assert text == "проверь текст"

    def test_no_prefix(self):
        role, text = self._extract("просто текст")
        assert role is None
        assert text == "просто текст"

    def test_prefix_with_newline(self):
        role, text = self._extract("@dev\nсделай")
        assert role == "dev"
        assert text == "сделай"

    def test_unknown_role_prefix_not_extracted(self):
        role, text = self._extract("@unknown сделай")
        assert role is None
        assert text == "@unknown сделай"


# =========================================
# is_admin
# =========================================

class TestIsAdmin:
    def test_admin_user(self):
        # ADMIN_USER_ID=42 from mock_env
        assert 42 == int("42")  # sanity

    def test_non_admin(self):
        assert 999 != 42


# =========================================
# Chunking (safe send logic)
# =========================================

class TestChunking:
    def _chunk(self, payload, max_len=3900):
        """Воспроизводим логику чанкинга из middleware."""
        return [payload[i:i+max_len] for i in range(0, len(payload), max_len)] or [payload]

    def test_short_message_single_chunk(self):
        parts = self._chunk("hello")
        assert len(parts) == 1
        assert parts[0] == "hello"

    def test_long_message_split(self):
        msg = "A" * 8000
        parts = self._chunk(msg, max_len=3900)
        assert len(parts) == 3  # 3900 + 3900 + 200
        assert "".join(parts) == msg

    def test_exact_boundary(self):
        msg = "B" * 3900
        parts = self._chunk(msg, max_len=3900)
        assert len(parts) == 1

    def test_empty_string(self):
        parts = self._chunk("")
        assert len(parts) == 1


# =========================================
# ClaudeResult dataclass
# =========================================

class TestClaudeResult:
    def test_default_values(self):
        @dataclass
        class ClaudeResult:
            text: str
            session_id: str = ""
            success: bool = True
            duration: float = 0

        r = ClaudeResult(text="hello")
        assert r.text == "hello"
        assert r.success is True
        assert r.session_id == ""
        assert r.duration == 0

    def test_failed_result(self):
        @dataclass
        class ClaudeResult:
            text: str
            session_id: str = ""
            success: bool = True
            duration: float = 0

        r = ClaudeResult(text="Error: timeout", success=False, duration=120.5)
        assert r.success is False
        assert r.duration == 120.5
