# Publishing a design-doc PR: sibling conflicts and push verification

Load when a design doc reserves a namespace (ports, paths, subdomains, cron slots), constrains sibling designs, or is about to be pushed to the design repo.

## Sibling conflicts land in the same PR

- A design that reserves a namespace or otherwise constrains sibling designs is not publishable while an undeployed PROPOSED doc still claims a conflicting value. Sweep before opening the PR: fetch every sibling PROPOSED doc in full, grep each for the constrained tokens with word boundaries, and rewrite every violating claim in the SAME PR. Bump the sibling's Rev, add the amendment note to its header and verdict history, and update its DESIGN-INDEX row (Rev, ports, new sha).
- A sibling doc with an explicit reassignment clause ("first consensus wins; if another doc claims X first, this doc reassigns and re-records") is the mechanism for the renumber. A doc without one still gets the renumber under the new policy, recorded as a decision fold. Keep the sibling's historical sweep text as history; only assignments change.
- WITHDRAWN and ADOPTED docs are out of scope (dead letters and the grandfathered reality the policy fits around). The policy note for claim-free siblings lives in the DESIGN-INDEX Attributes column (the repo's designed place for per-doc attributes), not in per-doc body edits.

## Verify every content push by blob SHA

- GitHub content writes can silently drop the trailing newline of the intended file; markdownlint MD047 then fails CI on the missing final newline. Verify bytes after every push, not the call's success message: compute the intended file's git blob SHA1 (sha1 of `blob <len>\x00` + bytes) and compare it with the remote SHA that get_file_contents reports in its header line.
- Run `scripts/verify_blob_sha.py LOCAL_FILE [SPILL_FILE...]`: it prints both SHAs, warns on a missing final newline, and compares a saved spillover of the remote fetch (over-budget get_file_contents results are saved to a spillover path; pass it instead of re-fetching).
- On mismatch, diff the remote content against the local file to localize the drift before re-pushing; never re-emit blind. End inline content with a trailing newline every time.

## Code-search zero hits are weak evidence

The GitHub code-search index misses real hits and can match operator words as literal tokens. Never use a zero-hit search as proof that no file claims a token. For a token sweep, fetch the files in full and regex them locally; word-boundary patterns keep substring noise (port digits inside sha digests) out of the results.
