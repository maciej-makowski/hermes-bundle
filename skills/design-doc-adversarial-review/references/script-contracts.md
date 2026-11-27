# Script contracts in design docs

A design that specifies an installer, updater or bootstrap script is specifying a CLI
driver. Prose about flags is where review loops bleed rounds: each unverified flag returns
as a MAJOR, and the fix round's fresh wording generates the next round's findings.

## Rules

1. **Pin every command and flag against the tool's source before the first dispatch.**
   Not the docs page alone when the source is available: a flag's help text and its code
   path can disagree.
2. **When the invocation cannot be settled yet, specify invariants, not commands.**
   State what must be true after the step (installed, enabled, source recorded, scan ran)
   and let implementation settle the exact argv with a test. A guessed argv reads as a
   promise and gets reviewed as one.
3. **Non-interactive means every prompt needs its flag.** A CLI that hits an unanswerable
   prompt can cancel and exit 0 having done nothing. The contract must pass the
   non-interactive flags AND assert post-conditions, never trust exit codes.
4. **Post-conditions are the contract's teeth.** Name the read-back per component type
   (a list row exists and is enabled, a hub-only list shows the skill, a file hash
   matches) and what state counts as success in each mode (for example installed and
   disabled under a no-enable run).
5. **One list, edited whole.** A fix that rewrites one bullet of the script contract
   leaves its siblings stale. Re-read the entire list after each edit and re-derive every
   command's flags from the current text, not from memory of the previous version.

## Flag semantics that have bitten

- `hermes skills install --force` is the Skills Guard override ("install despite blocked
  scan verdict"), not a reinstall. A reinstall is uninstall then install, so the scan runs.
- `--yes-deps` answers the Python dependency consent prompt only. Publish and enable are
  separate steps; the enable step is itself the consent path that admits a disabled
  plugin's Python deps. Node sidecar consent is separate and has no flag.
- `hermes plugins update` with no name, Desktop update-all and auto-update skip subdirectory
  installs (provenance class DRIFT). Per-name updates are the only path that moves them.
- A `--ref` pin refuses update until `--force --ref <new sha>`.
- `--force` on a plugin install also accepts a `caution` scan verdict without a prompt;
  a `dangerous` verdict stays blocked. Say so where the script passes it.
- `hermes skills list` includes bundled and local skills; guards and post-checks must use
  `--source hub`.

## Verification

Run the tool's own validator against the finished plugin or package
(`hermes plugins validate <dir>`), and re-run the design's post-condition commands against
real state before claiming the contract is proven. A contract reviewed only as prose is
unverified.
