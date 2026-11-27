# Design shapes: prior art and derived trial children

Two shapes that recur when the design is "build X" or "try Y instead of building X".

## Prior-art sections in build designs

When the design is "build X" (a pipeline, a factory, an automation, a new subsystem), the doc needs a prior-art section with three layers and one verdict, not a paragraph of prose:

1. **Hermes built-ins.** The docs pages for the closest features (kanban, delegation, cron, worktrees, profiles, goal mode), with what each gives and what it does not give.
2. **The plugin catalog AND the skills hub.** These are different sources: `plugin-catalog.json` holds plugins only, while the live `manage_catalog` search also returns community skills. A survey that greps only the catalog JSON will report real hub skills as nonexistent. Run the hub search from the parent session (subagents may not have `manage_catalog`) and hand the ids, kinds and tiers to the writer; record hub entries whose descriptions the search does not return as unread, never as rejected.
3. **Outside Hermes.** The candidate products and frameworks, each with licence, local-endpoint support, the control path from Hermes, and a verdict (adopt, borrow the pattern, reject).

End with one answer: does anything off the shelf run the whole job, and if not, which parts are worth borrowing. Every rejected candidate needs a reason, not just a verdict.

## Derived trial-onboarding child

When the user picks an off-the-shelf trial instead of building the parent (a plugin, a product, a hosted service), write a derived onboarding doc rather than a split:

- Quote the parent's decision verbatim in its own decision record, and state the relationship: the trial supersedes the parent's build path for v1, the parent is the fallback.
- Pin the candidate at a version and commit, and capture the vendor's own install, setup, settings and lifecycle text into the evidence dir.
- Carry the onboarding runbook (preflight, install, profiles, custody, board or project, the candidate's own quality gate, first task), success and failure criteria, a fixed decision date, and a rollback.
- It gets its own review loop and its own registry row; it does not edit the parent.
- Name the candidate's native limits that contradict the parent (for example a human merge gate where the parent wanted auto-merge) as trial facts, not as silent overrides.
