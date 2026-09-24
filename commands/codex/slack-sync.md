Pull recent conversation from this project's Slack channel(s) and cache it locally under `.llm/`, read-only.

## Which channels
Resolve in order:
1. If invoked with an argument, treat it as a channel name (strip a leading `#`) or an ID (starts with `C`).
2. Else read `.llm/slack.channels` (one channel name or ID per non-empty, non-comment line).
3. Else (first run) ASK the user which Slack channel(s) are relevant to this project, then save them to `.llm/slack.channels` (one per line) before continuing.

## Steps
1. Ensure your Slack MCP tools are available (`slack-mcp`). If disconnected, stop and tell the user (usually an expired session).
2. Resolve each channel name to an ID (`search in:#<name>` or `list_channels`) if you were given a name.
3. Fetch history: `batch_get_conversation_history`, limit 30 (widen if asked, or pass `oldest` for a window). Pull `batch_get_thread_replies` for any message with a non-zero `reply_count`.
4. Resolve `<@U…>` / `<@W…>` mentions to human names via `batch_get_user_info` (batch all unique IDs in one call).
5. Overwrite `.llm/slack-context.md`:
   - Header: `# Slack context — <channels> — synced <ISO ts of newest message>`.
   - **Snapshot** (3-6 bullets): current decisions, open blockers, who owes whom what.
   - **Transcript**, oldest→newest, one line per message as `<date time> **<name>**: <text, mentions resolved>`, thread replies indented under their parent.
6. Report the snapshot and the net-new items since the previous cache (diff if it existed); confirm the path.

## Hard rules
- Read-only: never `post_message`, react, or draft.
- Never commit the cache: ensure `.llm/slack-context.md` is gitignored (add `.llm/*-context.md` to `.gitignore` if needed) before writing.
- Redact any credential/passcode/token in messages as `[redacted]`.

Argument (optional channel): $ARGUMENTS
