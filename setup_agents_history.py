#!/usr/bin/env python3
"""Set up the cross-agent .llm/ AGENTS_HISTORY system on this machine (idempotent).

Installs, for whichever of Claude Code / Codex CLI are present:
  - SessionStart hook -> shared core that auto-creates/migrates `.llm/`, registers the dir,
    and injects `.llm/PROJECT_JOURNEY.md` + `.llm/AGENTS_HISTORY.md` + slack/outlook caches +
    the root `.llm/GLOBAL_AGENTS_HISTORY.md`.
  - SessionEnd hook -> appends a mechanical entry to `.llm/AGENTS_HISTORY.md`.
  - The rule into the agent's instruction file (CLAUDE.md / Codex AGENTS.md).
  - Slash commands: /project_journey, /slack-sync, /outlook-sync (Claude commands + Codex prompts).
Shared: the rollup + SessionStart core in ~/.agents-history/, and a tracked-dir registry.

Run:  python3 setup_agents_history.py [--dry-run] [--claude-only] [--codex-only]
Stdlib only. Safe to re-run: it detects existing installs and does not duplicate.
"""
import argparse
import glob
import json
import os
import shutil
import stat

KIT = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
SHARED = os.path.join(HOME, ".agents-history")
RULE_SENTINEL = "## Cross-Agent Directory History"
BEGIN = "<!-- BEGIN AGENTS_HISTORY_RULE -->"
END = "<!-- END AGENTS_HISTORY_RULE -->"


def log(m):
    print(m)


def read(p):
    with open(p, encoding="utf-8", errors="ignore") as fh:
        return fh.read()


