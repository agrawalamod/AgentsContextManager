#!/usr/bin/env python3
"""Codex SessionEnd hook: append a compact entry for the just-ended Codex session to
`<cwd>/AGENTS_HISTORY.md`, but only if that file already exists (opt-in per directory).

Parses Codex's rollout transcript (transcript_path) to extract the first real user
prompts and any files edited via apply_patch. Dedups by session id via an HTML-comment
marker. Mirrors the Claude SessionEnd hook so entries interleave in the same file.
"""
import sys, os, json, re, time

# User-message prefixes that are injected context, not real prompts; skip them.
INJECTED = (
    "# AGENTS.md instructions", "<user_instructions>", "<environment_context>",
    "# Environment", "<INSTRUCTIONS>", "## Shared directory history",
    "# Agents History", "# AGENTS",
)


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


def is_injected(t):
    ts = t.lstrip()
    return any(ts.startswith(p) for p in INJECTED)


def trunc(s, n):
    s = " ".join(s.split())
    return s[:n] + ("…" if len(s) > n else "")


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
    if ev.get("reason") == "clear":
        return
    cwd = ev.get("cwd") or os.getcwd()
    hist = os.path.join(cwd, ".llm", "AGENTS_HISTORY.md")
    if not os.path.isfile(hist):
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
    if ("sid:%s" % sid8) in existing:
        return

    ups = []
    files = []
    n_user = 0
    try:
        for line in open(tpath, encoding="utf-8", errors="ignore"):
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") != "response_item":
                continue
            p = o.get("payload", {})
            pt = p.get("type")
            if pt == "message":
                text = " ".join(
                    b.get("text", "") for b in p.get("content", [])
                    if isinstance(b, dict) and b.get("type") in ("input_text", "text", "output_text")
                ).strip()
                if text and p.get("role") == "user" and not is_injected(text):
                    n_user += 1
                    if len(ups) < 2:
                        ups.append(trunc(text, 200))
            elif pt == "function_call":
                args = p.get("arguments", "")
                if isinstance(args, str) and "File:" in args:
                    for m in re.finditer(r"\*\*\* (?:Add|Update|Delete) File: (.+)", args):
                        fp = m.group(1).strip().strip('"').strip("\\").strip()
                        if fp and fp not in files and len(files) < 12:
                            files.append(fp)
    except Exception:
        return

    if n_user == 0:
        return
    date = time.strftime("%Y-%m-%d")
    ttl = ups[0][:60] if ups else "Codex session"
    out = ["", "## %s: %s [Codex, auto] <!-- sid:%s -->" % (date, ttl, sid8)]
    if ups:
        out.append("- Did: " + "; ".join(ups))
    if files:
        out.append("- Files: " + ", ".join(files))
    try:
        with open(hist, "a", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
    except Exception:
        return


if __name__ == "__main__":
    main()
