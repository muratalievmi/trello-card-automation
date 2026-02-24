"""
Тесты для job_pipeline.py — pipeline, роли, claude_call, файловая система.
"""
import json
import os
import subprocess
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import job_pipeline as jp


@pytest.fixture(autouse=True)
def tmp_dirs(tmp_path, monkeypatch):
    """Перенаправляем JOBS_DIR, KB_DIR, STATE_DIR во временные директории."""
    jobs = tmp_path / "jobs"
    kb = tmp_path / "kb"
    state = tmp_path / "state"
    jobs.mkdir()
    kb.mkdir()
    state.mkdir()
    monkeypatch.setattr(jp, "JOBS_DIR", jobs)
    monkeypatch.setattr(jp, "KB_DIR", kb)
    monkeypatch.setattr(jp, "STATE_DIR", state)
    monkeypatch.setattr(jp, "PIPELINE_STATE_PATH", state / "pipeline_state.json")
    return {"jobs": jobs, "kb": kb, "state": state}


# =========================================
# Конфигурация ролей pipeline
# =========================================

class TestPipelineRoles:
    def test_all_pipeline_roles_defined(self):
        r = jp._roles()
        expected = {
            "orchestrator", "researcher", "methodist", "assistant",
            "editor", "critic", "dev", "designer", "presenter",
            "orchestrator_finalize",
        }
        assert set(r.keys()) == expected

    def test_orchestrator_uses_opus(self):
        r = jp._roles()
        assert "opus" in r["orchestrator"].model

    def test_researcher_uses_sonnet(self):
        r = jp._roles()
        assert "sonnet" in r["researcher"].model

    def test_dev_has_bash_tool(self):
        r = jp._roles()
        assert "Bash" in r["dev"].tools
        assert "Bash" in r["dev"].allowed_tools

    def test_researcher_no_bash(self):
        r = jp._roles()
        assert "Bash" not in r["researcher"].tools
        assert "Bash" not in r["researcher"].allowed_tools

    def test_all_roles_have_read_edit(self):
        """Все роли должны иметь минимум Read и Edit."""
        for key, cfg in jp._roles().items():
            assert "Read" in cfg.allowed_tools, f"{key}: missing Read"
            assert "Edit" in cfg.allowed_tools, f"{key}: missing Edit"

    def test_role_aliases(self):
        assert jp.ROLE_ALIASES["methodologist"] == "methodist"
        assert jp.ROLE_ALIASES["ontologist"] == "methodist"
        assert jp.ROLE_ALIASES["orchestrator_final"] == "orchestrator_finalize"

    def test_timeouts_from_env(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_TIMEOUT_ORCH_SEC", "999")
        monkeypatch.setenv("CLAUDE_TIMEOUT_DEV_SEC", "5000")
        monkeypatch.setenv("CLAUDE_TIMEOUT_WORK_SEC", "300")
        r = jp._roles()
        assert r["orchestrator"].timeout_sec == 999
        assert r["dev"].timeout_sec == 5000
        assert r["researcher"].timeout_sec == 300

    def test_timeouts_defaults(self, monkeypatch):
        monkeypatch.delenv("CLAUDE_TIMEOUT_ORCH_SEC", raising=False)
        monkeypatch.delenv("CLAUDE_TIMEOUT_DEV_SEC", raising=False)
        monkeypatch.delenv("CLAUDE_TIMEOUT_WORK_SEC", raising=False)
        monkeypatch.delenv("CLAUDE_TIMEOUT_SEC", raising=False)
        r = jp._roles()
        assert r["orchestrator"].timeout_sec == 240
        assert r["dev"].timeout_sec == 6000
        assert r["researcher"].timeout_sec == 180


# =========================================
# Pipeline state (enabled/disabled)
# =========================================

class TestPipelineState:
    def test_enabled_by_default(self):
        assert jp.pipeline_enabled() is True

    def test_disable_pipeline(self):
        jp.set_pipeline_enabled(False)
        assert jp.pipeline_enabled() is False

    def test_enable_pipeline(self):
        jp.set_pipeline_enabled(False)
        jp.set_pipeline_enabled(True)
        assert jp.pipeline_enabled() is True

    def test_corrupted_state_file(self, tmp_dirs):
        (tmp_dirs["state"] / "pipeline_state.json").write_text("broken!")
        assert jp.pipeline_enabled() is True  # graceful fallback


# =========================================
# Job init (файловая система)
# =========================================

class TestJobInit:
    def test_init_creates_directory_structure(self, tmp_dirs):
        job_id, job_dir = jp._init_job(111, "test request")
        assert job_dir.exists()
        assert (job_dir / "0_request.md").exists()
        assert (job_dir / "1_understanding.md").exists()
        assert (job_dir / "4_orchestrator_plan.json").exists() is False  # not created by init
        assert (job_dir / "5_execution" / "outputs").is_dir()
        assert (job_dir / "evidence.json").exists()
        assert (job_dir / "worklog.jsonl").exists()

    def test_request_file_has_user_text(self, tmp_dirs):
        _, job_dir = jp._init_job(111, "  my request  ")
        content = (job_dir / "0_request.md").read_text()
        assert content.strip() == "my request"

    def test_evidence_has_job_id_and_chat_id(self, tmp_dirs):
        job_id, job_dir = jp._init_job(222, "req")
        evidence = json.loads((job_dir / "evidence.json").read_text())
        assert evidence["job_id"] == job_id
        assert evidence["chat_id"] == 222

    def test_job_id_format(self, tmp_dirs):
        job_id, _ = jp._init_job(111, "x")
        assert job_id.startswith("JOB-")
        parts = job_id.split("-")
        assert len(parts) >= 3

    def test_worklog_initial_entry(self, tmp_dirs):
        job_id, job_dir = jp._init_job(111, "x")
        lines = (job_dir / "worklog.jsonl").read_text().strip().split("\n")
        entry = json.loads(lines[0])
        assert entry["action"] == "job_created"
        assert entry["job_id"] == job_id

    def test_empty_placeholder_files(self, tmp_dirs):
        _, job_dir = jp._init_job(111, "x")
        for fn in ["1_understanding.md", "2_research.md", "3_method.md", "6_qa.md", "7_done.md"]:
            assert (job_dir / fn).read_text() == ""


# =========================================
# _claude_call (мокаем subprocess)
# =========================================

class TestClaudeCall:
    def _make_role(self):
        return jp.RoleCfg(
            key="test_role",
            model="claude-sonnet-4-5-20250929",
            work_dir=Path("/tmp"),
            tools="Read,Edit",
            allowed_tools=["Read", "Edit"],
            timeout_sec=60,
        )

    @patch("job_pipeline.subprocess.run")
    def test_successful_call(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"result": "hello"}),
            stderr="",
            returncode=0,
        )
        role = self._make_role()
        result = jp._claude_call(role, "test prompt", "session-1")
        assert result["result"] == "hello"
        assert result["exit_code"] == 0
        assert result["role"] == "test_role"
        assert "duration_sec" in result

    @patch("job_pipeline.subprocess.run")
    def test_failed_call(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="",
            stderr="some error",
            returncode=1,
        )
        role = self._make_role()
        result = jp._claude_call(role, "test", "s1")
        assert result["exit_code"] == 1
        assert result["stderr"] == "some error"

    @patch("job_pipeline.subprocess.run")
    def test_unparseable_json(self, mock_run):
        mock_run.return_value = MagicMock(
            stdout="not json at all",
            stderr="",
            returncode=0,
        )
        role = self._make_role()
        result = jp._claude_call(role, "test", "s1")
        assert result["parse_error"] is True
        assert result["result"] == "not json at all"

    @patch("job_pipeline.subprocess.run")
    def test_timeout_propagates(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=60)
        role = self._make_role()
        with pytest.raises(subprocess.TimeoutExpired):
            jp._claude_call(role, "test", "s1")

    @patch("job_pipeline.subprocess.run")
    def test_cli_arguments(self, mock_run):
        """Проверяем что CLI вызывается с правильными аргументами."""
        mock_run.return_value = MagicMock(stdout="{}", stderr="", returncode=0)
        role = self._make_role()
        jp._claude_call(role, "my prompt", "sid-123")
        args = mock_run.call_args
        cmd = args[0][0]
        assert cmd[0] == "claude"
        assert "-p" in cmd
        assert cmd[cmd.index("-p") + 1] == "my prompt"
        assert "--model" in cmd
        assert "--session-id" in cmd
        assert cmd[cmd.index("--session-id") + 1] == "sid-123"

    @patch("job_pipeline.subprocess.run")
    def test_empty_result_warning(self, mock_run):
        """exit_code=0 но пустой result → добавляется _warning."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"result": ""}),
            stderr="",
            returncode=0,
        )
        role = self._make_role()
        result = jp._claude_call(role, "test", "s1")
        assert result.get("_warning") == "empty_result_on_success"

    @patch("job_pipeline.subprocess.run")
    def test_no_warning_when_result_present(self, mock_run):
        """exit_code=0 и есть result → нет _warning."""
        mock_run.return_value = MagicMock(
            stdout=json.dumps({"result": "some text"}),
            stderr="",
            returncode=0,
        )
        role = self._make_role()
        result = jp._claude_call(role, "test", "s1")
        assert "_warning" not in result


# =========================================
# Prompts
# =========================================

class TestPrompts:
    def test_orchestrator_prompt_contains_job_id(self):
        p = jp._prompt_orchestrator("JOB-123")
        assert "JOB-123" in p
        assert "ORCHESTRATOR" in p
        assert "1_understanding.md" in p
        assert "4_orchestrator_plan.json" in p

    def test_task_prompt_contains_role_and_job(self):
        task = {"role": "researcher", "task_id": "T1", "inputs": [], "outputs": []}
        p = jp._prompt_task("JOB-456", task)
        assert "JOB-456" in p
        assert "researcher" in p

    def test_finalize_prompt_contains_job_id(self):
        p = jp._prompt_finalize("JOB-789")
        assert "JOB-789" in p
        assert "ORCHESTRATOR_FINALIZE" in p
        assert "7_done.md" in p


# =========================================
# run_job_pipeline — интеграция (мокаем _claude_call)
# =========================================

class TestRunJobPipeline:
    def _mock_claude_success(self, result_text="done"):
        return MagicMock(return_value={
            "result": result_text,
            "exit_code": 0,
            "stderr": "",
            "duration_sec": 1.0,
            "model": "test",
            "role": "test",
        })

    @patch("job_pipeline._claude_call")
    def test_pipeline_disabled_returns_immediately(self, mock_call, tmp_dirs):
        jp.set_pipeline_enabled(False)
        result = jp.run_job_pipeline(111, "hello")
        assert result["final_answer"] == "Pipeline disabled."
        mock_call.assert_not_called()

    @patch("job_pipeline._claude_call")
    def test_orchestrator_failure(self, mock_call, tmp_dirs):
        mock_call.return_value = {
            "result": "", "exit_code": 1, "stderr": "orch error",
            "duration_sec": 1.0, "model": "m", "role": "orchestrator",
        }
        result = jp.run_job_pipeline(111, "test")
        assert "ORCH_FAIL" in result["stages"]
        # New: human-readable error message
        assert "orch error" in result["final_answer"]

    @patch("job_pipeline._claude_call")
    def test_orchestrator_success_but_no_files(self, mock_call, tmp_dirs, monkeypatch):
        """Ключевой тест: orchestrator вернул exit_code=0 но не записал файлы.
        Это корневая причина пустых сообщений бота."""
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)
        mock_call.return_value = {
            "result": "I thought about it", "exit_code": 0, "stderr": "",
            "duration_sec": 1.0, "model": "m", "role": "orchestrator",
        }
        result = jp.run_job_pipeline(111, "test")
        # Should NOT return empty — should return Claude's raw text as fallback
        assert result["final_answer"] == "I thought about it"
        assert "ORCH_NO_FILES" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_orchestrator_no_files_no_result(self, mock_call, tmp_dirs, monkeypatch):
        """Orchestrator exit=0, no files, no result text → descriptive error."""
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)
        mock_call.return_value = {
            "result": "", "exit_code": 0, "stderr": "",
            "duration_sec": 1.0, "model": "m", "role": "orchestrator",
        }
        result = jp.run_job_pipeline(111, "test")
        assert "Оркестратор не создал план" in result["final_answer"]
        assert "ORCH_NO_FILES" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_smoke_mode(self, mock_call, tmp_dirs, monkeypatch):
        monkeypatch.setenv("PIPELINE_SMOKE", "1")

        def fake_claude(role, prompt, sid):
            # Orchestrator: записываем файлы чтобы smoke-проверка прошла
            job_dirs = list(tmp_dirs["jobs"].iterdir())
            if job_dirs:
                jd = job_dirs[0]
                (jd / "1_understanding.md").write_text("understood")
                (jd / "4_orchestrator_plan.json").write_text(json.dumps({"tasks": []}))
            return {
                "result": "ok", "exit_code": 0, "stderr": "",
                "duration_sec": 1.0, "model": "m", "role": "orchestrator",
            }

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "smoke test")
        assert "SMOKE_OK" in result["final_answer"]
        assert "SMOKE_STOP" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_smoke_mode_fails_on_empty_understanding(self, mock_call, tmp_dirs, monkeypatch):
        monkeypatch.setenv("PIPELINE_SMOKE", "1")
        mock_call.return_value = {
            "result": "ok", "exit_code": 0, "stderr": "",
            "duration_sec": 1.0, "model": "m", "role": "orchestrator",
        }
        # orchestrator не записал файлы → ORCH_NO_FILES (файлы проверяются до smoke)
        result = jp.run_job_pipeline(111, "test")
        assert "ORCH_NO_FILES" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_full_pipeline_success(self, mock_call, tmp_dirs, monkeypatch):
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)

        call_count = [0]

        def fake_claude(role, prompt, sid):
            call_count[0] += 1
            job_dirs = sorted(tmp_dirs["jobs"].iterdir())
            jd = job_dirs[0] if job_dirs else None

            if jd and role.key == "orchestrator":
                (jd / "1_understanding.md").write_text("understood")
                plan = {
                    "job_id": jd.name,
                    "goal": "test",
                    "deliverables": [],
                    "tasks": [
                        {"task_id": "T1", "role": "researcher", "inputs": [], "outputs": [], "acceptance": []},
                        {"task_id": "T2", "role": "orchestrator_finalize", "inputs": [], "outputs": [], "acceptance": []},
                    ],
                }
                (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
            elif jd and role.key == "orchestrator_finalize":
                (jd / "7_done.md").write_text("Final answer here.")

            return {
                "result": "ok", "exit_code": 0, "stderr": "",
                "duration_sec": 1.0, "model": role.model, "role": role.key,
            }

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "full test")
        assert result["final_answer"] == "Final answer here."
        assert "ORCH_OK" in result["stages"]
        assert call_count[0] == 3  # orch + researcher + finalize

    @patch("job_pipeline._claude_call")
    def test_task_failure_stops_pipeline(self, mock_call, tmp_dirs, monkeypatch):
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)

        def fake_claude(role, prompt, sid):
            job_dirs = sorted(tmp_dirs["jobs"].iterdir())
            jd = job_dirs[0]

            if role.key == "orchestrator":
                (jd / "1_understanding.md").write_text("ok")
                plan = {
                    "tasks": [
                        {"task_id": "T1", "role": "researcher", "inputs": [], "outputs": [], "acceptance": []},
                        {"task_id": "T2", "role": "critic", "inputs": [], "outputs": [], "acceptance": []},
                    ],
                }
                (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
                return {"result": "ok", "exit_code": 0, "stderr": "", "duration_sec": 1.0, "model": "m", "role": "orchestrator"}

            if role.key == "researcher":
                return {"result": "", "exit_code": 1, "stderr": "research failed", "duration_sec": 1.0, "model": "m", "role": "researcher"}

            return {"result": "ok", "exit_code": 0, "stderr": "", "duration_sec": 1.0, "model": "m", "role": role.key}

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "will fail")
        # Task failure produces human-readable error with role and error text
        assert "researcher" in result["final_answer"] or "research failed" in result["final_answer"]
        # critic should NOT have been called
        assert mock_call.call_count == 2  # orch + researcher only

    @patch("job_pipeline._claude_call")
    def test_unknown_role_in_plan(self, mock_call, tmp_dirs, monkeypatch):
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)

        def fake_claude(role, prompt, sid):
            job_dirs = sorted(tmp_dirs["jobs"].iterdir())
            jd = job_dirs[0]
            if role.key == "orchestrator":
                (jd / "1_understanding.md").write_text("ok")
                plan = {"tasks": [{"task_id": "T1", "role": "alien_role", "inputs": [], "outputs": []}]}
                (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
            return {"result": "ok", "exit_code": 0, "stderr": "", "duration_sec": 1.0, "model": "m", "role": role.key}

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "unknown role")
        assert "unknown_role_in_plan" in result["final_answer"]
        assert "ERROR" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_timeout_handled(self, mock_call, tmp_dirs):
        mock_call.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=240)
        result = jp.run_job_pipeline(111, "timeout test")
        assert "Превышено время" in result["final_answer"]
        assert "TIMEOUT" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_unexpected_exception_handled(self, mock_call, tmp_dirs):
        mock_call.side_effect = RuntimeError("something unexpected")
        result = jp.run_job_pipeline(111, "crash test")
        assert "Ошибка pipeline" in result["final_answer"]
        assert "ERROR" in result["stages"]

    @patch("job_pipeline._claude_call")
    def test_role_alias_resolved(self, mock_call, tmp_dirs, monkeypatch):
        """Проверяем что alias 'methodologist' -> 'methodist' работает."""
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)

        def fake_claude(role, prompt, sid):
            job_dirs = sorted(tmp_dirs["jobs"].iterdir())
            jd = job_dirs[0]
            if role.key == "orchestrator":
                (jd / "1_understanding.md").write_text("ok")
                plan = {
                    "tasks": [
                        {"task_id": "T1", "role": "methodologist", "inputs": [], "outputs": []},
                        {"task_id": "T2", "role": "orchestrator_finalize", "inputs": [], "outputs": []},
                    ],
                }
                (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
            elif role.key == "orchestrator_finalize":
                (jd / "7_done.md").write_text("done via alias")
            return {"result": "ok", "exit_code": 0, "stderr": "", "duration_sec": 1.0, "model": "m", "role": role.key}

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "alias test")
        assert result["final_answer"] == "done via alias"


# =========================================
# Worklog
# =========================================

class TestWorklog:
    def test_append_worklog(self, tmp_dirs):
        job_dir = tmp_dirs["jobs"] / "TEST-JOB"
        job_dir.mkdir()
        jp._append_worklog(job_dir, {"action": "test1"})
        jp._append_worklog(job_dir, {"action": "test2"})
        lines = (job_dir / "worklog.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["action"] == "test1"
        assert json.loads(lines[1])["action"] == "test2"


# =========================================
# Plan loading
# =========================================

class TestPlanLoad:
    def test_load_valid_plan(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        plan = {"tasks": [{"task_id": "T1", "role": "dev"}]}
        (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
        loaded = jp._load_plan(jd)
        assert loaded["tasks"][0]["role"] == "dev"

    def test_load_empty_plan_raises(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "4_orchestrator_plan.json").write_text("")
        with pytest.raises(RuntimeError, match="plan_missing"):
            jp._load_plan(jd)

    def test_load_invalid_json_raises(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "4_orchestrator_plan.json").write_text("{bad json")
        with pytest.raises(json.JSONDecodeError):
            jp._load_plan(jd)


# =========================================
# _verify_files_written (NEW)
# =========================================

class TestVerifyFilesWritten:
    def test_all_files_present(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "a.md").write_text("content")
        (jd / "b.md").write_text("content")
        assert jp._verify_files_written(jd, ["a.md", "b.md"]) is None

    def test_missing_file(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "a.md").write_text("content")
        err = jp._verify_files_written(jd, ["a.md", "b.md"])
        assert err is not None
        assert "b.md" in err

    def test_empty_file_detected(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "a.md").write_text("content")
        (jd / "b.md").write_text("")  # empty
        err = jp._verify_files_written(jd, ["a.md", "b.md"])
        assert err is not None
        assert "b.md" in err

    def test_whitespace_only_file_detected(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "a.md").write_text("   \n\n  ")  # whitespace only
        err = jp._verify_files_written(jd, ["a.md"])
        assert err is not None

    def test_no_files_to_check(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        assert jp._verify_files_written(jd, []) is None


# =========================================
# _collect_fallback_answer (NEW)
# =========================================

class TestCollectFallbackAnswer:
    def test_minimal_fallback(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "5_execution" / "outputs").mkdir(parents=True)
        answer = jp._collect_fallback_answer(jd, "JOB-TEST", ["ORCH_OK"])
        assert "JOB-TEST" in answer
        assert "ORCH_OK" in answer

    def test_fallback_includes_understanding(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "5_execution" / "outputs").mkdir(parents=True)
        (jd / "1_understanding.md").write_text("Задача: написать скрипт")
        answer = jp._collect_fallback_answer(jd, "JOB-TEST", [])
        assert "Задача: написать скрипт" in answer

    def test_fallback_includes_draft(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "5_execution" / "outputs").mkdir(parents=True)
        (jd / "5_execution" / "outputs" / "draft_answer.md").write_text("Вот черновик ответа")
        answer = jp._collect_fallback_answer(jd, "JOB-TEST", [])
        assert "Вот черновик ответа" in answer

    def test_fallback_truncates_long_text(self, tmp_dirs):
        jd = tmp_dirs["jobs"] / "JOB-TEST"
        jd.mkdir()
        (jd / "5_execution" / "outputs").mkdir(parents=True)
        (jd / "1_understanding.md").write_text("A" * 2000)
        answer = jp._collect_fallback_answer(jd, "JOB-TEST", [])
        # Understanding truncated to 500 chars
        assert len(answer) < 2000


# =========================================
# Pipeline: fallback when 7_done.md empty (NEW)
# =========================================

class TestPipelineFallbackAnswer:
    @patch("job_pipeline._claude_call")
    def test_empty_done_uses_fallback(self, mock_call, tmp_dirs, monkeypatch):
        """Когда orchestrator_finalize не записал 7_done.md, pipeline
        должен вернуть fallback-ответ вместо пустого сообщения."""
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)

        def fake_claude(role, prompt, sid):
            job_dirs = sorted(tmp_dirs["jobs"].iterdir())
            jd = job_dirs[0]
            if role.key == "orchestrator":
                (jd / "1_understanding.md").write_text("Нужно сделать X")
                plan = {
                    "tasks": [
                        {"task_id": "T1", "role": "orchestrator_finalize", "inputs": [], "outputs": []},
                    ],
                }
                (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
            # orchestrator_finalize does NOT write 7_done.md
            return {"result": "ok", "exit_code": 0, "stderr": "", "duration_sec": 1.0, "model": "m", "role": role.key}

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "fallback test")

        # Should NOT be empty or "DONE_BUT_EMPTY"
        assert result["final_answer"] != ""
        assert "DONE_BUT_EMPTY" not in result["final_answer"]
        # Should contain useful info from understanding
        assert "Нужно сделать X" in result["final_answer"]

    @patch("job_pipeline._claude_call")
    def test_final_answer_never_empty(self, mock_call, tmp_dirs, monkeypatch):
        """Pipeline NEVER returns empty final_answer — any path."""
        monkeypatch.delenv("PIPELINE_SMOKE", raising=False)

        def fake_claude(role, prompt, sid):
            job_dirs = sorted(tmp_dirs["jobs"].iterdir())
            jd = job_dirs[0]
            if role.key == "orchestrator":
                (jd / "1_understanding.md").write_text("ok")
                plan = {"tasks": [{"task_id": "T1", "role": "orchestrator_finalize", "inputs": [], "outputs": []}]}
                (jd / "4_orchestrator_plan.json").write_text(json.dumps(plan))
            return {"result": "", "exit_code": 0, "stderr": "", "duration_sec": 1.0, "model": "m", "role": role.key}

        mock_call.side_effect = fake_claude
        result = jp.run_job_pipeline(111, "empty test")
        assert result["final_answer"].strip() != ""