def make_exec(p):
    st = os.stat(p)
    os.chmod(p, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy(src, dst, dry, execbit=False):
    log(f"  -> {dst}")
    if dry:
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copyfile(src, dst)
    if execbit:
        make_exec(dst)


def insert_rule(md_path, dry):
    rule = read(os.path.join(KIT, "RULE.md")).strip()
    block = f"{BEGIN}\n{rule}\n{END}\n"
    existing = read(md_path) if os.path.isfile(md_path) else ""
    if RULE_SENTINEL in existing or BEGIN in existing:
        log(f"  rule already present in {md_path} (skip)")
        return
    log(f"  append rule -> {md_path}")
    if dry:
        return
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    with open(md_path, "a", encoding="utf-8") as fh:
        fh.write(sep + block)


def copy_commands(agent_subdir, dst_dir, dry):
    for src in sorted(glob.glob(os.path.join(KIT, "commands", agent_subdir, "*.md"))):
        copy(src, os.path.join(dst_dir, os.path.basename(src)), dry)


def add_json_hook(settings, event, command, timeout=None):
    arr = settings.setdefault("hooks", {}).setdefault(event, [])
    for group in arr:
        for h in group.get("hooks", []):
            if h.get("command", "").strip() == command:
                return False
    entry = {"type": "command", "command": command}
    if timeout:
        entry["timeout"] = timeout
    arr.append({"hooks": [entry]})
    return True


def install_shared(dry):
    log("Shared (~/.agents-history):")
    copy(os.path.join(KIT, "agents_history_rollup.py"), os.path.join(SHARED, "agents_history_rollup.py"), dry, True)
    copy(os.path.join(KIT, "scripts", "session_start_core.py"), os.path.join(SHARED, "session_start_core.py"), dry, True)


def install_claude(dry):
    cdir = os.path.join(HOME, ".claude")
    if not os.path.isdir(cdir):
        log("Claude: ~/.claude not found, skipping.")
        return
    log("Claude Code:")
    copy(os.path.join(KIT, "scripts", "claude-session-start.sh"), os.path.join(cdir, "hooks", "agents-history-context.sh"), dry, True)
    copy(os.path.join(KIT, "scripts", "claude-session-end.py"), os.path.join(cdir, "hooks", "agents-history-append.py"), dry, True)
    copy_commands("claude", os.path.join(cdir, "commands"), dry)
    spath = os.path.join(cdir, "settings.json")
    settings = json.loads(read(spath)) if os.path.isfile(spath) else {}
    a = add_json_hook(settings, "SessionStart", "bash ~/.claude/hooks/agents-history-context.sh", 10)
    b = add_json_hook(settings, "SessionEnd", "python3 ~/.claude/hooks/agents-history-append.py", 10)
    if a or b:
        log(f"  register settings.json hooks (SessionStart={a}, SessionEnd={b})")
        if not dry:
            with open(spath, "w", encoding="utf-8") as fh:
                json.dump(settings, fh, indent=2)
    else:
        log("  settings.json hooks already registered (skip)")
    insert_rule(os.path.join(cdir, "CLAUDE.md"), dry)


def install_codex(dry):
    cdir = os.path.join(HOME, ".codex")
    if not os.path.isdir(cdir):
        log("Codex: ~/.codex not found, skipping.")
        return
    log("Codex CLI:")
    start = os.path.join(cdir, "hooks", "agents-history-context.sh")
    end = os.path.join(cdir, "hooks", "agents-history-append.py")
    copy(os.path.join(KIT, "scripts", "codex-session-start.sh"), start, dry, True)
    copy(os.path.join(KIT, "scripts", "codex-session-end.py"), end, dry, True)
    copy_commands("codex", os.path.join(cdir, "prompts"), dry)
    cfg = os.path.join(cdir, "config.toml")
    text = read(cfg) if os.path.isfile(cfg) else ""
    if start in text and end in text:
        log("  config.toml [hooks] already registered (skip)")
    else:
        block = (
            "\n[hooks]\n"
            f'SessionStart = [{{ hooks = [{{ type = "command", command = "{start}" }}] }}]\n'
            f'SessionEnd = [{{ hooks = [{{ type = "command", command = "{end}", timeout = 10 }}] }}]\n'
        )
        candidate = text + block
        ok = True
        try:
            import tomllib
            h = tomllib.loads(candidate).get("hooks", {})
            ok = bool(h.get("SessionStart") and h.get("SessionEnd"))
        except ModuleNotFoundError:
            ok = True
        except Exception as e:
            ok = False
            log(f"  config.toml candidate INVALID ({e}); leaving config untouched")
        if ok:
            log("  register [hooks] in config.toml")
            if not dry:
                if os.path.isfile(cfg):
                    shutil.copyfile(cfg, cfg + ".bak.agentshist")
                with open(cfg, "w", encoding="utf-8") as fh:
                    fh.write(candidate)
    agents_md = os.path.join(cdir, "AGENTS.md")
    claude_md = os.path.join(HOME, ".claude", "CLAUDE.md")
    if os.path.islink(agents_md) and os.path.realpath(agents_md) == os.path.realpath(claude_md):
        log("  ~/.codex/AGENTS.md -> CLAUDE.md symlink; rule already covered")
    else:
        insert_rule(agents_md, dry)


def main():
    ap = argparse.ArgumentParser(description="Install the cross-agent .llm/ AGENTS_HISTORY system.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--claude-only", action="store_true")
    ap.add_argument("--codex-only", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run
    if dry:
        log("== DRY RUN (no changes) ==")
    install_shared(dry)
    if not args.codex_only:
        install_claude(dry)
    if not args.claude_only:
        install_codex(dry)
    log("")
    log("Done. Next steps:")
    log("  - Codex: first real session prompts to trust the new hooks; approve once "
        "(or run with --dangerously-bypass-hook-trust).")
    log("  - Open an agent in any project dir under $HOME: it auto-creates .llm/AGENTS_HISTORY.md "
        "and starts logging. Run /project_journey to synthesize .llm/PROJECT_JOURNEY.md.")
    log("  - Build the global map: python3 ~/.agents-history/agents_history_rollup.py --root ~")
    log("  - /slack-sync and /outlook-sync cache project comms under .llm/ (need the Slack/Outlook MCP).")
    log("  - macOS: to include privacy-protected folders (Downloads/Desktop) in the map, run the "
        "rollup from a terminal with Full Disk Access.")


if __name__ == "__main__":
    main()
