# Fold-review fix batches — the producer-script pattern

Proven live Nov 15-16 2026 on the jumpbox-al2023-migration fold loop (rounds R8-R20; the loop closed at R20 with zero findings at every tag incl. NITs). Add a pointer to this file from SKILL.md when the skill is next edited.

## Why the pattern exists

Incremental patches to the doc's rev chain (L3) and verdict-history line (L4) bred a fresh bookkeeping defect nearly every round (wrong hop, misordered entries, unlanded claims, falsified tallies from a buggy format string, an em dash smuggled into a rebuilt line). The fix: stop patching, rebuild deterministically.

## The pattern

1. **One deterministic producer script** rebuilds the WHOLE lines(s) — its embedded strings are the FINAL text. No post-script hand edits, ever: a producer snapshot that predates the landed bytes becomes a staleness finding (the R18-4 class).
2. **In-script verification battery**, printed and exit-nonzero on failure: chain census (junction order, no dups, FINAL count, no self-references), L3↔L4 tallies cross-check (all rounds, incorporated-in = round+1 on both lines), the per-finding acceptance greps, em/en-dash and curly-quote census, line-count checks — beware trailing-newline off-by-ones with split('\n') (count lines via the written content, not the split length).
3. **Byte-snapshot before/after** (tmp copies), diff to prove the delta is exactly the named surfaces; reconstruction pins (splice the old lines back from the reviewer's r-NN side files, re-hash, match the prior pin) prove body stability stronger than code-path arguments.
4. **If the script's own battery catches a defect** (e.g. an em dash in new text), fold the fix into the script and re-run as the final pass — the on-disk script must carry the final text (the R18-4 acceptance: producer snapshot content == landed text, verified by string extraction and diff).
5. **Disclose parent-declared additions** beyond the prescription (row refs, range extensions) as declared edits in the round record, not as exceptions to hunt.
6. **Reviewer side files** (r-NN-L3.txt/r-NN-L4.txt) are the proven delta bases — keep until the loop closes, prune after.
7. **Under the zero-findings bar** (BLOCKER through NIT), convergence = each fix round shrinks the count; a clean round closes the loop. No manufactured noise: when nothing remains, the round record states CONSENSUS reached with zero findings.

## Decision-row bookkeeping

- Every section a decision row names as its effect must carry the change: a row pointing at a section with no corresponding note is a false record. Grep each named section for the decision's subject before dispatch.
- Renumber sub-numbered headings when a new subsection is inserted above an existing one; a fold must not read 0, 0.2, 0.1. Update every reference to the moved numbers in the same pass.
- Anchor a new decision block on the END of the last existing block, never on its opening line: an insertion keyed to the first line of the block above lands the new entry ABOVE it and the record reads out of order (M11 above M10), which the round bills as a bookkeeping defect.
- Settle the numbering of every NEW note or section before writing citations to it. A fold that cites a note number while that material still sits inside one combined entry forces a restructure mid-round, and the restructure is what the next round reviews instead of the content. Write the bodies first, then the cross-references.

## Sweeps over added lines

- A diff-based dash or vocabulary sweep flags pre-existing text that moved because its line was extended (a verdict-history line gaining a round entry, a Rev node relabelled to Prior). Read each hit's provenance before "fixing" it: rewriting retained text to satisfy the sweep corrupts the record. Declare the retained occurrences as expected exceptions in the reviewer dispatch instead.
- Sweep the REPLACEMENT strings before applying a batch, not only the doc after: a fixer's own fresh phrasing is where the tells return, and a pre-apply catch costs nothing while a post-apply residue pass costs a round.

## Fix-added commands and gates are executed, not just written

- Run every command a fix round adds, against real data, before dispatch: check the exit
  code and the hit counts. A grep gate without `-r` errors on a directory and reads as a
  clean tree; without `-i` it misses capitalised names; a gate that false-positives on
  generic content (bare loopback addresses, common words) can never pass.
- Read the implementation of every flag a fix round cites. A flag that exists can mean the
  opposite of what the prose assumes: `hermes skills install --force` is the security-scan
  override, not a reinstall, so a "reinstall" step written with it silently tells the
  operator to bypass the guard.
- An evidence claim ("captured", "recorded") must name a capture that actually contains
  the claim. When no capture does, mark the figure unverified and put the live re-check in
  the runbook; an install record is provenance for a figure, not evidence of it.
- Calibrate list-based gates: an entry that is a prefix of a legitimate name (a private
  repo name `jump-box` against a skill `jump-box-ops`) blocks its own subject. State the
  prefix rule beside the list and test each entry against the shipped names.
- When a fix adds a gate, the fix-verification dispatch names its expected hit set (what
  must match, what must not), so the next round tests calibration instead of existence.

## Publish handoff

The fold publish is a separate deterministic pass (hermes-cron-script-jobs → references/relay-pattern.md, "Design-repo publish payloads: recurrence traps"): fresh /tmp clone, feature branch BEFORE committing, row edit as an idempotent fragment replacement on main's current copy, CI gate on the Actions runs API + mergeable_state, squash merge, byte-verify via cat-file, local-tree sync, branch cleanup.
