# Session visibility rules — exact SQL + source backing

## The listable predicate

`hermes_state.py::list_sessions_rich` (default `include_children=False`) ANDs
two things, so a row is shown only if BOTH hold:

1. It is a root or a user-visible child — `_LISTABLE_CHILD_SQL`
   (`hermes_state_common.py:260`):

   ```sql
   s.parent_session_id IS NULL
   OR _BRANCH_CHILD_SQL   -- _branched_from set, OR parent ended 'branched' after child started
   OR _RESET_CHILD_SQL    -- _reset_from set, OR child shares parent's session_key on a reset reason
   ```

2. It is not a delegate subagent (`hermes_state.py:10486`):

   ```sql
   json_extract(COALESCE(s.model_config,'{}'), '$._delegate_from') IS NULL
   ```

so `_delegate_from` rows are hidden unconditionally.

## Marker definitions (all in `hermes_state_common.py`)

- `_BRANCH_CHILD_SQL:176` — `_branched_from IS NOT NULL` OR parent with
  `end_reason='branched'` and `child.started_at >= parent.ended_at`.
- `_COMPRESSION_CHILD_SQL:185` — parent `end_reason='compression'`.
- `_RESET_CHILD_SQL:252` — `_reset_from IS NOT NULL` OR shared non-empty
  `session_key` + parent ended with a reset reason (session_reset, session_switch,
  idle, daily, suspended, resume_pending_expired).
- `_LISTABLE_CHILD_SQL:260` — `parent IS NULL OR branch OR reset`.
- `_ephemeral_child_sql:266` — child that is NOT branch/compression/reset
  (i.e. subagent runs and clean compression continuations).

## Marker writers

- `_delegate_from` ← `tools/delegate_tool.py:2052` (delegate_task spawn only):
  `child._session_init_model_config["_delegate_from"] = parent_sid`.
- `_branched_from` ← `/branch`.
- `_reset_from` ← session reset/switch.

## The trap that bites

Compression rotates a session and copies `model_config` verbatim onto the
continuation (`publish_compression_child` callers pass
`agent._session_init_model_config`). So a delegate's continuation carries
`_delegate_from=<the delegate's own parent>` and is hidden even though it is a
real continuation — see `hermes_state.py:13352` and `:6896` comments.

## Fix SQL for a wrongly-marked conversation

Back the row up first, then promote it to a normal top-level session:

```sql
-- snapshot
SELECT * FROM sessions WHERE id='<id>';

UPDATE sessions
SET parent_session_id = NULL,
    model_config = json_remove(model_config, '$._delegate_from')
WHERE id = '<id>';
```

Only removing `_delegate_from` is *not* enough: a parented row with no branch/
reset marker is still an ephemeral child. Nulling `parent_session_id` makes it a
root (always listable). Alternative that preserves lineage: set
`json_set(model_config,'$._branched_from', parent_session_id)` to make it a
listable branch child nested under the parent.

## Worked example (Aug 2026)

Session `20260828_174934_3dcaf4` ("Z13 next steps") kept vanishing from the
desktop sidebar. Forensics:

- It was a child of `20260828_170013_bd4d1d` (parent_session_id set), parent
  end_reason NULL, and `model_config` held `_delegate_from = 20260828_170013_bd4d1d`.
- The predicate `(root OR branch OR reset) AND _delegate_from IS NULL` evaluated
  to 0 → invisible. It rendered only as the active foreground chat (a separate
  path), so it looked like it "kept disappearing".

Classification of the same marker data + the empirical `visible_in_list` check is
in `scripts/classify_session.py`.