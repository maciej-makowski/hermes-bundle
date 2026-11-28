# Derived trial docs and their fix-round sweep surfaces

Depth for two situations that recur on derived designs: a child doc that trials an external product instead of building the parent design, and the sweep surfaces a fix round must move or the next reviewer bills it as a partial fix.

## Derived trial docs (a parent open question picks an external product)

When the operator answers a parent design's open question by choosing a trial of an external product
instead of the parent's build path, write a derived design rather than editing the parent. The
child quotes the decision and the parent rev in its decision record, states the relationship (the
trial is the v1 path; the parent build is the fallback if the trial fails), and does not re-argue
the parent's locked decisions.

- Pin the product at the catalog's reviewed version and commit; install by bare catalog name so the
  pin applies, and gate on the install metadata's revision plus the installed `plugin.yaml`
  version. `owner/repo` is a Git source and skips the reviewed pin.
- Read the product's OWN environment-knob table for worker, precommit and review timers. Hermes
  profile settings (`agent.gateway_timeout`, `agent.max_turns`) do not lift a plugin's own caps: a
  four-hour profile timeout next to a one-hour plugin reaper still kills the worker at one hour.
  Put both layers in the settings table.
- Verify every command against the product's CLI list at the pinned commit, and every behaviour
  claim against a capture from that commit. A product in beta is an honest note, not a pass: state
  what was not executed.
- The trial protocol is part of the doc: success criteria with a measured baseline, failure
  criteria, a fixed decision date, and a rollback that keeps the product's own database as the
  audit trail. The database is rarely under the plugin's workspace directory; read the storage path
  from the product's env table.

## Fix-round sweep surfaces (first-class)

A fix round is not done when the named findings are edited. Three surfaces must move in the same
pass or the next reviewer bills them as partial fixes:

- **The header.** Bump the Rev cell and append the round's tally to the verdict-history line at the
  FIRST fix round, not only at close; a doc still marked "Rev 1, not reviewed" after a review
  round is a finding.
- **The canonical examples.** When a fix states a wrapper or custody rule ("every gate runs through
  W"), grep every example, fenced command and card-schema row for the bare form and update them
  too. A canonical example that teaches the violation is a MAJOR next round.
- **The evidence manifest's claims index.** Every fixed value that a claims row states must be
  corrected in the same pass; the doc sweep does not reach the manifest, and a stale claims row
  sends the next round to re-derive the pre-fix claim.
