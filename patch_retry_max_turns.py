#!/usr/bin/env python3
"""
Патч для job_pipeline.py — добавляет --max-turns и retry для оркестратора.

Запуск на сервере:
  cd /home/ec2-user/ai-assistant
  python3 patch_retry_max_turns.py

Создаёт бэкап job_pipeline.py.bak перед изменениями.
"""
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "job_pipeline.py"

def patch():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found"); sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")
    backup = TARGET.with_suffix(".py.bak")
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")

    patches = [
        # 1. Add max_turns to RoleCfg
        (
            "    timeout_sec: int\n",
            "    timeout_sec: int\n    max_turns: int = 10      # Claude CLI --max-turns (agentic rounds)\n",
        ),
        # 2. Orchestrator max_turns=15
        (
            '            timeout_sec=t["orchestrator"],\n        ),\n        "researcher"',
            '            timeout_sec=t["orchestrator"],\n            max_turns=15,\n        ),\n        "researcher"',
        ),
        # 3. orchestrator_finalize max_turns=10
        (
            '            timeout_sec=t["orchestrator"],\n        ),\n    }\n\n\nROLE_ALIASES',
            '            timeout_sec=t["orchestrator"],\n            max_turns=10,\n        ),\n    }\n\n\nROLE_ALIASES',
        ),
        # 4. Add --max-turns to CLI call
        (
            '        "--model", role.model,\n        "--allowedTools"',
            '        "--model", role.model,\n        "--max-turns", str(role.max_turns),\n        "--allowedTools"',
        ),
        # 5. Replace orchestrator step with retry logic
        (
            '        # --- orchestrator step ---\n'
            '        orch = roles["orchestrator"]\n'
            '        orch_sid = str(uuid.uuid4())\n'
            '        r = _claude_call(orch, _prompt_orchestrator(job_id), orch_sid)\n'
            '\n'
            '        _append_worklog(job_dir, {\n'
            '            "ts": time.time(),\n'
            '            "job_id": job_id,\n'
            '            "task_id": "ORCH_UNDERSTAND_PLAN",\n'
            '            "role": orch.key,\n'
            '            "model": orch.model,\n'
            '            "action": "claude_call",\n'
            '            "ok": (r.get("exit_code") == 0),\n'
            '            "duration_sec": r.get("duration_sec"),\n'
            '        })\n'
            '\n'
            '        if r.get("exit_code") != 0:\n'
            '            msg = f"Ошибка оркестратора: {r.get(\'stderr\') or r.get(\'result\') or \'неизвестная ошибка\'}"\n'
            '            _write_text(job_dir / "7_done.md", msg + "\\n")\n'
            '            return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_FAIL"]}\n'
            '\n'
            '        # Validate orchestrator actually wrote required files\n'
            '        orch_err = _verify_files_written(job_dir, ["1_understanding.md", "4_orchestrator_plan.json"])\n'
            '        if orch_err:\n'
            '            # Orchestrator returned exit_code 0 but didn\'t write files — this is the\n'
            '            # root cause of empty bot messages. Return Claude\'s raw result as fallback.\n'
            '            claude_text = (r.get("result") or "").strip()\n'
            '            if claude_text:\n'
            '                msg = claude_text\n'
            '            else:\n'
            '                msg = f"Оркестратор не создал план. {orch_err}"\n'
            '            _write_text(job_dir / "7_done.md", msg + "\\n")\n'
            '            _append_worklog(job_dir, {\n'
            '                "ts": time.time(), "job_id": job_id, "task_id": "ORCH_NO_FILES",\n'
            '                "role": "system", "action": "orch_files_missing", "error": orch_err,\n'
            '                "claude_result": (r.get("result") or "")[:500],\n'
            '                "claude_stderr": (r.get("stderr") or "")[:500],\n'
            '                "exit_code": r.get("exit_code"),\n'
            '                "num_turns": r.get("num_turns"),\n'
            '            })\n'
            '            return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_NO_FILES"]}',
            # REPLACEMENT:
            '        # --- orchestrator step (with retry) ---\n'
            '        orch = roles["orchestrator"]\n'
            '        orch_sid = str(uuid.uuid4())\n'
            '        orch_prompt = _prompt_orchestrator(job_id)\n'
            '\n'
            '        ORCH_MAX_ATTEMPTS = 2\n'
            '        orch_ok = False\n'
            '\n'
            '        for attempt in range(1, ORCH_MAX_ATTEMPTS + 1):\n'
            '            r = _claude_call(orch, orch_prompt, orch_sid)\n'
            '\n'
            '            _append_worklog(job_dir, {\n'
            '                "ts": time.time(),\n'
            '                "job_id": job_id,\n'
            '                "task_id": "ORCH_UNDERSTAND_PLAN",\n'
            '                "role": orch.key,\n'
            '                "model": orch.model,\n'
            '                "action": "claude_call",\n'
            '                "ok": (r.get("exit_code") == 0),\n'
            '                "duration_sec": r.get("duration_sec"),\n'
            '                "attempt": attempt,\n'
            '                "num_turns": r.get("num_turns"),\n'
            '                "raw_stdout_len": len(r.get("result") or ""),\n'
            '                "raw_stderr_len": len(r.get("stderr") or ""),\n'
            '            })\n'
            '\n'
            '            if r.get("exit_code") != 0:\n'
            '                if attempt < ORCH_MAX_ATTEMPTS:\n'
            '                    _append_worklog(job_dir, {\n'
            '                        "ts": time.time(), "job_id": job_id, "task_id": "ORCH_RETRY",\n'
            '                        "role": "system", "action": "retry_after_fail",\n'
            '                        "attempt": attempt, "error": r.get("stderr", "")[:500],\n'
            '                    })\n'
            '                    time.sleep(3)\n'
            '                    continue\n'
            '                msg = f"Ошибка оркестратора: {r.get(\'stderr\') or r.get(\'result\') or \'неизвестная ошибка\'}"\n'
            '                _write_text(job_dir / "7_done.md", msg + "\\n")\n'
            '                return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_FAIL"]}\n'
            '\n'
            '            # Validate orchestrator actually wrote required files\n'
            '            orch_err = _verify_files_written(job_dir, ["1_understanding.md", "4_orchestrator_plan.json"])\n'
            '            if orch_err:\n'
            '                if attempt < ORCH_MAX_ATTEMPTS:\n'
            '                    _append_worklog(job_dir, {\n'
            '                        "ts": time.time(), "job_id": job_id, "task_id": "ORCH_RETRY",\n'
            '                        "role": "system", "action": "retry_after_empty_files",\n'
            '                        "attempt": attempt, "error": orch_err,\n'
            '                        "claude_result": (r.get("result") or "")[:500],\n'
            '                        "claude_stderr": (r.get("stderr") or "")[:500],\n'
            '                    })\n'
            '                    time.sleep(3)\n'
            '                    continue\n'
            '                # Final attempt also failed — return error\n'
            '                claude_text = (r.get("result") or "").strip()\n'
            '                if claude_text:\n'
            '                    msg = claude_text\n'
            '                else:\n'
            '                    msg = f"Оркестратор не создал план. {orch_err}"\n'
            '                _write_text(job_dir / "7_done.md", msg + "\\n")\n'
            '                _append_worklog(job_dir, {\n'
            '                    "ts": time.time(), "job_id": job_id, "task_id": "ORCH_NO_FILES",\n'
            '                    "role": "system", "action": "orch_files_missing", "error": orch_err,\n'
            '                    "claude_result": (r.get("result") or "")[:500],\n'
            '                    "claude_stderr": (r.get("stderr") or "")[:500],\n'
            '                    "exit_code": r.get("exit_code"),\n'
            '                    "num_turns": r.get("num_turns"),\n'
            '                })\n'
            '                return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_NO_FILES"]}\n'
            '\n'
            '            # Both files written successfully\n'
            '            orch_ok = True\n'
            '            break\n'
            '\n'
            '        assert orch_ok, "orchestrator loop ended without success or return"',
        ),
    ]

    applied = 0
    for old, new in patches:
        if old in src:
            src = src.replace(old, new, 1)
            applied += 1
        else:
            # Check if already patched
            if new in src:
                print(f"  SKIP (already applied): {old[:60]}...")
            else:
                print(f"  WARN: pattern not found: {old[:60]}...")

    TARGET.write_text(src, encoding="utf-8")
    print(f"\nApplied {applied} patches to {TARGET}")
    print("Done! Restart the bot to apply changes.")


if __name__ == "__main__":
    patch()
