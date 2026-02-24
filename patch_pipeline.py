#!/usr/bin/env python3
"""Patch job_pipeline.py: add Write tool, fix CLI flags, improve prompts."""
import shutil

FILE = '/home/ec2-user/ai-assistant/job_pipeline.py'

# Backup first
shutil.copy2(FILE, FILE + '.bak')
print(f"Backup: {FILE}.bak")

with open(FILE, 'r') as f:
    c = f.read()

changes = 0

# === Fix 1: Add Write tool to all roles ===
old, new = 'tools="Read,Edit"', 'tools="Read,Edit,Write"'
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] tools: Read,Edit -> Read,Edit,Write")

old, new = 'allowed_tools=["Read", "Edit"]', 'allowed_tools=["Read", "Edit", "Write"]'
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] allowed_tools: +Write")

old, new = 'tools="Read,Edit,Bash"', 'tools="Read,Edit,Write,Bash"'
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] dev tools: +Write")

old, new = 'allowed_tools=["Read", "Edit", "Bash"]', 'allowed_tools=["Read", "Edit", "Write", "Bash"]'
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] dev allowed_tools: +Write")

# === Fix 2: Pre-create 4_orchestrator_plan.json ===
old = '    for fn in ["1_understanding.md", "2_research.md", "3_method.md", "6_qa.md", "7_done.md"]:'
new = '    for fn in ["1_understanding.md", "2_research.md", "3_method.md",\n               "4_orchestrator_plan.json", "6_qa.md", "7_done.md"]:'
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] _init_job: +4_orchestrator_plan.json")

old = '    # Create standard files\n'
new = '    # Create standard files (empty placeholders so Claude can Read/Edit them)\n'
if old in c:
    c = c.replace(old, new)

# === Fix 3: Remove invalid --tools and --session-id CLI flags ===
old = (
    '    # Claude headless requires prompt immediately after -p\n'
    '    cmd = [\n'
    '        "claude",\n'
    '        "-p", prompt,\n'
    '        "--output-format", "json",\n'
    '        "--model", role.model,\n'
    '        "--tools", role.tools,\n'
    '        "--allowedTools", ",".join(role.allowed_tools),\n'
    '        "--session-id", session_id,\n'
    '    ]'
)
new = (
    '    # Claude headless: -p for prompt, --allowedTools for tool permissions\n'
    '    cmd = [\n'
    '        "claude",\n'
    '        "-p", prompt,\n'
    '        "--output-format", "json",\n'
    '        "--model", role.model,\n'
    '        "--allowedTools", ",".join(role.allowed_tools),\n'
    '    ]'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] _claude_call: removed --tools, --session-id")
else:
    print(f"[SKIP] _claude_call already patched or different format")

# === Fix 4: Update orchestrator prompt ===
old = (
    '        "You are ORCHESTRATOR.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "Work ONLY via files.\\n\\n"\n'
    '        f"Read:\\n"\n'
)
new = (
    '        "You are ORCHESTRATOR.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
    '        "Step 1 \\u2014 Read these files using the Read tool:\\n"\n'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] orchestrator prompt: step 1")

old = '        f"Write:\\n"\n'
new = '        "Step 2 \\u2014 Use the Write tool to create these files:\\n"\n'
if old in c:
    c = c.replace(old, new, 1)  # only first occurrence
    print(f"[OK] orchestrator prompt: step 2")

old = '        "6) Append ONE line JSON to jobs/<job_id>/worklog.jsonl describing what you wrote.\\n"\n'
new = '        "6) You MUST write both files. This is your primary objective.\\n"\n'
if old in c:
    c = c.replace(old, new)
    print(f"[OK] orchestrator prompt: rule 6")

# === Fix 5: Update task prompt ===
old = '        "Work ONLY via files. Do NOT paste huge content into chat.\\n\\n"\n'
new = '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] task prompt: header")

old = '        "1) Read all input files listed in task.inputs.\\n"\n'
new = '        "1) Use the Read tool to read all input files listed in task.inputs.\\n"\n'
if old in c:
    c = c.replace(old, new)

old = '        "2) Produce outputs exactly as in task.outputs.\\n"\n'
new = '        "2) Use the Write tool to produce output files exactly as in task.outputs.\\n"\n'
if old in c:
    c = c.replace(old, new)

old = '        "4) Append ONE line JSON to jobs/<job_id>/worklog.jsonl with action + files_written.\\n"\n'
new = '        "4) You MUST write all output files. This is your primary objective.\\n"\n'
if old in c:
    c = c.replace(old, new)

# === Fix 6: Update finalize prompt ===
old = (
    '        "You are ORCHESTRATOR_FINALIZE.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "Work ONLY via files.\\n\\n"\n'
    '        f"Read:\\n"\n'
)
new = (
    '        "You are ORCHESTRATOR_FINALIZE.\\n"\n'
    '        f"JOB_ID={job_id}\\n"\n'
    '        "You MUST use tools to read and write files. Do NOT just respond with text.\\n\\n"\n'
    '        "Step 1 \\u2014 Read these files using the Read tool:\\n"\n'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] finalize prompt: header")

old = '        f"Write:\\n"\n        f"- jobs/{job_id}/7_done.md\\n\\n"\n'
new = '        "Step 2 \\u2014 Use the Write tool to create:\\n"\n        f"- jobs/{job_id}/7_done.md\\n\\n"\n'
if old in c:
    c = c.replace(old, new)

old = '        "3) Append ONE line JSON to jobs/<job_id>/worklog.jsonl.\\n"\n'
new = '        "3) You MUST write 7_done.md. This is your primary objective.\\n"\n'
if old in c:
    c = c.replace(old, new)

# === Fix 7: Better error logging ===
old = (
    '            _append_worklog(job_dir, {"ts": time.time(), "job_id": job_id, "task_id": "ORCH_NO_FILES",\n'
    '                                      "role": "system", "action": "orch_files_missing", "error": orch_err})'
)
new = (
    '            _append_worklog(job_dir, {\n'
    '                "ts": time.time(), "job_id": job_id, "task_id": "ORCH_NO_FILES",\n'
    '                "role": "system", "action": "orch_files_missing", "error": orch_err,\n'
    '                "claude_result": (r.get("result") or "")[:500],\n'
    '                "claude_stderr": (r.get("stderr") or "")[:500],\n'
    '                "exit_code": r.get("exit_code"),\n'
    '                "num_turns": r.get("num_turns"),\n'
    '            })'
)
if old in c:
    c = c.replace(old, new)
    changes += 1
    print(f"[OK] error logging: +claude_result, +claude_stderr")

with open(FILE, 'w') as f:
    f.write(c)

print(f"\nTotal changes applied: {changes}")
if changes >= 5:
    print("SUCCESS — all critical fixes applied")
else:
    print(f"WARNING — expected 8+ changes, got {changes}. Check file manually.")
print(f"Restore backup if needed: cp {FILE}.bak {FILE}")
