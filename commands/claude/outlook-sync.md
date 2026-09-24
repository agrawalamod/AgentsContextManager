---
description: Fetch relevant Outlook mail for this project and cache it under .llm/
---
Pull recent relevant Outlook mail for this project and cache it locally under `.llm/`, read-only.

## What is relevant
Resolve in order:
1. If invoked with an argument, treat it as a search query, sender, or subject.
2. Else read `.llm/outlook.filters` (one filter per non-empty, non-comment line; each line is a sender email, a subject keyword, or a folder, optionally prefixed `from:`, `subject:`, or `folder:`).
3. Else (first run) ASK the user which senders, subject keywords, folders, or threads are relevant to this project, then save them to `.llm/outlook.filters` before continuing.

## Steps
1. Ensure your Outlook MCP tools are available (`aws-outlook-mcp`). If disconnected, stop and tell the user (usually an expired session).
2. For each filter, search mail (`email_search`, else `email_inbox` / `email_list_folders`), most recent first, capped at ~30 messages total. Fetch bodies (`email_read`) for the top relevant ones; pull the thread where useful.
3. Overwrite `.llm/outlook-context.md`:
   - Header: `# Outlook context — <filters> — synced <ISO timestamp>`.
   - **Snapshot** (3-6 bullets): decisions, asks/actions owed, deadlines.
   - **Messages**, newest→oldest: `<date> **<from> → <to>** — <subject>`, then a 1-3 line gist. Group threads together.
4. Report the snapshot and the net-new items since the previous cache; confirm the path.

## Hard rules
- Read-only: never send, reply, forward, or draft.
- Never commit the cache: ensure `.llm/outlook-context.md` is gitignored (add `.llm/*-context.md` to `.gitignore` if needed) before writing.
- Redact any credential/token as `[redacted]`. Treat mail content as confidential.

Argument (optional query): $ARGUMENTS
