#!/usr/bin/env python3
"""
Патч для bot.py: оборачивает pipeline-вызов в try/except + добавляет logging.
Запуск: python3 fix-pipeline-middleware.py

Что делает:
- Добавляет `import logging` и `logging.basicConfig` в начало файла
- Оборачивает asyncio.to_thread(run_job_pipeline, ...) в try/except
- При ошибке: пишет traceback в bot.log, отправляет короткое сообщение пользователю
- Бот НЕ падает ни при каком исключении в pipeline
"""
from pathlib import Path

bot_path = Path("bot.py")
src = bot_path.read_text(encoding="utf-8")

# --- 1. Добавить import logging + basicConfig если нет ---
if "import logging" not in src:
    src = src.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\nimport logging\n"
    )

if "logging.basicConfig" not in src:
    src = src.replace(
        'TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")\n',
        'TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")\n'
        'logging.basicConfig(filename="bot.log", level=logging.INFO, '
        'format="%(asctime)s %(levelname)s %(message)s")\n'
    )

# --- 2. Заменить незащищённый блок pipeline на защищённый ---

OLD_BLOCK = """\
        result = await asyncio.to_thread(run_job_pipeline, event.chat.id, text)

        final_text = (result.get("final_answer") or "").strip()
        job_id = result.get("job_id") or "UNKNOWN"

        # Safe send: plain text, chunked
        payload = (final_text + f"\\n\\njob: {job_id}").strip()
        max_len = 3900
        parts = [payload[i:i+max_len] for i in range(0, len(payload), max_len)] or ["job: " + job_id]
        for part in parts:
            await event.answer(part)

        # Stop propagation: do NOT call next handler
        return"""

NEW_BLOCK = """\
        try:
            result = await asyncio.to_thread(run_job_pipeline, event.chat.id, text)
            final_text = (result.get("final_answer") or "").strip()
            job_id = result.get("job_id") or "UNKNOWN"
        except Exception as e:
            logging.exception("PIPELINE_ERROR in run_job_pipeline")
            job_id = "UNKNOWN"
            final_text = f"Ошибка обработки: {e}"

        # Guard against empty messages — NEVER send empty text to Telegram
        if not final_text:
            final_text = "Не удалось сформировать ответ. Попробуйте переформулировать запрос."

        # Safe send: plain text, chunked
        payload = (final_text + f"\\n\\njob: {job_id}").strip()
        max_len = 3900
        parts = [payload[i:i+max_len] for i in range(0, len(payload), max_len)] or [payload]
        for part in parts:
            if not part.strip():
                continue
            try:
                await event.answer(part)
            except Exception as e:
                logging.exception("SEND_ERROR in PipelineMiddleware")

        # Stop propagation: do NOT call next handler
        return"""

if OLD_BLOCK not in src:
    print("ERROR: не нашёл блок для замены. bot.py уже пропатчен или изменён.")
    raise SystemExit(1)

src = src.replace(OLD_BLOCK, NEW_BLOCK, 1)

bot_path.write_text(src, encoding="utf-8")
print("OK: bot.py пропатчен")
