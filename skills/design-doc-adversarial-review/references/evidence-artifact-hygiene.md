# Evidence artifact hygiene: listings, timestamps, and the sweep set

Rules for the artifact files a review loop creates or edits (evidence captures, backup-dir files,
batch-list headers, kit-side READMEs). Each has bitten in a loop; pitfalls.md carries the doc-side
counterparts, this file the artifact-side ones (pitfalls.md was at its size cap when these landed).

## Listings

- **Never hand-compose an artifact listing (sizes, stamps, row sets) — generate it with real `ls`
  output from a staged script.** Hand-composed rows drift from disk on exactly the details a
  reviewer stat-checks (a count, a byte size, a stamp), and each drift is its own round. The drift
  class survives multiple rounds when the composed rows look plausible: pre-edit knowledge leaks
  into post-edit rows.
- **When a fix round edits any file a listing captured, REGENERATE the listing in the same batch**
  and widen the doc's capture-time window to the new stamp. A window that excludes the newest
  capture (or a capture stamped with a vague 'x' minute) re-teaches the staleness the fix was
  supposed to close.
- **Keep the generator script** beside the listing (non-evidence row in the manifest): the next
  regeneration is then one command, and the script documents the extraction boundary (which
  directories, which columns).

## Timestamps

- **Treat Proton's server-side `uploaded` field as the authoritative upload time.** Hand-converting
  an epoch mid-loop to a wall-clock claim has produced a falsified stamp (reviewer MAJOR) when the
  conversion was wrong; cite the field's own rendered time from a fresh `get`.
- **Where the sandbox clock is known to jump across container resets, disclose the drift once and
  demote every file-name timestamp (backup-label suffixes, `-1437`-style names) to labels rather
  than UTC claims.** A doc whose 'after the last change' blanket rests on a drifted clock is false
  under its own reading; restamp the governing change from file mtimes instead.

## Sweep set

- **The unslop/dash sweep set is every file the fix round created or edited, not just the doc.**
  Backup-directory READMEs, batch-list headers, and kit-side artifacts written during the loop
  carry the same em-dash and AI-tell risk; grep the round's whole edit surface before dispatching.
- **When a reviewer records an out-of-scope observation, close it in the next fix round** instead
  of leaving it for a later sweep to find again — an observation the fix list ignores returns as a
  full finding.

## Screenshots the user pastes into chat

- **A user-attached screenshot is an evidence capture, not just an illustration — land it as a
  numbered capture with the mechanics it deserves.** The files arrive in the sandbox under the
  sandbox HOME's `.hermes/images/<upload-id>.png` (the sandbox HOME, not the shared mount's
  `.hermes`); copy them into the evidence dir, chmod 644 (they land root-owned 0600 on the shared
  tree, unreadable by the host user), write the capture note (source, what each screen establishes,
  cross-verification against any box-side capture of the same facts), and add the manifest row in
  the same pass — a screenshot left in the chat thread is unverifiable next round, same class as
  evidence living only in a comments file.
- **Respect reserved capture numbers when numbering new evidence** — a doc may reserve the next
  P-number for a later phase's reads; scan the doc for the reservation before assigning, and take
  the next free number past it.
- **Do not embed key digests in fact-store rows** — the store's credential classifier rejects
  fingerprints and pin-adjacent numerals as secrets and burns retries; state that the digest is
  verified and cite the evidence file that carries it.

## Recovery/backup artifacts (ADB device work)

- **Pair each batch list to its recovery JSON from the JSON's own recorded `list` field** — the
  JSON file names are content hashes, not batch numbers, and creation order does not follow batch
  order; a guessed pairing falsifies the doc and the backup README at once.
- **Recovery JSONs record already-disabled packages too** (their package count exceeds the batch
  list's line count): attribute disables to the step that actually did them (an installer can
  disable a list entry first) from the installer's own log, not from the JSON's package count.
- **Finalize a backup directory (README, batch lists, recovery copies) BEFORE tar+upload** — a
  directory amended after the tarball makes the uploaded copy point-in-time; either re-tar or state
  the point-in-time scope in the README and in every doc that cites the tarball.
- **Never hand-compose a backup-directory listing either** — the same generator rule applies, and
  the generator doubles as the drift check (diff the regenerated listing against the doc's rows).
