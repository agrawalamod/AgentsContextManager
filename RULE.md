## Cross-Agent Directory History: the `.llm/` folder

Every working directory carries a `.llm/` folder shared by all agents (Claude, Codex), so context follows the directory rather than the agent or the thread. A new thread does not start blind. Files:
- `.llm/AGENTS_HISTORY.md` — append-only log of the threads worked in this directory.
- `.llm/PROJECT_JOURNEY.md` — curated technical narrative (why, dead-ends ruled out, current standing); present only where `/project_journey` has been run.
- `.llm/slack-context.md`, `.llm/outlook-context.md` — cached project comms (from `/slack-sync`, `/outlook-sync`).
- At the root only: `~/.llm/GLOBAL_AGENTS_HISTORY.md` — a consolidated map of every directory's log below it.

**On start.** Read `.llm/PROJECT_JOURNEY.md` first if it exists (the highest-signal source), then `.llm/AGENTS_HISTORY.md`. Skip for trivial one-off commands.

**On finish.** When you finish a substantive thread or reach a meaningful checkpoint, append one short entry (3 to 6 lines) to `.llm/AGENTS_HISTORY.md`. Do not edit or delete older entries. Newest at the bottom. Skip trivial work.

**Entry format:**

    ## <YYYY-MM-DD>: <short title> [<agent: Claude|Codex>]
    - Did: <what happened>
    - Decisions: <choices made, if any>
    - Open: <unresolved items or next step>
    - Files: <key paths touched>

**Routing.** At the root, read `~/.llm/GLOBAL_AGENTS_HISTORY.md` to see the whole landscape and decide which directory to work in. Directories tagged `(journey)` have a curated `PROJECT_JOURNEY.md`.

**Commands (available in both Claude and Codex).**
- `/project_journey` — read all of this project's threads plus its log and discussions, and write the detailed `.llm/PROJECT_JOURNEY.md`. Manual; run when you want the narrative refreshed.
- `/slack-sync` — cache this project's Slack channel(s) under `.llm/` (first run asks which channels).
- `/outlook-sync` — cache this project's relevant Outlook mail under `.llm/` (first run asks which senders/subjects/folders).
- `/update-agents-history` — append a curated entry for the current session to this directory's `.llm/AGENTS_HISTORY.md` on demand (manual counterpart to the exit hook).
- `/update-global-agents-history` — regenerate the root `~/.llm/GLOBAL_AGENTS_HISTORY.md` map (runs the rollup).

**Automation.** With the kit's hooks installed, a SessionStart hook auto-creates `.llm/AGENTS_HISTORY.md` (migrating any legacy root-level file) and injects the files above; a SessionEnd hook auto-appends a baseline entry at exit. You add a manual entry only to capture notable decisions the mechanical one would miss.
