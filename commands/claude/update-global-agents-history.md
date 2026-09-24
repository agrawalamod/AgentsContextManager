---
description: Regenerate the consolidated ~/.llm/GLOBAL_AGENTS_HISTORY.md map from all tracked directories
---
Regenerate the consolidated global map that indexes every tracked directory's `.llm/AGENTS_HISTORY.md`.

## Steps
1. Run the rollup script:

        python3 ~/.agents-history/agents_history_rollup.py --root ~

   If the user gave an argument, use it as the root: `--root <arg>`. If the script is missing, tell the user to run the kit installer (`setup_agents_history.py`).
2. Read back the top of `~/.llm/GLOBAL_AGENTS_HISTORY.md` and report: how many directories were consolidated, the most recently active ones, and any directory shown as "unreadable" (needs macOS Full Disk Access for the process running this).
3. If a directory you expected is missing, note it: its `.llm/AGENTS_HISTORY.md` may not exist yet, or it is not in `~/.agents-history/registry.txt`.

Optional root override: $ARGUMENTS
