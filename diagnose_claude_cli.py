#!/usr/bin/env python3
"""
Диагностика: почему claude CLI возвращает пустой stdout из subprocess.

Запустить ДВА раза:
  1) python3 diagnose_claude_cli.py                        # чистое окружение
  2) set -a && source .env && set +a && python3 diagnose_claude_cli.py   # с env бота

Если #1 работает, а #2 нет — проблема в переменных .env
"""

import subprocess
import json
import os
import sys
import time

BLUE = "\033[94m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def header(msg):
    print(f"\n{BLUE}{'='*60}\n  {msg}\n{'='*60}{RESET}")

def run_claude(label, cmd, env=None):
    """Run claude CLI and print raw diagnostics."""
    print(f"\n{BLUE}--- {label} ---{RESET}")
    print(f"  cmd: {' '.join(cmd[:6])}{'...' if len(cmd)>6 else ''}")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, env=env,
        )
        dur = time.time() - t0
        print(f"  returncode: {proc.returncode}")
        print(f"  duration:   {dur:.1f}s")
        print(f"  stdout len: {len(proc.stdout)} bytes")
        print(f"  stderr len: {len(proc.stderr)} bytes")

        if proc.stdout.strip():
            try:
                j = json.loads(proc.stdout)
                print(f"  {GREEN}JSON parsed OK{RESET}")
                print(f"    num_turns: {j.get('num_turns')}")
                print(f"    result:    {str(j.get('result',''))[:200]}")
                print(f"    is_error:  {j.get('is_error')}")
                print(f"    cost:      ${j.get('total_cost_usd', 0):.4f}")
            except Exception as e:
                print(f"  {RED}JSON parse failed: {e}{RESET}")
                print(f"  raw stdout: {proc.stdout[:300]}")
        else:
            print(f"  {RED}EMPTY stdout!{RESET}")

        if proc.stderr.strip():
            print(f"  stderr: {proc.stderr[:300]}")

        return proc.returncode == 0 and len(proc.stdout.strip()) > 0

    except subprocess.TimeoutExpired:
        print(f"  {RED}TIMEOUT after {time.time()-t0:.0f}s{RESET}")
        return False
    except Exception as e:
        print(f"  {RED}ERROR: {e}{RESET}")
        return False


def main():
    header("Environment check")
    print(f"  USER:   {os.environ.get('USER', '?')}")
    print(f"  HOME:   {os.environ.get('HOME', '?')}")
    print(f"  PATH:   {os.environ.get('PATH', '?')[:200]}")

    # Check for env vars that might interfere with Claude CLI auth
    suspect_vars = [
        "ANTHROPIC_API_KEY", "CLAUDE_API_KEY", "CLAUDE_CONFIG_DIR",
        "ANTHROPIC_BASE_URL", "CLAUDE_CODE_API_KEY", "CLAUDE_ACCESS_TOKEN",
        "API_KEY", "OPENAI_API_KEY",
    ]
    print(f"\n  Suspect env vars:")
    found_suspects = []
    for v in suspect_vars:
        val = os.environ.get(v, "")
        if val:
            masked = f"{val[:6]}...{val[-4:]}" if len(val) > 10 else f"({len(val)} chars)"
            print(f"    {RED}{v} = {masked}{RESET}")
            found_suspects.append(v)
        else:
            print(f"    {v} = (not set)")

    header("Test 1: Simple hello (default env)")
    ok1 = run_claude("hello", [
        "claude", "-p", "Say hello in one word",
        "--output-format", "json", "--max-turns", "1",
    ])

    header("Test 2: Write tool (like orchestrator)")
    ok2 = run_claude("write_tool", [
        "claude", "-p",
        "Use the Write tool to write 'diagnostic test OK' to /tmp/claude_diag_test.txt",
        "--output-format", "json", "--model", "claude-opus-4-6",
        "--max-turns", "3", "--allowedTools", "Read,Write",
    ])

    # If suspects found, test with them unset
    if found_suspects:
        header(f"Test 3: hello WITH suspect vars REMOVED")
        clean_env = os.environ.copy()
        for v in found_suspects:
            clean_env.pop(v, None)
        ok3 = run_claude("hello_clean_env", [
            "claude", "-p", "Say hello in one word",
            "--output-format", "json", "--max-turns", "1",
        ], env=clean_env)

        header(f"Test 4: Write tool WITH suspect vars REMOVED")
        ok4 = run_claude("write_clean_env", [
            "claude", "-p",
            "Use the Write tool to write 'clean env test OK' to /tmp/claude_diag_test2.txt",
            "--output-format", "json", "--model", "claude-opus-4-6",
            "--max-turns", "3", "--allowedTools", "Read,Write",
        ], env=clean_env)
    else:
        ok3, ok4 = True, True

    header("SUMMARY")
    results = [
        ("Test 1 (simple hello)", ok1),
        ("Test 2 (write tool)", ok2),
    ]
    if found_suspects:
        results.append(("Test 3 (hello, clean env)", ok3))
        results.append(("Test 4 (write, clean env)", ok4))

    for label, ok in results:
        status = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  {label}: {status}")

    if found_suspects and not ok1 and ok3:
        print(f"\n  {RED}DIAGNOSIS: env vars are breaking Claude CLI!{RESET}")
        print(f"  Problematic vars: {', '.join(found_suspects)}")
        print(f"  FIX: remove these vars from subprocess env in _claude_call()")
    elif not ok1:
        print(f"\n  {RED}DIAGNOSIS: Claude CLI broken even without suspect vars{RESET}")
        print(f"  Check: claude auth, PATH, permissions")
    else:
        print(f"\n  {GREEN}All tests passed in current environment.{RESET}")
        if found_suspects:
            print(f"  BUT check if bot's .env sets different values!")

if __name__ == "__main__":
    main()
