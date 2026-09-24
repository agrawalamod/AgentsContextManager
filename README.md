# Agents History Kit

A cross-agent, per-directory memory system for CLI coding agents (Claude Code, Codex), built
around a `.llm/` folder in each working directory. Agents read it at session start and append
to it at exit, so context follows the *directory* rather than the agent or the individual thread.
A root map consolidates every directory's log so a parent/router agent sees the whole landscape.

## The layout
- `<dir>/.llm/AGENTS_HISTORY.md` — append-only log of threads worked in that directory (auto).
- `<dir>/.llm/PROJECT_JOURNEY.md` — curated technical narrative: why, dead-ends ruled out,
  current standing. Created by the `/project_journey` command. Auto-loaded (Claude `@import`,
  Codex `AGENTS.md` pointer).
- `<dir>/.llm/slack-context.md`, `outlook-context.md` — cached comms (`/slack-sync`, `/outlook-sync`).
- `~/.llm/GLOBAL_AGENTS_HISTORY.md` — consolidated high-level map of all directories below root.

## What it installs
- **Shared** (`~/.agents-history/`): `session_start_core.py` (the SessionStart logic both agents
  call) and `agents_history_rollup.py` (builds the global map). Plus a tracked-dir registry.
- **Claude Code** (`~/.claude`): SessionStart + SessionEnd hooks in `settings.json`, hook scripts
  in `~/.claude/hooks/`, commands in `~/.claude/commands/`, and the rule in `~/.claude/CLAUDE.md`.
- **Codex CLI** (`~/.codex`): SessionStart + SessionEnd hooks in `config.toml [hooks]`, hook
  scripts in `~/.codex/hooks/`, prompts in `~/.codex/prompts/`, and the rule in `~/.codex/AGENTS.md`
  (skipped if that is already a symlink to CLAUDE.md).

## Requirements
- Python 3 (3.11+ preferred, used to validate Codex's TOML). macOS or Linux.
- Claude Code and/or Codex CLI installed. Whichever is present gets set up.

## Install
    python3 setup_agents_history.py             # set up whatever is present
    python3 setup_agents_history.py --dry-run    # preview, change nothing
    python3 setup_agents_history.py --claude-only
    python3 setup_agents_history.py --codex-only
Idempotent: safe to re-run. It detects existing installs and does not duplicate.

## Daily use
- Open an agent in any project directory under your home: it auto-creates `.llm/AGENTS_HISTORY.md`,
  injects the `.llm/` context, and appends a one-line summary at exit (tagged `[Claude, auto]` /
  `[Codex, auto]`).
- `/project_journey` — synthesize the detailed `.llm/PROJECT_JOURNEY.md` from all threads + the log
  + discussions. Run manually when you want it refreshed.
- `/slack-sync`, `/outlook-sync` — cache project comms under `.llm/` (first run asks what's relevant).
- `/update-agents-history` — append a curated entry for the current session to this directory's log now.
- `/update-global-agents-history` — rebuild the root map. The global map ONLY refreshes when this
  (or the rollup) runs; the per-directory logs update automatically. Equivalent direct call:
  `python3 ~/.agents-history/agents_history_rollup.py --root ~`.

## Notes
- **Auto-track scope**: the SessionStart hook creates `.llm/` in any directory under `$HOME` (a
  system-dir denylist keeps it out of `/tmp`, `/usr`, etc.). Tracking is automatic, not opt-in.
- **Codex trust**: the first real Codex session after install prompts you to trust the two new hooks.
  Approve once, or launch with `--dangerously-bypass-hook-trust`.
- **Slack/Outlook**: `/slack-sync` and `/outlook-sync` need the `slack-mcp` / `aws-outlook-mcp`
  servers reachable in the agent (auth is per-session).
- **macOS privacy (TCC)**: reading protected folders (Downloads, Desktop) needs Full Disk Access for
  the process running the rollup. The registry still lists such directories; grant Full Disk Access
  or run the rollup via an agent that has it to include their content.

## Files
- `setup_agents_history.py` — installer
- `agents_history_rollup.py` — global consolidator
- `RULE.md` — the rule inserted into agent instruction files
- `scripts/` — hook scripts + `session_start_core.py`
- `commands/claude/`, `commands/codex/` — the slash commands: project_journey, slack-sync, outlook-sync, update-agents-history, update-global-agents-history
