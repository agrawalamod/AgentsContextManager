#!/usr/bin/env bash
# Claude SessionStart hook (thin wrapper): ensure/inject this directory's .llm/ context via the
# shared core. Working directory from CLAUDE_PROJECT_DIR (fallback $PWD).
core="$HOME/.agents-history/session_start_core.py"
[ -f "$core" ] || exit 0
exec python3 "$core" "${CLAUDE_PROJECT_DIR:-$PWD}"
