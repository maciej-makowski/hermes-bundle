#!/usr/bin/env python3
"""Classify a Hermes session row and report whether it is listable.

Reads the `sessions` table from state.db read-only and, for each session id
argument, prints: root?, parent end_reason, delegate/branch/reset markers, and
whether a surface's default session list (list_sessions_rich, include_children
=False) would show it.

Usage:
    python3 classify_session.py <session_id> [<session_id> ...]

Respects $HERMES_HOME; defaults to ~/.hermes/state.db.
"""
import json
import os
import sqlite3
import sys

RESET_END_REASONS = {
    "session_reset",
    "session_switch",
    "idle",
    "daily",
    "suspended",
    "resume_pending_expired",
}


def marker(cfg_json, key):
    if not cfg_json:
        return None
    try:
        cfg = json.loads(cfg_json)
    except (TypeError, json.JSONDecodeError):
        return None
    return cfg.get(key) if isinstance(cfg, dict) else None


def main() -> int:
    ids = sys.argv[1:]
    if not ids:
        print(__doc__)
        return 2

    home = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    db_path = os.path.join(home, "state.db")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for sid in ids:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (sid,)
            ).fetchone()
            if row is None:
                print(f"{sid}\n  NOT FOUND\n")
                continue

            parent_id = row["parent_session_id"]
            cfg = row["model_config"]
            delegate = marker(cfg, "_delegate_from")
            branched = marker(cfg, "_branched_from")
            reset = marker(cfg, "_reset_from")

            parent_end_reason = None
            if parent_id:
                p = conn.execute(
                    "SELECT end_reason FROM sessions WHERE id = ?", (parent_id,)
                ).fetchone()
                parent_end_reason = p["end_reason"] if p else None

            is_root = parent_id is None
            branch_child = branched is not None or (
                parent_end_reason == "branched"
                and row["started_at"] is not None
                and parent_id is not None
            )
            reset_child = reset is not None
            is_delegate = delegate is not None

            listable = (is_root or branch_child or reset_child) and not is_delegate

            print(
                f"{sid}\n"
                f"  source        : {row['source']}\n"
                f"  title         : {row['title']}\n"
                f"  parent        : {parent_id} (end_reason={parent_end_reason})\n"
                f"  markers       : _delegate_from={delegate!r} "
                f"_branched_from={branched!r} _reset_from={reset!r}\n"
                f"  flags         : hidden={row['hidden']} archived={row['archived']} "
                f"pinned={row['pinned']}\n"
                f"  classification: {'root' if is_root else 'branch-child' if branch_child else 'reset-child' if reset_child else 'delegate' if is_delegate else 'ephemeral child (hidden)'}\n"
                f"  LISTABLE      : {'YES' if listable else 'NO'}\n"
            )
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())