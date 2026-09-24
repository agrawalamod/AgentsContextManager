#!/usr/bin/env python3
"""Consolidate every `.llm/AGENTS_HISTORY.md` into one high-level map at the root.

Discovery unions two sources:
  1. The registry (~/.agents-history/registry.txt) of tracked directories, maintained by the
     SessionEnd hooks and read by direct path (works even for macOS folders whose enumeration
     is blocked by privacy/TCC, e.g. ~/Downloads).
  2. A best-effort filesystem walk under <root>.

For each directory it prefers the curated `.llm/PROJECT_JOURNEY.md` (its lead section) as the
summary, else the `.llm/AGENTS_HISTORY.md` Overview or recent entry titles, plus metadata.
Writes GLOBAL_AGENTS_HISTORY.md (default ~/.llm/), newest activity first. A parent/router agent
reads this map to see what work lives where; the per-directory files hold the detail.

Usage: python3 agents_history_rollup.py [--root DIR] [--out FILE] [--max-depth N]
Defaults: root=$HOME, out=<root>/.llm/GLOBAL_AGENTS_HISTORY.md, max-depth=8. Stdlib only.
"""
import argparse
import os
import re
import time

LEAF_REL = os.path.join(".llm", "AGENTS_HISTORY.md")
JOURNEY_REL = os.path.join(".llm", "PROJECT_JOURNEY.md")
GLOBAL_NAME = "GLOBAL_AGENTS_HISTORY.md"
REGISTRY = os.path.expanduser("~/.agents-history/registry.txt")
SKIP_DIRS = {
    "node_modules", "__pycache__", ".cache", ".mypy_cache", ".pytest_cache",
    "build", "dist", ".next", "venv", "Library", "target", ".terraform",
}


def _read(path):
    return open(path, encoding="utf-8", errors="ignore").read()


def journey_summary(path):
    """Lead prose of PROJECT_JOURNEY.md: the first body paragraph(s) under a heading."""
    try:
        lines = _read(path).splitlines()
    except Exception:
        return None
    body, started = [], False
    for ln in lines:
        if ln.startswith("## "):
            if body:
                break
            started = True
            continue
        if started and ln.strip() and not ln.strip().startswith(">"):
            body.append(ln.strip())
    text = " ".join(body).strip()
    return text or None


def history_summary(path):
    try:
        lines = _read(path).splitlines()
    except Exception:
        try:
            mt = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))
        except Exception:
            mt = time.strftime("%Y-%m-%d")
        return {"overview": "(present but unreadable by the process running the rollup; "
                            "grant Full Disk Access or run via an agent. Content is intact.)",
                "entry_count": 0, "last_date": mt, "recent": []}
    overview, in_ov, titles = [], False, []
    for ln in lines:
        if ln.strip().lower().startswith("## overview"):
            in_ov = True
            continue
        if in_ov:
            if ln.startswith("## "):
                in_ov = False
            elif ln.strip():
                overview.append(ln.strip())
        m = re.match(r"^##\s+(\d{4}-\d{2}-\d{2})\s*[:\-]\s*(.+)", ln)
        if m:
            title = re.sub(r"\s*<!--.*?-->\s*$", "", m.group(2))
            title = re.sub(r"\s*\[[^\]]*\]\s*$", "", title).strip()
            titles.append((m.group(1), title))
    last_date = titles[-1][0] if titles else time.strftime(
        "%Y-%m-%d", time.localtime(os.path.getmtime(path)))
    return {"overview": " ".join(overview).strip(), "entry_count": len(titles),
            "last_date": last_date, "recent": titles[-5:]}


def describe(dirpath):
    hist = os.path.join(dirpath, LEAF_REL)
    if not os.path.isfile(hist):
        return None
    info = history_summary(hist)
    j = os.path.join(dirpath, JOURNEY_REL)
    info["has_journey"] = os.path.isfile(j)
    if info["has_journey"]:
        js = journey_summary(j)
        if js:
            info["overview"] = js  # prefer the curated narrative's lead
    info["dir"] = os.path.abspath(dirpath)
    return info


def registry_dirs():
    dirs = []
    if os.path.isfile(REGISTRY):
        for line in _read(REGISTRY).splitlines():
            p = line.strip()
            if p and os.path.isdir(p):
                dirs.append(p)
    return dirs


def find_logs(root, out_path, max_depth):
    root = os.path.abspath(root)
    out_abs = os.path.abspath(out_path)
    seen = {}

    def add(dirpath):
        key = os.path.abspath(dirpath)
        if key in seen or os.path.abspath(os.path.join(dirpath, LEAF_REL)) == out_abs:
            return
        info = describe(dirpath)
        if info:
            seen[key] = info

    for d in registry_dirs():
        add(d)
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        if dirpath[len(root):].count(os.sep) >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS]
        if os.path.isfile(os.path.join(dirpath, LEAF_REL)):
            add(dirpath)
    return list(seen.values())


def render(root, logs):
    root = os.path.abspath(root)
    logs = sorted(logs, key=lambda x: x["last_date"], reverse=True)
    now = time.strftime("%Y-%m-%d %H:%M")
    out = [
        "# Global Agents History (consolidated map)", "",
        f"Generated {now} from {len(logs)} directories.",
        "High-level index of per-directory `.llm/` logs, newest activity first. A directory "
        "marked (journey) has a curated `.llm/PROJECT_JOURNEY.md`; open an agent there and it "
        "auto-loads. To work in a directory, open an agent there; its `.llm/AGENTS_HISTORY.md` "
        "has the full thread history. Refresh this map with the rollup script (see the kit).", "",
    ]
    for info in logs:
        rel = os.path.relpath(info["dir"], root)
        if rel.startswith(".."):
            rel = info["dir"]
        tag = " (journey)" if info.get("has_journey") else ""
        out.append(f"## {rel}{tag}   ({info['entry_count']} threads, last {info['last_date']})")
        if info["overview"]:
            ov = info["overview"]
            out.append(ov if len(ov) <= 600 else ov[:600] + "…")
        elif info["recent"]:
            for d, t in reversed(info["recent"]):
                out.append(f"- {d}: {t}")
        else:
            out.append("- (no entries yet)")
        out.append("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Consolidate .llm/AGENTS_HISTORY.md files into a global map.")
    ap.add_argument("--root", default=os.path.expanduser("~"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-depth", type=int, default=8)
    args = ap.parse_args()
    root = os.path.abspath(os.path.expanduser(args.root))
    out_path = os.path.abspath(os.path.expanduser(
        args.out or os.path.join(root, ".llm", GLOBAL_NAME)))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    logs = find_logs(root, out_path, args.max_depth)
    if not logs:
        # Never clobber an existing map with an empty one (e.g. registry lost or all unreadable).
        print(f"No tracked directories found; left {out_path} unchanged.")
        return
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(render(root, logs))
    print(f"Wrote {out_path} ({len(logs)} directories consolidated)")


if __name__ == "__main__":
    main()
