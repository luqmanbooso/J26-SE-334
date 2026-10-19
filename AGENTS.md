# AGENTS.md — HEART (J26-SE-334) Context Map Protocol

## Context map (read this first, every session)
This project's shared memory lives in `context/`, an Obsidian vault of small linked notes. Before any planning or implementation task, invoke the `context-map` skill (explicitly with `$context-map` if you're not sure it triggered) and follow its orientation + update protocol exactly.

## Hard rules
- Never read or grep the whole codebase to "catch up." Navigate via `context/CONTEXT-MAP.md` and its links instead.
- Every completed task must update the context map (per the skill's update phase) before the turn ends — this is not optional cleanup, it's part of the task.
- If `context/` and the actual code disagree, the code is ground truth — fix the note, and mention the fix in the day's log entry.
- Every note title in `context/` is unique vault-wide; never create a duplicate title.
