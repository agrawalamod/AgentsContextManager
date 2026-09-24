---
description: Read all of this project's threads and discussions and (re)write a detailed technical .llm/PROJECT_JOURNEY.md
---
Build or refresh `.llm/PROJECT_JOURNEY.md` for the current project: the single canonical, highly technical narrative of the work here. Manual command; run when you want the journey brought up to date.

## Sources to read (this directory's project)
1. `.llm/AGENTS_HISTORY.md` — the cross-agent thread ledger (Claude + Codex entries). Use it as the index of what threads happened.
2. Your own raw transcripts for THIS directory, for depth:
   - Claude: `~/.claude/projects/<slug>/*.jsonl`, where `<slug>` is this directory's absolute path with every non-alphanumeric char replaced by `-`.
   - Codex: `~/.codex/sessions/**/rollout-*.jsonl` whose `session_meta.payload.cwd` equals this directory.
   Read efficiently (extract user prompts, decisions, outcomes, files touched); do not dump whole transcripts into context. Dispatch a subagent for the heavy reading if your runtime supports it.
3. `.llm/slack-context.md` and `.llm/outlook-context.md` if present (project discussion outside the terminal).
4. Key repo docs: `CLAUDE.md` / `AGENTS.md`, `README*`, design docs, eval/result files, and the project memory index if any.
When a source and the code disagree, trust the code.

## What to write
First read the existing `.llm/PROJECT_JOURNEY.md` if present; treat it as the prior canonical narrative. If it already reflects every thread and nothing material has changed, do not rewrite it: say so and stop. Otherwise write the full updated document, preserving still-accurate curated content (especially the **dead-ends** section) and refreshing the rest. Never discard hand-written detail. The document has these sections, technical and specific (names, files, numbers, commit/CR ids where known):
1. **Read-this-first header** — one line on what this doc is, plus the rule "trust the code over this doc, then update this doc."
2. **One-paragraph orientation** — what the project is and the headline result/state.
3. **Current standing (dated)** — built/validated/shipped vs in-progress vs blocked.
4. **Problem and thesis** — the core problem and the approach's key idea.
5. **Approach in phases** — the system/method broken into phases, with the real files/modules.
6. **Chronological journey** — grouped by time/thread: what was done, why, and what was decided.
7. **Dead-ends already ruled out** — things tried that failed and must not be retried. This is the highest-value section.
8. **Open items / next** — unresolved work, in priority order.

## After writing
- Ensure the journey auto-loads next session:
  - Claude: add the line `@.llm/PROJECT_JOURNEY.md` to the repo-root `CLAUDE.md` (create a short one if none) if not already present.
  - Codex: add a "Read `.llm/PROJECT_JOURNEY.md` first" pointer near the top of `AGENTS.md` (create one if none), since Codex does not auto-import.
- Report a tight summary in chat: sections written, the biggest dead-ends captured, and the file path.

Arguments (optional focus, e.g. a subsystem): $ARGUMENTS
