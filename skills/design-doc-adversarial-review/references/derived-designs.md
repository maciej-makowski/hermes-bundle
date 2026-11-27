# Derived design docs and first-round checks

Depth for a child design that follows a parent decision (a trial of an outside tool) and for the two checks that cost a round when missed. SKILL.md is at its size cap; this file is the home for these rules.

## Derived design docs (a parent decision picks a third-party tool)

When a consensus parent doc leaves an open question that the operator answers by choosing a trial of an outside tool, the child doc is a derived design: not a split, not a rewrite.

1. Quote the decision verbatim in the child's decision record (the parent's question id and the operator's answer), and state the relationship in the first section: what the child owns, what the parent still owns, and what happens on success and on failure.
2. Restate every parent decision the trial changes as a child decision with the trial scope (auto-merge deferred, profile count, reviewer placement). A named deviation is not a finding; a silent override is the review's first finding.
3. Re-derive the tool's own facts from its repository at a pinned commit: env knobs, timeouts, database path, CLI verbs, defaults. Never infer them from the host's conventions. A plugin's worker timeout, precommit cap and board database are its own; the host's profile settings do not move them, and a design that raises the wrong knob fails at the first task.
4. Keep the parent's evidence dir separate; the child gets its own `<stem>-design-evidence/` and cites the parent's captures by path where it relies on them.
5. Review the child with a fold round that checks the parent for silent overrides and the tool's docs for every claimed knob.

## Check the evidence count before dispatching the reviewer

Count the files in the evidence dir against the doc header's capture count and the manifest rows. A writer that claims a capture it never wrote leaves a manifest row pointing at nothing; the reviewer finds it as a guaranteed round. Restore the capture or correct the count before dispatch.

## The first fix round moves the header out of the draft state

The fix batch that answers the first review round must move the header's Rev cell and verdict history out of the draft state in the same batch as the fixes. A doc that still says "Rev 1, not reviewed" after R1 reads as an unreviewed draft and is a guaranteed next-round finding. This is the first-round case of the general rule that every fix round writes its own rev node.
