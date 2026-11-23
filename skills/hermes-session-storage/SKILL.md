---
name: hermes-session-storage
description: "Use when diagnosing Hermes session storage or vanishing."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, sessions, state-db, sqlite, lineage, desktop, debugging, diagnostics]
---

# Hermes Session Storage & Lineage

Diagnosing how sessions are stored, related to each other, and why one does (or
doesn't) show up in a surface's session list.

## When to Use

- A session "disappeared" from the desktop/TUI/CLI list, or "keeps disappearing".
- You need to trace a session's lineage (parent/child/compression/branch/reset).
- You're debugging "session not found", vanishing history, or orphaned rows.
- You need to surgically repair a session row's `model_config` markers in
  `state.db`.

## Where things actually live

- **`~/.hermes/state.db`** (SQLite + FTS5) is the canonical session store — the
  `sessions` table. All surfaces (CLI, TUI, desktop, gateway, cron) read here.
  Resolve the real home via `$HERMES_HOME`, never hardcode `~/.hermes`.
- **`~/.hermes/sessions/sessions.json`** is a *legacy mirror* of the gateway
  routing index (maps `agent:main:<platform>:...` → active session id). It is
  **NOT** the session list. Do not read it to debug "my session vanished".
- Relevant tables: `sessions`, `messages`, `messages_fts*`, `gateway_routing`,
  `session_model_usage`, `async_delegations`, `schema_version`.

## Key `sessions` columns

`id` (PK), `source` (desktop/tui/cli/signal/telegram/cron/subagent/tool/…),
`parent_session_id`, `started_at`/`ended_at`/`end_reason`, `title`, `hidden`,
`archived`, `pinned`, `rewind_count`, `model_config` (JSON; **holds lineage
markers**), `session_key`, `profile_name`, `last_activity_at`, `system_prompt`.
Note the UNIQUE index on non-null `title` — two sessions can't share a title.

## Lineage + visibility model (the important part)

A session's *identity* is not one thing. Desktop AGENTS.md calls out three:
durable navigation id, runtime streaming id, and lineage root. Conflating them
is the recurring cause of "session not found" / "vanishing history".

Lineage is encoded with `parent_session_id` **plus** a `model_config` marker:

| Marker in `model_config` | Written by | Meaning | Listable? |
|---|---|---|---|
| `_delegate_from` | `tools/delegate_tool.py` (delegate_task spawn) | spawned subagent | **hidden** |
| `_branched_from` | `/branch` (explicit fork) | alternate conversation branch | yes (nested) |
| `_reset_from` | session reset / switch | reset continuation | yes |
| (none; parent `end_reason='compression'`) | `publish_compression_child` | compression continuation | hidden from list, projected onto root's tip |

`list_sessions_rich` (default `include_children=False`) shows only **roots**
(`parent_session_id IS NULL`) plus branch/reset children (`_LISTABLE_CHILD_SQL`),
AND additionally requires `json_extract(model_config,'$._delegate_from') IS NULL`.
So any row carrying `_delegate_from` is filtered out no matter what else is true.
See `hermes_state_common.py` `_LISTABLE_CHILD_SQL`/`_BRANCH_CHILD_SQL`/
`_RESET_CHILD_SQL` and `hermes_state.py::list_sessions_rich`.

`project_compression_tips=True` (default) projects a compression-chain root
forward to its live continuation, so one logical conversation = one list entry.

## Pitfalls

- **The "keeps disappearing" symptom is usually *persistent*, not flaky.** A
  session renders when it's the foreground/running chat (a separate path), but
  is absent from the list on every refresh. That's a filtered-out row, not a
  race — the filter just looks intermittent.
- **Compression copies `model_config` verbatim onto the continuation**, so a
  delegate's compression-continuation inherits `_delegate_from=<delegate's
  parent>` and stays hidden even though it's now a real continuation.
- **Clearing `_delegate_from` alone is NOT enough** to make a row listable: if
  it's still a child with no `_branched_from`/`_reset_from` marker and its
  parent didn't end `'branched'`, it still falls into the "ephemeral child"
  bucket. You must also `parent_session_id = NULL` (make it a root) or add a
  `_branched_from` marker.

## Diagnostic workflow

1. Confirm the row exists and inspect its markers:
   `sqlite3 state.db "SELECT id, source, parent_session_id, end_reason, hidden,
   archived, pinned, substr(model_config,1,300) FROM sessions WHERE id='<id>';"`
2. Classify it with `scripts/classify_session.py <id>` (see
   `references/visibility-rules.md` for the exact SQL predicate and writer
   call-sites).
3. The predicate that answers "is this listable?":
   `(parent IS NULL OR _branched_from IS NOT NULL OR parent.end_reason='branched'
   OR _reset_from IS NOT NULL) AND _delegate_from IS NULL`.
4. If it's a real conversation wrongly carrying `_delegate_from`, fix with a
   backed-up update; see `references/visibility-rules.md` for the exact SQL.

See `references/visibility-rules.md` for the precise SQL and the source line
numbers backing each rule.