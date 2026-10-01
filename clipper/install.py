#!/usr/bin/env python3
"""Install the "Save to AI Context" clipper on macOS (idempotent).

  - Copies save-clip.sh to ~/.ai-context/ and, on first install, writes
    ~/.ai-context/config.sh with the full claude path and an empty profile line.
  - Builds and signs the "Save to AI Context" Quick Action and opens it for import.
  - Appends the saved-context rule to ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md.

Run:  python3 clipper/install.py [--dry-run] [--no-shortcut]
Stdlib only. Needs macOS (Shortcuts) and the claude CLI on PATH.
"""
import argparse
import os
import plistlib
import shutil
import subprocess
import tempfile
import uuid

KIT = os.path.dirname(os.path.abspath(__file__))
HOME = os.path.expanduser("~")
TARGET = os.path.join(HOME, ".ai-context")
NAME = "Save to AI Context"
RULE_SENTINEL = "## Saved Reading Context"
BEGIN = "<!-- BEGIN AI_CONTEXT_RULE -->"
END = "<!-- END AI_CONTEXT_RULE -->"


def log(m):
    print(m, flush=True)


def install_script(dry):
    dst = os.path.join(TARGET, "save-clip.sh")
    log(f"  copy save-clip.sh -> {dst}")
    if dry:
        return
    os.makedirs(TARGET, exist_ok=True)
    shutil.copy2(os.path.join(KIT, "save-clip.sh"), dst)
    os.chmod(dst, 0o755)


def write_config(dry):
    path = os.path.join(TARGET, "config.sh")
    if os.path.exists(path):
        log(f"  {path} exists (skip)")
        return
    claude = shutil.which("claude") or ""
    if not claude:
        log("  WARNING: claude is not on PATH; set claude= in config.sh by hand")
    log(f"  write {path}")
    if dry:
        return
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Local settings for save-clip.sh. Not tracked in git.\n"
                 f'claude="{claude}"\n'
                 "# One line about you (job, current goals). It sharpens topic routing.\n"
                 'profile=""\n')


def build_shortcut(dry):
    """One Quick Action step: pass the selection (or the clipboard) to save-clip.sh as arguments."""
    signed = os.path.join(TARGET, f"{NAME}.shortcut")
    log(f"  build + sign shortcut -> {signed}, then open it for import")
    if dry:
        return
    shell = {"WFWorkflowActionIdentifier": "is.workflow.actions.runshellscript",
             "WFWorkflowActionParameters": {
                 "UUID": str(uuid.uuid4()).upper(), "Shell": "/bin/zsh", "InputMode": "as arguments",
                 "Script": '"$HOME/.ai-context/save-clip.sh" "$@"',
                 "Input": {"Value": {"Type": "ExtensionInput"},
                           "WFSerializationType": "WFTextTokenAttachment"}}}
    shortcut = {
        "WFWorkflowActions": [shell],
        "WFWorkflowClientVersion": "2607.0.2",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59446},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": ["QuickActions"],
        "WFQuickActionSurfaces": ["Services"],
        "WFWorkflowHasShortcutInputVariables": True,
        "WFWorkflowInputContentItemClasses": ["WFStringContentItem", "WFRichTextContentItem",
                                              "WFURLContentItem", "WFImageContentItem"],
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowNoInputBehavior": {"Name": "WFWorkflowNoInputBehaviorGetClipboard", "Parameters": {}},
    }
    with tempfile.TemporaryDirectory() as tmp:
        unsigned = os.path.join(tmp, "unsigned.shortcut")
        with open(unsigned, "wb") as fh:
            plistlib.dump(shortcut, fh, fmt=plistlib.FMT_BINARY)
        subprocess.run(["shortcuts", "sign", "--mode", "anyone",
                        "--input", unsigned, "--output", signed], check=True)
    subprocess.run(["open", signed], check=True)
    log("  Shortcuts is asking to add it: click Add Shortcut (Replace if it already exists).")


def insert_rule(md_path, dry):
    rule = open(os.path.join(KIT, "RULE.md"), encoding="utf-8").read().strip()
    existing = open(md_path, encoding="utf-8").read() if os.path.isfile(md_path) else ""
    if RULE_SENTINEL in existing or BEGIN in existing:
        log(f"  rule already present in {md_path} (skip)")
        return
    log(f"  append rule -> {md_path}")
    if dry:
        return
    sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    with open(md_path, "a", encoding="utf-8") as fh:
        fh.write(f"{sep}{BEGIN}\n{rule}\n{END}\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="show what would change, change nothing")
    ap.add_argument("--no-shortcut", action="store_true", help="skip building and importing the shortcut")
    a = ap.parse_args()

    log("[clipper]")
    install_script(a.dry_run)
    write_config(a.dry_run)
    if not a.no_shortcut:
        build_shortcut(a.dry_run)

    claude_md = os.path.join(HOME, ".claude", "CLAUDE.md")
    if os.path.isdir(os.path.dirname(claude_md)):
        insert_rule(claude_md, a.dry_run)
    agents_md = os.path.join(HOME, ".codex", "AGENTS.md")
    if os.path.isdir(os.path.dirname(agents_md)):
        if os.path.realpath(agents_md) == os.path.realpath(claude_md):
            log("  ~/.codex/AGENTS.md -> CLAUDE.md symlink; rule already covered")
        else:
            insert_rule(agents_md, a.dry_run)
    if a.dry_run:
        log("(dry run: nothing changed)")


if __name__ == "__main__":
    main()
