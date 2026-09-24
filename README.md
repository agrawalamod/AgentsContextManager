# Agents Context Manager

**Give your CLI coding agents a shared, per-directory memory that survives across threads and across tools.**

If you use Claude Code or Codex, you start a lot of separate conversations in the same directory, and every new one begins with no idea what the previous ones did. Switch from Claude to Codex and it is worse: neither can see the other's history. Agents Context Manager fixes that. It keeps a small `.llm/` folder in each working directory that both agents read at the start of a session and append to at the end, so context follows the **directory**, not the agent or the individual chat. A root map consolidates every directory's log so a top-level agent can see the whole landscape and route you to the right place.

It is plain Markdown files plus lightweight hooks. No database, no service, no lock-in. Uninstalling means deleting a few files.

---

## The idea

Two tiers, both shared by Claude and Codex:

```
~/Documents/my-project/
└── .llm/
    ├── AGENTS_HISTORY.md      # append-only log of every thread worked here (auto)
    ├── PROJECT_JOURNEY.md     # curated technical narrative (manual: /project_journey)
    ├── slack-context.md       # cached Slack discussion (manual: /slack-sync)
    └── outlook-context.md     # cached mail (manual: /outlook-sync)

~/.llm/
├── AGENTS_HISTORY.md          # your home directory's own log
└── GLOBAL_AGENTS_HISTORY.md   # consolidated high-level map of every tracked directory
```

- **Leaf log** (`.llm/AGENTS_HISTORY.md`): the running history of a directory. Maintained automatically.
- **Curated journey** (`.llm/PROJECT_JOURNEY.md`): the deep narrative for a project, the why, the decisions, and the dead-ends already ruled out. You generate it on demand; it is the highest-signal file and auto-loads every session.
- **Global map** (`~/.llm/GLOBAL_AGENTS_HISTORY.md`): a one-screen index of what work lives in which directory, so a parent agent knows where to send you.

## Quickstart

```
git clone git@github.com:agrawalamod/AgentsContextManager.git
cd AgentsContextManager
python3 setup_agents_history.py          # sets up whichever of Claude / Codex you have
```

Preview without changing anything:

```
python3 setup_agents_history.py --dry-run
```

The installer is idempotent. Re-running detects what is already set up and does not duplicate. Flags: `--dry-run`, `--claude-only`, `--codex-only`.

## How it works

- **On session start**, a hook ensures the current directory has `.llm/AGENTS_HISTORY.md` (creating it if missing, under your home directory only) and injects the journey, the log, any cached comms, and the global map into the agent's context. You start informed.
- **On session end**, a hook appends a short entry for what the session did. It is append-only and skips sessions with nothing new, so the log stays clean.
- **The global map** is a derived index. It refreshes when you run `/update-global-agents-history` (or the rollup script). The per-directory logs stay current on their own.

Both agents call the exact same core logic, so behavior is identical whether you are in Claude or Codex. Entries are tagged `[Claude]` or `[Codex]` so a mixed history stays readable.

## Commands

Available in both Claude (`/name`) and Codex (`/name`):

| Command | What it does | When |
|---|---|---|
| `/project_journey` | Reads all of a project's threads, its log, and cached discussions, then writes the detailed `.llm/PROJECT_JOURNEY.md`. Preserves prior curated content instead of overwriting. | Manual, when you want the narrative refreshed |
| `/slack-sync` | Caches the project's Slack channel(s) into `.llm/slack-context.md`. First run asks which channels. | When you want current Slack context |
| `/outlook-sync` | Caches relevant Outlook mail into `.llm/outlook-context.md`. First run asks which senders/subjects/folders. | When you want current mail context |
| `/update-agents-history` | Appends a curated entry for the current session to this directory's log. Append-only, skips if nothing new. | To checkpoint mid-session |
| `/update-global-agents-history` | Rebuilds `~/.llm/GLOBAL_AGENTS_HISTORY.md`. | After a working session, to refresh the map |

## What gets installed

- **Shared** (`~/.agents-history/`): the SessionStart core both agents call, the rollup script, and a registry of tracked directories.
- **Claude Code** (`~/.claude/`): SessionStart and SessionEnd hooks in `settings.json`, the hook scripts, the five commands in `commands/`, and the rule appended to `CLAUDE.md`.
- **Codex CLI** (`~/.codex/`): the same hooks in `config.toml` under `[hooks]`, the hook scripts, the five prompts in `prompts/`, and the rule in `AGENTS.md` (skipped if that is already a symlink to `CLAUDE.md`).

## Requirements and caveats

- **Python 3** (3.11+ preferred; used to validate Codex's TOML). macOS or Linux. Claude Code and/or Codex installed; whichever is present gets set up.
- **It ships the mechanism, not data.** Your logs, journeys, and cached comms stay on your machine. A fresh install starts empty.
- **Codex trust:** the first real Codex session after install prompts you to trust the two new hooks. Approve once, or launch with `--dangerously-bypass-hook-trust`.
- **Slack / Outlook:** `/slack-sync` and `/outlook-sync` need a Slack or Outlook MCP server reachable in your agent. The history and journey features need no MCP at all.
- **macOS privacy:** reading protected folders (Downloads, Desktop) needs Full Disk Access for the process running the rollup. The registry still lists those directories; grant Full Disk Access, or run the rollup from an agent that has it, to include their contents.

## Repository layout

```
setup_agents_history.py     # idempotent installer
agents_history_rollup.py    # builds the consolidated global map
RULE.md                     # the rule inserted into CLAUDE.md / AGENTS.md
scripts/                    # hook scripts + the shared session_start_core.py
commands/claude/            # the five slash commands (Claude format)
commands/codex/             # the five slash commands (Codex prompt format)
```

## Uninstall

Delete `~/.agents-history/`, remove the hook entries from `~/.claude/settings.json` and `~/.codex/config.toml`, and delete the command files. The `.llm/` folders and their contents are yours to keep or remove; nothing else depends on them.
