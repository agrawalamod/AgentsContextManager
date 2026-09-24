Append a well-written entry summarizing THIS session's substantive work to `<cwd>/.llm/AGENTS_HISTORY.md`. Manual, agent-authored counterpart to the automatic exit-hook entry.

**Append-only, never overwrite.** Only add a new entry at the bottom. Never rewrite, reorder, edit, or delete existing content.

**Skip if nothing is new.** First read the current `.llm/AGENTS_HISTORY.md`. Do NOT append if any of these hold, and instead say so briefly and stop:
- the session did no substantive work in this directory;
- an entry for this session already exists; or
- everything this session did is already captured in the most recent entries.
Never force an entry just because the command was run.

## When you do append
1. Ensure `.llm/AGENTS_HISTORY.md` exists (SessionStart usually creates it; if missing, create it with a `# Agents History` header line).
2. Review what actually changed this session: files, decisions, problems solved, open items. Be specific and technical; do not pad.
3. Add ONE entry at the bottom, in this exact format:

        ## <YYYY-MM-DD>: <short title> [Codex]
        - Did: <what happened>
        - Decisions: <choices made, if any; omit the line if none>
        - Open: <unresolved items / next step; omit if none>
        - Files: <key paths touched; omit if none>

4. Keep it 3 to 6 lines. Report the entry you wrote, tightly, in chat.

Do not touch any other directory.

Optional focus/title: $ARGUMENTS
