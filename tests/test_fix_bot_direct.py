"""
Тесты для fix-bot-direct.py — проверяем что патч-скрипт корректно исправляет bot.py.
"""
import pytest
from pathlib import Path


BUGGY_BOT = '''\
#!/usr/bin/env python3
from pathlib import Path
import logging
import logging
from aiogram import BaseMiddleware

class PipelineMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        text = getattr(event, "text", None)
        if not text:
            return await handler(event, data)
        text = text.strip()
        if text.startswith("/") or text.startswith("@"):
            return await handler(event, data)
        try:
            enabled = is_orchestrator_enabled()
        except Exception:
            enabled = False
        if not enabled:
            return await handler(event, data)

        final_text = "test"
        job_id = "JOB-1"

        # Safe send: plain text, chunked
        payload = (final_text + f"\\n\\njob: {job_id}").strip()
        max_len = 3900
        parts = [payload[i:i+max_len] for i in range(0, len(payload), max_len)] or ["job: " + job_id]
        for part in parts:
            await event.answer(part)
        return

TELEGRAM_BOT_TOKEN = ""
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

async def _route_and_send(chat_id, text, source_msg, prefix=""):
    result = None
    # 5. Ответ с badge роли
    resp = result.text
    pass
'''


class TestFixBotDirect:
    def test_fix_chat_id_bug(self, tmp_path):
        """is_orchestrator_enabled() → is_orchestrator_enabled(event.chat.id)"""
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path),
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        fixed = bot_py.read_text()
        assert "is_orchestrator_enabled(event.chat.id)" in fixed
        assert "is_orchestrator_enabled()" not in fixed

    def test_removes_duplicate_imports(self, tmp_path):
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        fixed = bot_py.read_text()
        assert fixed.count("import logging\n") == 1

    def test_removes_duplicate_basicconfig(self, tmp_path):
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        fixed = bot_py.read_text()
        assert fixed.count("logging.basicConfig") == 1

    def test_wraps_event_answer_in_try_except(self, tmp_path):
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        fixed = bot_py.read_text()
        assert "SEND_ERROR in PipelineMiddleware" in fixed
        assert "if not part.strip():" in fixed

    def test_adds_empty_message_guard(self, tmp_path):
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        fixed = bot_py.read_text()
        assert "Guard against empty messages" in fixed

    def test_adds_empty_response_guard_in_route(self, tmp_path):
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        fixed = bot_py.read_text()
        assert "Claude не вернул ответ" in fixed

    def test_creates_backup(self, tmp_path):
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        assert (tmp_path / "bot.py.bak").exists()
        assert (tmp_path / "bot.py.bak").read_text() == BUGGY_BOT

    def test_idempotent(self, tmp_path):
        """Повторный запуск не ломает файл."""
        bot_py = tmp_path / "bot.py"
        bot_py.write_text(BUGGY_BOT)

        import subprocess
        # First run
        subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        first_fixed = bot_py.read_text()

        # Second run
        result = subprocess.run(
            ["python3", str(Path(__file__).parent.parent / "fix-bot-direct.py")],
            cwd=str(tmp_path), capture_output=True, text=True,
        )
        second_fixed = bot_py.read_text()
        assert first_fixed == second_fixed
