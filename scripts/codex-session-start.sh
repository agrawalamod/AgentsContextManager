#!/usr/bin/env bash
# Codex SessionStart hook (thin wrapper): ensure/inject this directory's .llm/ context via the
# shared core. Working directory parsed from the JSON payload on stdin (fallback $PWD).
core="$HOME/.agents-history/session_start_core.py"
[ -f "$core" ] || exit 0
payload="$(cat 2>/dev/null)"
cwd="$(printf '%s' "$payload" | python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("cwd") or "")
except Exception: print("")' 2>/dev/null)"
[ -z "$cwd" ] && cwd="$PWD"
exec python3 "$core" "$cwd"
