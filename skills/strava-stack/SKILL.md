---
name: strava-stack
version: 1.0.0
description: Use when working on the Strava MCP server or local store.
author: Hermes Agent (the operator)
license: MIT
tags: [strava, mcp, activity-store, api]
metadata:
  hermes:
    tags: [strava, mcp, activity-store, api]
---

# Strava stack: MCP server (8016), local activity store, API access

## When to Use

Any work on the Strava MCP server or its local activity store (mcp-stack monorepo): sync/backfill operation, store queries, rate-budget decisions, deploy verification, or reviewing a Strava API change against the stack. Dated project state lives in the fact store; the repo README + design docs are the source of truth for internals — this skill carries the routing, the always-on rules, and the review procedure.

## Deployment map (routing only)

- Monorepo `<your-org>/mcp-stack`, `strava/` subtree (`strava_mcp/`: client, oauth, rate, store, sync, tools). Rootless podman quadlet under the nologin user `mcp`; HTTP on 127.0.0.1:8016 (garmin next door on 8017).
- Store root `/app/store` in the container = host `/home/mcp/strava-store`: `index.db` (SQLite, WAL, rebuildable) + flat per-activity JSON (`activities/<id>/{summary,detail,streams}.json`, plus gear/athlete/stats/zones/segments/routes). Files are primary; JSON payloads are archived VERBATIM, so new upstream fields appear in stored payloads automatically.
- Sync: one asyncio task inside the server process. Tiers frequent (6 h default) / slow (24 h) / sweep (7 d) / backfill (trigger-only, resumes from a persisted cursor). Every request shares ONE rate guard and ONE token writer with tool traffic. `STRAVA_SYNC_ENABLED` ships false; only the `strava_sync` trigger action starts the first population.
- `read_all` scope (attended re-authorization) gates the segments/routes tiers.
- Sync knobs live in `/home/mcp/env/strava.env` (0600, mcp-owned — edits are the operator's hand): `STRAVA_SYNC_ENABLED` (the go-card), `STRAVA_SYNC_FREQUENT_HOURS` / `_SLOW_HOURS` / `_SWEEP_DAYS` / `_BULK_CAP`, and `STRAVA_OAUTH_SCOPES` (the string the attended re-auth extends with `read_all`).

## Always-on rules

- Read from the store first: `strava_activities` with `source: "store"` answers list/get/streams with ZERO API requests. Only hit the live API when the store cannot answer — the rate budget is shared with the sync's bulk cap, and sync traffic loses its slot when tool traffic eats it.
- A stalled backfill is diagnosed from `strava_sync` status, never from logs: the failing batch's `outcome` + `note` carry the exception type and message. Upstream-404 items (an activity flagged/removed between the list walk and its detail fetch) are marked deleted locally by design — files stay, the sweep's list membership revives the row if the summary content changes — and a streams-404 (manual/no-sensor entry) stores an `{"unavailable": true}` marker; neither blocks a batch. Any other per-item error stays pending for the next tier run.

## Backfill verification (after any bulk backfill)

1. **Completion gate**: a fresh list walk through the API path (4 pages/call, 100/page, until a short page) must count exactly the store's `activities` total, then 5 random ids spot-checked `api detail` vs `store detail` on id/name/distance/moving_time/start_date. All match → the gate passes; a count mismatch means the sync's watermark or list walk missed something — re-check the sweep before declaring done.
2. **Streams gate**: a stored GPS-bearing activity's `streams.json` must contain `latlng` — it proves the STREAM_KEYS fix (heartrate spelling + CSV encoding) is actually in the deployed image. A missing latlng halts the backfill until the image is fixed.
3. **Daily watch**: a no-agent cron can automate both checks daily (status read + the streams gate) — the script-install route and the loopback call recipe live in the cron relay skill's reference; retire the watch once the completion gate passes, keep it alive for any re-backfill.
4. **Sizing reality**: the `detail.json` payloads (include_all_efforts) dominate per-activity storage — the store measured ~300 MB at ~1,900 activities, roughly twice the streams-only estimate; size disk checks and the offsite row on details, not streams.
- Route ALL store reads through the MCP tools; the store directory lives in the mcp user's home and is not visible to the agent sandbox, so local file reads of the store path are a dead end by construction.
- After any deploy, re-verify the served schema (tool_describe) before calling strava tools from a session older than the restart — a pre-restart registry keeps the old action enum and client-side validation rejects new actions outright.
- store.py asserts integer ids (`isinstance(..., int)`). Keep them: Strava keeps `id` numeric and adds `id_str` beside it — never widen the asserts to accept string ids.

## API-change email review (trigger: a Strava developer email worth reviewing)

1. Fetch: proton_mail `search` {query} → `get` {id}; the body is one HTML blob — read the requirement + deadline out of it.
2. Verify against the LIVE payload first: one `source: "store"` read of a known activity shows which fields already ship. The live payload is ground truth for "live now"; a fetched changelog page can omit the newest entries while a web_search snippet of the same URL shows them — when they disagree, trust the payload.
3. Check the official changelog (developers.strava.com/docs/changelog/) for the requirement + deadline.
4. Impact test, four layers: JSON layer (Python parses 64-bit ints exactly — the JS >2^53 failure mode does not apply), SQLite layer (INTEGER PRIMARY KEY is signed 64-bit), boundary layer (ids only cross as strings: dir names, URL paths), assert layer (store.py integer asserts vs the API's field type). All four pass → verdict "no change needed".
5. Record verdict + deadline as a fact; move any pending item into `references/api-change-watchlist.md`.

## Watchlist pointer

`references/api-change-watchlist.md` — deadline-driven Strava API items and their stack status. Update in place as items land or get done; never fork a new file per review.
