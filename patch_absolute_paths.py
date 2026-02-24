#!/usr/bin/env python3
"""Patch job_pipeline.py: convert prompts from relative to absolute paths.

Fixes: "Оркестратор не создал план" — Claude CLI in headless mode
doesn't resolve relative paths correctly. This patch makes all file
paths in prompts absolute using JOBS_DIR and KB_DIR.

Run on server: python3 patch_absolute_paths.py
"""
import shutil

FILE = '/home/ec2-user/ai-assistant/job_pipeline.py'

shutil.copy2(FILE, FILE + '.bak2')
print(f"Backup: {FILE}.bak2")

with open(FILE, 'r') as f:
    c = f.read()

changes = 0

# === Fix 1: Orchestrator prompt — add job_dir/kb_dir locals, use absolute paths ===
old = (
    'def _prompt_orchestrator(job_id: str) -> str:\n'
    '    # Orchestrator writes: 1_understanding.md + 4_orchestrator_plan.json\n'
    '    # It must keep plan minimal, but include tasks in strict order.\n'
    '    return (\n'
    '        "You are ORCHESTRATOR.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
    '        "Step 1 \\u2014 Read these files using the Read tool:\\n"\n'
    '        f"- jobs/{job_id}/0_request.md\\n"\n'
    '        f"- kb/user_profile.md\\n"\n'
    '        f"- kb/playbooks/pipeline.md\\n\\n"\n'
    '        "Step 2 \\u2014 Use the Write tool to create these files:\\n"\n'
    '        f"- jobs/{job_id}/1_understanding.md\\n"\n'
    '        f"- jobs/{job_id}/4_orchestrator_plan.json\\n\\n"\n'
)
new = (
    'def _prompt_orchestrator(job_id: str) -> str:\n'
    '    # Orchestrator writes: 1_understanding.md + 4_orchestrator_plan.json\n'
    '    # It must keep plan minimal, but include tasks in strict order.\n'
    '    job_dir = JOBS_DIR / job_id\n'
    '    kb_dir = KB_DIR\n'
    '    return (\n'
    '        "You are ORCHESTRATOR.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
    '        "Step 1 \\u2014 Read the request file using the Read tool:\\n"\n'
    '        f"- {job_dir}/0_request.md\\n"\n'
    '        f"(Also try to read {kb_dir}/user_profile.md and {kb_dir}/playbooks/pipeline.md if they exist, but do NOT fail if they are missing.)\\n\\n"\n'
    '        "Step 2 \\u2014 Use the Write tool to create these files:\\n"\n'
    '        f"- {job_dir}/1_understanding.md\\n"\n'
    '        f"- {job_dir}/4_orchestrator_plan.json\\n\\n"\n'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print("[OK] orchestrator prompt: absolute paths + optional kb/")
else:
    print("[SKIP] orchestrator prompt: pattern not found (maybe already patched)")

# === Fix 2: Task prompt — add job_dir local, add JOB_DIR line ===
old = (
    'def _prompt_task(job_id: str, task: Dict[str, Any]) -> str:\n'
    '    role = task.get("role", "")\n'
    '    return (\n'
    '        f"You are role={role}.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
)
new = (
    'def _prompt_task(job_id: str, task: Dict[str, Any]) -> str:\n'
    '    role = task.get("role", "")\n'
    '    job_dir = JOBS_DIR / job_id\n'
    '    return (\n'
    '        f"You are role={role}.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        f"JOB_DIR={job_dir}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n"\n'
    '        "All file paths are ABSOLUTE. Use them exactly as given.\\n\\n"\n'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print("[OK] task prompt: absolute paths + JOB_DIR header")
else:
    print("[SKIP] task prompt: pattern not found (maybe already patched)")

# === Fix 3: Finalize prompt — add job_dir local, use absolute paths ===
old = (
    'def _prompt_finalize(job_id: str) -> str:\n'
    '    return (\n'
    '        "You are ORCHESTRATOR_FINALIZE.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
    '        "Step 1 \\u2014 Read these files using the Read tool:\\n"\n'
    '        f"- jobs/{job_id}/6_qa.md\\n"\n'
    '        f"- jobs/{job_id}/5_execution/outputs/draft_answer.md\\n\\n"\n'
    '        "Step 2 \\u2014 Use the Write tool to create:\\n"\n'
    '        f"- jobs/{job_id}/7_done.md\\n\\n"\n'
)
new = (
    'def _prompt_finalize(job_id: str) -> str:\n'
    '    job_dir = JOBS_DIR / job_id\n'
    '    return (\n'
    '        "You are ORCHESTRATOR_FINALIZE.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
    '        "Step 1 \\u2014 Read these files using the Read tool:\\n"\n'
    '        f"- {job_dir}/6_qa.md\\n"\n'
    '        f"- {job_dir}/5_execution/outputs/draft_answer.md\\n\\n"\n'
    '        "Step 2 \\u2014 Use the Write tool to create:\\n"\n'
    '        f"- {job_dir}/7_done.md\\n\\n"\n'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print("[OK] finalize prompt: absolute paths")
else:
    print("[SKIP] finalize prompt: pattern not found (maybe already patched)")

with open(FILE, 'w') as f:
    f.write(c)

print(f"\nTotal changes: {changes}")
if changes == 3:
    print("SUCCESS — all 3 prompts patched to absolute paths")
elif changes > 0:
    print(f"PARTIAL — {changes}/3 applied. Check skipped items.")
else:
    print("NO CHANGES — file may already be patched or has different format")
print(f"Restore backup if needed: cp {FILE}.bak2 {FILE}")
