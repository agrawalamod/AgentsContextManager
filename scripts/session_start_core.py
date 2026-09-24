#!/usr/bin/env python3
"""Shared SessionStart core for Claude and Codex (symmetric behavior).

Given a working directory it: (1) migrates any legacy root-level AGENTS_HISTORY.md into `.llm/`,
(2) auto-creates `.llm/AGENTS_HISTORY.md` if missing (scoped to under $HOME, minus a system-dir
denylist so it does not litter /tmp or system paths), (3) registers the directory for the
rollup, and (4) prints context to stdout for the agent to load: the curated PROJECT_JOURNEY.md,
the AGENTS_HISTORY.md log, any slack/outlook caches, and (at the root) the consolidated GLOBAL map.
"""
import os
import sys
import shutil

HOME = os.path.expanduser("~")
DENY_PREFIXES = ("/tmp", "/private", "/var", "/usr", "/etc", "/opt", "/bin", "/sbin",
                 "/System", "/Library")


def under_home(p):
    return p == HOME or p.startswith(HOME + os.sep)


def blocked(p):
    return any(p == d or p.startswith(d + os.sep) for d in DENY_PREFIXES)


def register(cwd):
    try:
        rd = os.path.join(HOME, ".agents-history")
        os.makedirs(rd, exist_ok=True)
        reg = os.path.join(rd, "registry.txt")
        seen = set(l.strip() for l in open(reg, encoding="utf-8", errors="ignore")) if os.path.isfile(reg) else set()
        if cwd not in seen:
            with open(reg, "a", encoding="utf-8") as fh:
                fh.write(cwd + "\n")
    except Exception:
        pass


def emit(path, header, note, n):
    if not os.path.isfile(path):
        return
    try:
        body = "\n".join(open(path, encoding="utf-8", errors="ignore").read().splitlines()[-n:])
    except Exception:
        return
    print("## " + header)
    print(note)
    print()
    print(body)
    print()


def main():
    cwd = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else os.getcwd()
    cwd = os.path.abspath(cwd)
    if not under_home(cwd) or blocked(cwd):
        return
    llm = os.path.join(cwd, ".llm")
    hist = os.path.join(llm, "AGENTS_HISTORY.md")
    legacy = os.path.join(cwd, "AGENTS_HISTORY.md")
    # migrate a legacy root-level file into .llm/
    try:
        if os.path.isfile(legacy) and not os.path.isfile(hist):
            os.makedirs(llm, exist_ok=True)
            shutil.move(legacy, hist)
    except Exception:
        pass
    # auto-create if missing, but NEVER when a legacy root-level file still exists (its
    # migration just failed, e.g. macOS privacy): creating an empty file here would strand
    # the legacy log. Leave it for a later session that can move it.
    try:
        if not os.path.isfile(hist) and not os.path.isfile(legacy):
            os.makedirs(llm, exist_ok=True)
            with open(hist, "w", encoding="utf-8") as fh:
                fh.write("# Agents History\n\nShared per-directory work log (Claude/Codex). "
                         "Agents read this at session start and append a dated entry when they "
                         "finish substantive work. Newest entry at the bottom.\n")
    except Exception:
        pass
    register(cwd)
    emit(os.path.join(llm, "PROJECT_JOURNEY.md"), "Project journey (.llm/PROJECT_JOURNEY.md)",
         "Canonical curated narrative: decisions, the why, dead-ends already ruled out, current "
         "standing. Read this first. Regenerate with /project_journey.", 400)
    emit(hist, "Shared directory history (.llm/AGENTS_HISTORY.md)",
         "Prior-thread log for this directory. Append a dated entry when you finish substantive work.", 200)
    emit(os.path.join(llm, "slack-context.md"), "Slack context (.llm/slack-context.md)",
         "Cached Slack discussion for this project. Refresh with /slack-sync.", 150)
    emit(os.path.join(llm, "outlook-context.md"), "Outlook context (.llm/outlook-context.md)",
         "Cached Outlook mail for this project. Refresh with /outlook-sync.", 150)
    # sync reminders for configured projects (preserves the old slack-sync nudge, both agents)
    if os.path.isfile(os.path.join(llm, "slack.channels")):
        print("## Slack sync")
        print("This project tracks Slack channel(s) in .llm/slack.channels. Early in your first "
              "response, run /slack-sync to refresh cached Slack context, unless the user's message "
              "is clearly unrelated. Treat it as background awareness, not the subject of your reply.")
        print()
    if os.path.isfile(os.path.join(llm, "outlook.filters")):
        print("## Outlook sync")
        print("This project tracks Outlook filters in .llm/outlook.filters. Early in your first "
              "response, run /outlook-sync to refresh cached mail, unless clearly unrelated. Treat "
              "it as background awareness.")
        print()
    emit(os.path.join(llm, "GLOBAL_AGENTS_HISTORY.md"), "Global agents history (consolidated map)",
         "High-level index across all tracked directories. Use it to route to the right directory.", 400)


if __name__ == "__main__":
    main()
