#!/usr/bin/env python3
"""SessionEnd hook: append a compact entry for the just-ended Claude session to
`<cwd>/AGENTS_HISTORY.md`, but only if that file already exists (opt-in per directory).

Mechanical extraction only (no model call): session title, the first user prompts, and
files touched. Dedups by session id via an HTML-comment marker so resuming/re-exiting a
session does not create duplicates. This is the auto-writer half of the cross-agent
AGENTS_HISTORY.md system; see the rule in ~/.claude/CLAUDE.md.
"""
import sys, os, json, time


def _register_dir(cwd):
    """Record this directory in the tracked-dirs registry the rollup reads."""
    try:
        reg_dir = os.path.expanduser("~/.agents-history")
        os.makedirs(reg_dir, exist_ok=True)
        reg = os.path.join(reg_dir, "registry.txt")
        cwd_abs = os.path.abspath(cwd)
        seen = set()
        if os.path.isfile(reg):
            seen = set(l.strip() for l in open(reg, encoding="utf-8", errors="ignore"))
        if cwd_abs not in seen:
            with open(reg, "a", encoding="utf-8") as fh:
                fh.write(cwd_abs + "\n")
    except Exception:
        pass


def main():
    try:
        raw = sys.stdin.read() if (sys.stdin and not sys.stdin.isatty()) else ""
    except Exception:
        raw = ""
    try:
        ev = json.loads(raw) if raw else {}
    except Exception:
        ev = {}
    if not isinstance(ev, dict):
        return

    if ev.get("reason") == "clear":            # do not log on /clear
        return
    cwd = ev.get("cwd") or os.getcwd()
    hist = os.path.join(cwd, ".llm", "AGENTS_HISTORY.md")
    if not os.path.isfile(hist):               # tracked dirs have .llm/AGENTS_HISTORY.md
        return
    _register_dir(cwd)
    tpath = ev.get("transcript_path", "")
    if not tpath or not os.path.isfile(tpath):
        return

    sid8 = (ev.get("session_id") or os.path.basename(tpath)).split(".")[0][:8]
    try:
        existing = open(hist, encoding="utf-8", errors="ignore").read()
    except Exception:
        existing = ""
    if ("sid:%s" % sid8) in existing:          # this session already logged
        return

    def trunc(s, n):
        s = " ".join(s.split())
        return s[:n] + ("…" if len(s) > n else "")

    title = name = None
    ups = []
    files_touched = []
    n_user = 0
    try:
        for line in open(tpath, encoding="utf-8", errors="ignore"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            t = o.get("type")
            if t == "ai-title" and o.get("aiTitle"):
                title = o["aiTitle"]
            if o.get("customName"):
                name = o["customName"]
            if t == "user":
                c = o.get("message", {}).get("content")
                txt = ""
                if isinstance(c, str):
                    txt = c
                elif isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "text":
                            txt += " " + b.get("text", "")
                txt = txt.strip()
                if txt and not txt.startswith("<"):
                    n_user += 1
                    if len(ups) < 2:
                        ups.append(trunc(txt, 200))
            if t == "assistant":
                c = o.get("message", {}).get("content")
                if isinstance(c, list):
                    for b in c:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in ("Edit", "Write", "NotebookEdit"):
                            fp = (b.get("input") or {}).get("file_path")
                            if fp and fp not in files_touched and len(files_touched) < 12:
                                files_touched.append(fp)
    except Exception:
        return

    if n_user == 0:                            # skip trivial/empty sessions
        return

    date = time.strftime("%Y-%m-%d")
    ttl = name or title or (ups[0][:60] if ups else "session")
    out = ["", "## %s: %s [Claude, auto] <!-- sid:%s -->" % (date, ttl, sid8)]
    if ups:
        out.append("- Did: " + "; ".join(ups))
    if files_touched:
        out.append("- Files: " + ", ".join(files_touched))
    try:
        with open(hist, "a", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
    except Exception:
        return


if __name__ == "__main__":
    main()
