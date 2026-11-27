# Strava API change watchlist

Deadline-driven API changes and their stack status. Update items in place; do not fork a file per review.

## Open items

### Base URL switch to api-v3.strava.com — due before June 1, 2027
- Changelog (June 1, 2026 entry): base URL moves from `https://www.strava.com/api/v3` to `https://api-v3.strava.com`; new host available **January 4, 2027**. Old host serves until the switch deadline (verify the exact cutoff on the changelog when planning).
- Stack status: PREP DONE Nov 19, 2026 — PR #59 merged (squash `5a343193`): `client.py` reads `STRAVA_API_BASE_URL` (default = old URL; a scheme-less value refuses to boot). Remaining step is the FLIP on/after Jan 4, 2027: add `STRAVA_API_BASE_URL=https://api-v3.strava.com` to `/home/mcp/env/strava.env`, recreate the quadlet, confirm the boot log line `strava api base url`, one read smoke. Rollback = remove the line and restart. Verified Nov 19: api-v3.strava.com does NOT resolve yet (curl rc=6) — do not flip early.

### 64-bit identifiers (activity/athlete `id`) — deadline June 1, 2027
- Reviewed Nov 19, 2026 (fact 638): verdict NO change needed. `id_str` already live in payloads (store-verified). Python json exact, SQLite INTEGER 64-bit, ids cross boundaries as strings, store.py integer asserts stay.

### Tokens headers-only — deadline June 1, 2027
- Already compliant: `client.py` sends `Authorization: Bearer` header only (verified in source Nov 19, 2026).

### /oauth/deauthorize → /oauth/revoke — deadline June 1, 2027
- N/A: the 8016 server never calls deauthorize (source-verified Nov 19, 2026).
