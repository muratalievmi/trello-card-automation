#!/usr/bin/env python3
"""
fix-bot-direct.py — прямые исправления bot.py (без поиска блоков).

Баги:
1. is_orchestrator_enabled() без chat_id → middleware НИКОГДА не работает
2. Duplicate import logging
3. Duplicate logging.basicConfig
4. await event.answer(part) без try/except → краш при пустом сообщении
5. Нет защиты от пустых сообщений

Запуск: python3 fix-bot-direct.py
"""
from pathlib import Path
import re

bot_path = Path("bot.py")
if not bot_path.exists():
    # Try common server path
    bot_path = Path("/home/ec2-user/ai-assistant/bot.py")
if not bot_path.exists():
    print("ERROR: bot.py не найден")
    raise SystemExit(1)

src = bot_path.read_text(encoding="utf-8")
original = src
changes = []

# --- Fix 1: is_orchestrator_enabled() → is_orchestrator_enabled(event.chat.id) ---
# This is THE root cause of empty messages — middleware never activates
old = "enabled = is_orchestrator_enabled()"
new = "enabled = is_orchestrator_enabled(event.chat.id)"
if old in src and new not in src:
    src = src.replace(old, new, 1)
    changes.append("Fix 1: is_orchestrator_enabled() → is_orchestrator_enabled(event.chat.id)")

# --- Fix 2: Remove duplicate `import logging` ---
if src.count("import logging\n") > 1:
    # Remove second occurrence
    first_pos = src.index("import logging\n")
    second_pos = src.index("import logging\n", first_pos + 1)
    src = src[:second_pos] + src[second_pos + len("import logging\n"):]
    changes.append("Fix 2: removed duplicate 'import logging'")

# --- Fix 3: Remove duplicate `logging.basicConfig(...)` ---
bc_pattern = 'logging.basicConfig(filename="bot.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")\n'
if src.count(bc_pattern) > 1:
    first_pos = src.index(bc_pattern)
    second_pos = src.index(bc_pattern, first_pos + 1)
    src = src[:second_pos] + src[second_pos + len(bc_pattern):]
    changes.append("Fix 3: removed duplicate logging.basicConfig")

# --- Fix 4: Wrap event.answer(part) in pipeline middleware with try/except + empty guard ---
old_send = """        for part in parts:
            await event.answer(part)"""
new_send = """        for part in parts:
            if not part.strip():
                continue
            try:
                await event.answer(part)
            except Exception as e:
                logging.exception("SEND_ERROR in PipelineMiddleware")"""
if old_send in src:
    src = src.replace(old_send, new_send, 1)
    changes.append("Fix 4: wrapped event.answer in try/except + skip empty chunks")

# --- Fix 5: Guard against empty final_text in pipeline middleware ---
old_guard = """        # Safe send: plain text, chunked
        payload = (final_text"""
new_guard = """        # Guard against empty messages
        if not final_text:
            final_text = "Не удалось сформировать ответ. Попробуйте переформулировать запрос."

        # Safe send: plain text, chunked
        payload = (final_text"""
if "Guard against empty messages" not in src and old_guard in src:
    src = src.replace(old_guard, new_guard, 1)
    changes.append("Fix 5: added empty message guard before send")

# --- Fix 6: Guard empty response in _route_and_send ---
old_route = """    # 5. Ответ с badge роли
    resp = result.text"""
new_route = """    # 5. Ответ с badge роли
    resp = result.text
    if not resp or not resp.strip():
        resp = "(Claude не вернул ответ. Попробуйте ещё раз.)" """
if "(Claude не вернул ответ" not in src and old_route in src:
    src = src.replace(old_route, new_route, 1)
    changes.append("Fix 6: guard empty response in _route_and_send")

# --- Write ---
if src == original:
    print("bot.py уже исправлен или структура не совпадает.")
    raise SystemExit(0)

# Backup
backup = bot_path.with_suffix(".py.bak")
backup.write_text(original, encoding="utf-8")
print(f"Бэкап: {backup}")

bot_path.write_text(src, encoding="utf-8")
print(f"OK: bot.py исправлен ({len(changes)} фиксов)")
for c in changes:
    print(f"  ✓ {c}")
