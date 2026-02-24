#!/usr/bin/env python3
"""
Патч #2 — заменяет orchestrator step на retry-логику.
Ищет блок между двумя якорями, заменяет целиком.

Запуск:
  python3 patch2_retry.py
"""
import shutil
import sys
from pathlib import Path

TARGET = Path(__file__).resolve().parent / "job_pipeline.py"

# Anchor: line that starts the block we want to replace
START_ANCHOR = "        # --- orchestrator step ---\n"
# Anchor: line that ends the block (this line is NOT replaced, kept as-is)
END_ANCHOR = "        # Smoke mode: stop after plan exists\n"

REPLACEMENT = '''\
        # --- orchestrator step (with retry) ---
        orch = roles["orchestrator"]
        orch_sid = str(uuid.uuid4())
        orch_prompt = _prompt_orchestrator(job_id)

        ORCH_MAX_ATTEMPTS = 2
        orch_ok = False

        for attempt in range(1, ORCH_MAX_ATTEMPTS + 1):
            r = _claude_call(orch, orch_prompt, orch_sid)

            _append_worklog(job_dir, {
                "ts": time.time(),
                "job_id": job_id,
                "task_id": "ORCH_UNDERSTAND_PLAN",
                "role": orch.key,
                "model": orch.model,
                "action": "claude_call",
                "ok": (r.get("exit_code") == 0),
                "duration_sec": r.get("duration_sec"),
                "attempt": attempt,
                "num_turns": r.get("num_turns"),
                "raw_stdout_len": len(r.get("result") or ""),
                "raw_stderr_len": len(r.get("stderr") or ""),
            })

            if r.get("exit_code") != 0:
                if attempt < ORCH_MAX_ATTEMPTS:
                    _append_worklog(job_dir, {
                        "ts": time.time(), "job_id": job_id, "task_id": "ORCH_RETRY",
                        "role": "system", "action": "retry_after_fail",
                        "attempt": attempt, "error": r.get("stderr", "")[:500],
                    })
                    time.sleep(3)
                    continue
                msg = f"Ошибка оркестратора: {r.get('stderr') or r.get('result') or 'неизвестная ошибка'}"
                _write_text(job_dir / "7_done.md", msg + "\\n")
                return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_FAIL"]}

            # Validate orchestrator actually wrote required files
            orch_err = _verify_files_written(job_dir, ["1_understanding.md", "4_orchestrator_plan.json"])
            if orch_err:
                if attempt < ORCH_MAX_ATTEMPTS:
                    _append_worklog(job_dir, {
                        "ts": time.time(), "job_id": job_id, "task_id": "ORCH_RETRY",
                        "role": "system", "action": "retry_after_empty_files",
                        "attempt": attempt, "error": orch_err,
                        "claude_result": (r.get("result") or "")[:500],
                        "claude_stderr": (r.get("stderr") or "")[:500],
                    })
                    time.sleep(3)
                    continue
                # Final attempt also failed — return error
                claude_text = (r.get("result") or "").strip()
                if claude_text:
                    msg = claude_text
                else:
                    msg = f"Оркестратор не создал план. {orch_err}"
                _write_text(job_dir / "7_done.md", msg + "\\n")
                _append_worklog(job_dir, {
                    "ts": time.time(), "job_id": job_id, "task_id": "ORCH_NO_FILES",
                    "role": "system", "action": "orch_files_missing", "error": orch_err,
                    "claude_result": (r.get("result") or "")[:500],
                    "claude_stderr": (r.get("stderr") or "")[:500],
                    "exit_code": r.get("exit_code"),
                    "num_turns": r.get("num_turns"),
                })
                return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_NO_FILES"]}

            # Both files written successfully
            orch_ok = True
            break

        assert orch_ok, "orchestrator loop ended without success or return"

'''


def patch():
    if not TARGET.exists():
        print(f"ERROR: {TARGET} not found"); sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")

    # Check if already patched
    if "ORCH_MAX_ATTEMPTS" in src:
        print("Already patched (ORCH_MAX_ATTEMPTS found). Nothing to do.")
        return

    start_idx = src.find(START_ANCHOR)
    if start_idx == -1:
        print(f"ERROR: start anchor not found: {START_ANCHOR.strip()!r}")
        sys.exit(1)

    end_idx = src.find(END_ANCHOR, start_idx)
    if end_idx == -1:
        print(f"ERROR: end anchor not found: {END_ANCHOR.strip()!r}")
        sys.exit(1)

    # Backup
    backup = TARGET.with_suffix(".py.bak2")
    shutil.copy2(TARGET, backup)
    print(f"Backup: {backup}")

    # Replace everything from START_ANCHOR to (but not including) END_ANCHOR
    new_src = src[:start_idx] + REPLACEMENT + src[end_idx:]
    TARGET.write_text(new_src, encoding="utf-8")

    print(f"Replaced orchestrator block ({end_idx - start_idx} chars) with retry logic.")
    print("Done! Restart the bot to apply.")


if __name__ == "__main__":
    patch()
