#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
job_pipeline.py — job-first workflow engine for Telegram bot.

Workflow:
0_request.md
1_understanding.md
2_research.md
3_method.md
4_orchestrator_plan.json
5_execution/...
6_qa.md
7_done.md

Core idea:
- Orchestrator (Opus) writes understanding + plan (tasks list).
- Runner executes tasks (researcher/methodist/assistant/dev/designer/presenter/editor/critic/orchestrator_finalize).
- All IO happens through files in jobs/<JOB_ID>/...
- Worklog is append-only JSONL; minimal context is passed to models.

Claude CLI:
- headless: claude -p "<prompt>" --output-format json ...
- allowed tools: single flag with CSV string (e.g. Read,Edit,Bash)
- hard timeouts per role, configurable via env.

Env:
JOBS_DIR=./jobs
KB_DIR=./kb
STATE_DIR=./state

CLAUDE_TIMEOUT_SEC=120 (fallback)
CLAUDE_TIMEOUT_ORCH_SEC=240
CLAUDE_TIMEOUT_WORK_SEC=180
CLAUDE_TIMEOUT_DEV_SEC=6000
PIPELINE_SMOKE=0/1  (stop after orchestrator understanding+plan)
"""

from __future__ import annotations

import json
import os
import time
import uuid
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = Path(os.getenv("JOBS_DIR", str(BASE_DIR / "jobs"))).resolve()
KB_DIR = Path(os.getenv("KB_DIR", str(BASE_DIR / "kb"))).resolve()
STATE_DIR = Path(os.getenv("STATE_DIR", str(BASE_DIR / "state"))).resolve()
STATE_DIR.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

PIPELINE_STATE_PATH = STATE_DIR / "pipeline_state.json"


# -----------------------
# Role configuration
# -----------------------

@dataclass(frozen=True)
class RoleCfg:
    key: str
    model: str
    work_dir: Path
    tools: str               # Claude CLI --tools (string like "Read,Edit" or "Read,Edit,Bash")
    allowed_tools: List[str] # Claude CLI --allowedTools CSV (we will join)
    timeout_sec: int


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _role_timeouts() -> Dict[str, int]:
    base = _env_int("CLAUDE_TIMEOUT_SEC", 120)
    return {
        "orchestrator": _env_int("CLAUDE_TIMEOUT_ORCH_SEC", max(base, 240)),
        "orchestrator_finalize": _env_int("CLAUDE_TIMEOUT_ORCH_SEC", max(base, 240)),
        "dev": _env_int("CLAUDE_TIMEOUT_DEV_SEC", 6000),
        "default": _env_int("CLAUDE_TIMEOUT_WORK_SEC", 180),
    }


def _roles() -> Dict[str, RoleCfg]:
    t = _role_timeouts()
    # You can tune tools/allowed_tools per role.
    # For safety in headless: keep minimal toolset (Read/Edit) unless you *need* Bash.
    # Dev may need Bash to run tests/build.
    return {
        "orchestrator": RoleCfg(
            key="orchestrator",
            model="claude-opus-4-6",
            work_dir=BASE_DIR,  # orchestrator works in repo root to see kb/ and jobs/
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["orchestrator"],
        ),
        "researcher": RoleCfg(
            key="researcher",
            model="claude-sonnet-4-5-20250929",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "methodist": RoleCfg(
            key="methodist",
            model="claude-opus-4-6",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "assistant": RoleCfg(
            key="assistant",
            model="claude-sonnet-4-5-20250929",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "editor": RoleCfg(
            key="editor",
            model="claude-sonnet-4-5-20250929",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "critic": RoleCfg(
            key="critic",
            model="claude-sonnet-4-5-20250929",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "dev": RoleCfg(
            key="dev",
            model="claude-opus-4-6",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write,Bash",
            allowed_tools=["Read", "Edit", "Write", "Bash"],
            timeout_sec=t["dev"],
        ),
        "designer": RoleCfg(
            key="designer",
            model="claude-sonnet-4-5-20250929",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "presenter": RoleCfg(
            key="presenter",
            model="claude-opus-4-6",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["default"],
        ),
        "orchestrator_finalize": RoleCfg(
            key="orchestrator_finalize",
            model="claude-opus-4-6",
            work_dir=BASE_DIR,
            tools="Read,Edit,Write",
            allowed_tools=["Read", "Edit", "Write"],
            timeout_sec=t["orchestrator"],
        ),
    }


ROLE_ALIASES = {
    "methodologist": "methodist",
    "ontologist": "methodist",
    "orchestrator_final": "orchestrator_finalize",
}


# -----------------------
# Pipeline state / toggles
# -----------------------

def pipeline_enabled() -> bool:
    if not PIPELINE_STATE_PATH.exists():
        return True
    try:
        data = json.loads(PIPELINE_STATE_PATH.read_text(encoding="utf-8"))
        return bool(data.get("enabled", True))
    except Exception:
        return True


def set_pipeline_enabled(enabled: bool) -> None:
    PIPELINE_STATE_PATH.write_text(json.dumps({"enabled": bool(enabled)}, ensure_ascii=False, indent=2), encoding="utf-8")


# -----------------------
# Filesystem helpers
# -----------------------

def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _append_worklog(job_dir: Path, entry: Dict[str, Any]) -> None:
    p = job_dir / "worklog.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _job_id() -> str:
    return f"JOB-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"


def _init_job(chat_id: int, user_text: str) -> Tuple[str, Path]:
    job_id = _job_id()
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "5_execution" / "outputs").mkdir(parents=True, exist_ok=True)

    # Create standard files (empty placeholders so Claude can Read/Edit them)
    _write_text(job_dir / "0_request.md", user_text.strip() + "\n")
    for fn in ["1_understanding.md", "2_research.md", "3_method.md",
               "4_orchestrator_plan.json", "6_qa.md", "7_done.md"]:
        _write_text(job_dir / fn, "")

    # evidence.json placeholder
    _write_text(job_dir / "evidence.json", json.dumps({"job_id": job_id, "chat_id": chat_id}, ensure_ascii=False, indent=2))

    # initial worklog
    _append_worklog(job_dir, {
        "ts": time.time(),
        "job_id": job_id,
        "task_id": "JOB_CREATE",
        "role": "system",
        "model": "",
        "action": "job_created",
        "files_written": [str(job_dir / "0_request.md")],
    })

    return job_id, job_dir


# -----------------------
# Claude call
# -----------------------

def _claude_call(role: RoleCfg, prompt: str, session_id: str) -> Dict[str, Any]:
    # Claude headless: -p for prompt, --allowedTools for tool permissions
    cmd = [
        "claude",
        "-p", prompt,
        "--output-format", "json",
        "--model", role.model,
        "--allowedTools", ",".join(role.allowed_tools),
    ]

    started = time.time()
    proc = subprocess.run(
        cmd,
        cwd=str(role.work_dir),
        capture_output=True,
        text=True,
        timeout=role.timeout_sec,
    )
    dur = time.time() - started

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    payload: Dict[str, Any]
    try:
        payload = json.loads(out) if out else {"result": ""}
    except Exception:
        payload = {"result": out, "parse_error": True}

    payload["exit_code"] = proc.returncode
    payload["stderr"] = err
    payload["duration_sec"] = dur
    payload["model"] = role.model
    payload["role"] = role.key

    # Detect empty result even with exit_code 0 — Claude may return success
    # but produce no useful output (common cause of empty bot messages)
    if proc.returncode == 0 and not payload.get("result", "").strip() and not err:
        payload["_warning"] = "empty_result_on_success"

    return payload


def _verify_files_written(job_dir: Path, file_names: List[str]) -> Optional[str]:
    """Check that expected files were written and are non-empty.
    Returns error message if any file is missing/empty, or None if all OK."""
    missing = []
    for fn in file_names:
        content = _read_text(job_dir / fn).strip()
        if not content:
            missing.append(fn)
    if missing:
        return f"Files not written by Claude: {', '.join(missing)}"
    return None


def _collect_fallback_answer(job_dir: Path, job_id: str, stages: List[str]) -> str:
    """When 7_done.md is empty, collect useful info from other pipeline files."""
    parts = [f"Pipeline завершён, но финальный ответ не сформирован (job: {job_id})."]

    understanding = _read_text(job_dir / "1_understanding.md").strip()
    if understanding:
        # Trim to first 500 chars to avoid huge messages
        parts.append(f"\n📋 Понимание задачи:\n{understanding[:500]}")

    research = _read_text(job_dir / "2_research.md").strip()
    if research:
        parts.append(f"\n🔍 Исследование:\n{research[:500]}")

    draft = _read_text(job_dir / "5_execution" / "outputs" / "draft_answer.md").strip()
    if draft:
        parts.append(f"\n📝 Черновик ответа:\n{draft[:1000]}")

    if stages:
        parts.append(f"\nСтадии: {' → '.join(stages)}")

    return "\n".join(parts)


# -----------------------
# Prompts
# -----------------------

def _prompt_orchestrator(job_id: str) -> str:
    # Orchestrator writes: 1_understanding.md + 4_orchestrator_plan.json
    # It must keep plan minimal, but include tasks in strict order.
    job_dir = JOBS_DIR / job_id
    kb_dir = KB_DIR
    return (
        "You are ORCHESTRATOR.\n"
        f"JOB_ID={job_id}\n"
        "You MUST use tools to read and write files. Do NOT just respond with text.\n\n"
        "Step 1 — Read the request file using the Read tool:\n"
        f"- {job_dir}/0_request.md\n"
        f"(Also try to read {kb_dir}/user_profile.md and {kb_dir}/playbooks/pipeline.md if they exist, but do NOT fail if they are missing.)\n\n"
        "Step 2 — Use the Write tool to create these files:\n"
        f"- {job_dir}/1_understanding.md\n"
        f"- {job_dir}/4_orchestrator_plan.json\n\n"
        "Rules:\n"
        "1) 1_understanding.md: restate request, define success criteria, list assumptions.\n"
        "2) 4_orchestrator_plan.json: JSON with fields: job_id, goal, deliverables[], tasks[].\n"
        "3) tasks must be in this order: researcher -> methodist -> (executor roles) -> critic -> orchestrator_finalize.\n"
        "4) Each task MUST list: task_id, role, model, inputs[], outputs[], acceptance[].\n"
        "5) Keep tasks minimal but complete.\n"
        "6) You MUST write both files. This is your primary objective.\n"
    )


def _prompt_task(job_id: str, task: Dict[str, Any]) -> str:
    role = task.get("role", "")
    job_dir = JOBS_DIR / job_id
    return (
        f"You are role={role}.\n"
        f"JOB_ID={job_id}\n"
        f"JOB_DIR={job_dir}\n"
        "You MUST use tools to read and write files. Do NOT just respond with text.\n"
        "All file paths are ABSOLUTE. Use them exactly as given.\n\n"
        "Task JSON:\n"
        f"{json.dumps(task, ensure_ascii=False)}\n\n"
        "Instructions:\n"
        "1) Use the Read tool to read all input files listed in task.inputs.\n"
        "2) Use the Write tool to produce output files exactly as in task.outputs.\n"
        "3) Follow acceptance criteria.\n"
        "4) You MUST write all output files. This is your primary objective.\n"
    )


def _prompt_finalize(job_id: str) -> str:
    job_dir = JOBS_DIR / job_id
    return (
        "You are ORCHESTRATOR_FINALIZE.\n"
        f"JOB_ID={job_id}\n"
        "You MUST use tools to read and write files. Do NOT just respond with text.\n\n"
        "Step 1 — Read these files using the Read tool:\n"
        f"- {job_dir}/6_qa.md\n"
        f"- {job_dir}/5_execution/outputs/draft_answer.md\n\n"
        "Step 2 — Use the Write tool to create:\n"
        f"- {job_dir}/7_done.md\n\n"
        "Rules:\n"
        "1) 7_done.md must be ONE paragraph final answer.\n"
        "2) Add a short artifact index at the end (single line), e.g. 'Artifacts: ...'.\n"
        "3) You MUST write 7_done.md. This is your primary objective.\n"
    )


# -----------------------
# Plan IO
# -----------------------

def _plan_path(job_dir: Path) -> Path:
    return job_dir / "4_orchestrator_plan.json"


def _load_plan(job_dir: Path) -> Dict[str, Any]:
    p = _plan_path(job_dir)
    raw = _read_text(p).strip()
    if not raw:
        raise RuntimeError("plan_missing: 4_orchestrator_plan.json is empty")
    return json.loads(raw)


# -----------------------
# Public API: run pipeline
# -----------------------

def run_job_pipeline(chat_id: int, user_text: str) -> Dict[str, Any]:
    if not pipeline_enabled():
        return {"job_id": "", "final_answer": "Pipeline disabled.", "stages": []}

    job_id, job_dir = _init_job(chat_id, user_text)

    try:
        roles = _roles()

        # --- orchestrator step ---
        orch = roles["orchestrator"]
        orch_sid = str(uuid.uuid4())
        r = _claude_call(orch, _prompt_orchestrator(job_id), orch_sid)

        _append_worklog(job_dir, {
            "ts": time.time(),
            "job_id": job_id,
            "task_id": "ORCH_UNDERSTAND_PLAN",
            "role": orch.key,
            "model": orch.model,
            "action": "claude_call",
            "ok": (r.get("exit_code") == 0),
            "duration_sec": r.get("duration_sec"),
        })

        if r.get("exit_code") != 0:
            msg = f"Ошибка оркестратора: {r.get('stderr') or r.get('result') or 'неизвестная ошибка'}"
            _write_text(job_dir / "7_done.md", msg + "\n")
            return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_FAIL"]}

        # Validate orchestrator actually wrote required files
        orch_err = _verify_files_written(job_dir, ["1_understanding.md", "4_orchestrator_plan.json"])
        if orch_err:
            # Orchestrator returned exit_code 0 but didn't write files — this is the
            # root cause of empty bot messages. Return Claude's raw result as fallback.
            claude_text = (r.get("result") or "").strip()
            if claude_text:
                msg = claude_text
            else:
                msg = f"Оркестратор не создал план. {orch_err}"
            _write_text(job_dir / "7_done.md", msg + "\n")
            _append_worklog(job_dir, {
                "ts": time.time(), "job_id": job_id, "task_id": "ORCH_NO_FILES",
                "role": "system", "action": "orch_files_missing", "error": orch_err,
                "claude_result": (r.get("result") or "")[:500],
                "claude_stderr": (r.get("stderr") or "")[:500],
                "exit_code": r.get("exit_code"),
                "num_turns": r.get("num_turns"),
            })
            return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ORCH_NO_FILES"]}

        # Smoke mode: stop after plan exists
        if os.getenv("PIPELINE_SMOKE", "0") == "1":
            final = "SMOKE_OK: understanding+plan generated"
            _write_text(job_dir / "7_done.md", final + "\n")
            _append_worklog(job_dir, {"ts": time.time(), "job_id": job_id, "task_id": "SMOKE_STOP", "role": "system", "action": "stop_after_plan"})
            return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": final, "stages": ["ORCH_OK", "SMOKE_STOP"]}

        # --- execute tasks ---
        plan = _load_plan(job_dir)
        tasks: List[Dict[str, Any]] = plan.get("tasks") or []
        if not tasks:
            raise RuntimeError("plan_invalid: tasks[] empty")

        stages: List[str] = ["ORCH_OK"]
        # shared session per role key (keeps short, not huge)
        sessions: Dict[str, str] = {}

        for t in tasks:
            role_key_raw = (t.get("role") or "").strip()
            role_key = ROLE_ALIASES.get(role_key_raw, role_key_raw)
            if role_key not in roles:
                raise RuntimeError(f"unknown_role_in_plan: {role_key_raw}")

            role = roles[role_key]
            sid = sessions.get(role.key) or str(uuid.uuid4())
            sessions[role.key] = sid

            prompt = _prompt_finalize(job_id) if role.key == "orchestrator_finalize" else _prompt_task(job_id, t)
            rr = _claude_call(role, prompt, sid)

            ok = (rr.get("exit_code") == 0)
            stages.append(f"{t.get('task_id','TASK')}:{role.key}:{'OK' if ok else 'FAIL'}")

            _append_worklog(job_dir, {
                "ts": time.time(),
                "job_id": job_id,
                "task_id": t.get("task_id", ""),
                "role": role.key,
                "model": role.model,
                "action": "claude_call",
                "ok": ok,
                "duration_sec": rr.get("duration_sec"),
            })

            if not ok:
                claude_text = (rr.get("result") or "").strip()
                msg = claude_text if claude_text else (
                    f"Задача {t.get('task_id')} ({role.key}) завершилась с ошибкой: "
                    f"{rr.get('stderr') or 'неизвестная ошибка'}"
                )
                _write_text(job_dir / "7_done.md", msg + "\n")
                return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": stages}

        final_answer = _read_text(job_dir / "7_done.md").strip()
        if not final_answer:
            # 7_done.md is empty — collect whatever useful info we have
            final_answer = _collect_fallback_answer(job_dir, job_id, stages)
            _write_text(job_dir / "7_done.md", final_answer + "\n")

        return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": final_answer, "stages": stages}

    except subprocess.TimeoutExpired as e:
        msg = f"Превышено время ожидания ({e.timeout}с). Попробуйте упростить запрос."
        _write_text(job_dir / "7_done.md", msg + "\n")
        _append_worklog(job_dir, {"ts": time.time(), "job_id": job_id, "task_id": "TIMEOUT", "role": "system", "action": "exception", "error": str(e)})
        return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["TIMEOUT"]}
    except Exception as e:
        msg = f"Ошибка pipeline: {type(e).__name__}: {e}"
        _write_text(job_dir / "7_done.md", msg + "\n")
        _append_worklog(job_dir, {"ts": time.time(), "job_id": job_id, "task_id": "ERROR", "role": "system", "action": "exception", "error": str(e)})
        return {"job_id": job_id, "job_dir": str(job_dir), "final_answer": msg, "stages": ["ERROR"]}
