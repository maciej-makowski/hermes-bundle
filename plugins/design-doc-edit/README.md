# design-doc-edit

Two editing tools for long design documents, built so an edit either lands exactly as
counted or does not land at all.

| Tool | What it does |
|---|---|
| `doc_replace` | One literal or regex replacement, occurrence-count checked, written atomically (temp file + rename, mode preserved, owner preserved when the process may chown). |
| `doc_batch` | Many replacements in one call, applied in order against the evolving content, all-or-nothing. |

## Why

`patch` and `write_file` are fine for code. On a 500-line design doc under review, the
failure that hurts is a find string that matches twice: the edit lands in the wrong place,
or a rewrite silently duplicates a paragraph. These tools refuse that edit and tell you
the count.

They are also prompt-free by construction: the scope check is code, not a model decision.
Every call, success or failure, appends one JSON line to `log/edits.jsonl` next to the
plugin.

## Install

```bash
hermes plugins install maciej-makowski/hermes-bundle/plugins/design-doc-edit --enable
```

The toolset is `design_doc`. It registers no hooks and starts no processes.

## Scope

The target's real path must sit under one of the roots in `roots.json` next to the
plugin. Without that file the default is `/home/hermes/hermes-designs`:

```json
["/home/hermes/hermes-designs"]
```

Protected paths are always refused: `.env`, `.env.*`, `*.env`, `.envrc`, and any path
inside a `.git` directory or a file named `.git`. Files over 8 MB, non-UTF-8 files, and
batches over 200 edits are refused.

`roots.json` and `log/` are user state. They are not in this repository and survive
reinstalls. A malformed `roots.json` (invalid JSON, an empty list, or a non-string entry)
fails closed: no path is allowed, and the refusal is written to the audit log as a
`roots_invalid` event.

## Behaviour

- Literal edits default to `expected_count: 1`; a different count refuses and writes
  nothing.
- `regex: true` requires an explicit `expected_count`.
- `doc_batch` applies edits in order; if any count check fails, no part of the batch is
  written.
- A successful call returns the new file sha256 and a reminder to re-read the file before
  further `patch` or `write_file` edits, because those tools cache reads.

## Tests

```bash
python3 -m unittest discover -s plugins/design-doc-edit/tests -v
```

## Licence

MIT. See the repository LICENCE.
