# Git-era publish and implementation flow (design docs)

Depth for the SKILL.md publish bullet and adoption kickoff: how a finished
design doc lands in the design repo, and how an adopted design's
implementation phases run. The SKILL.md publish bullet names the staged-script
path via github-repo-management's bulk-repo-sync recipe; on a box with the
no-agent cron relay installed, the agent fires that staged script itself, so
no user attendance is needed. This file is the proven form of that path.

## Publishing a finished doc

- Never inline `push_files` for a 40-60 KB doc body: tool-call payloads are
  hand-emitted inline, and the failure shape is a malformed tool-call (the
  body's bytes break the hand-composed JSON array), not a clean size
  rejection, so bulk content rides the host clone instead.
- Publish through the no-agent cron relay (see the hermes-cron-script-jobs
  skill's relay pattern): stage the publish script at the workspace bind,
  overwrite the shared relay slot immediately before each fire, fire a
  one-shot no-agent job running `run-staged.sh`, and tee the payload's output
  to an `out-<task>.txt` beside it in the bind. The fire's stdout does not
  re-enter the session, so the out-file is the read-back: wait ~3 minutes,
  then read it from the bind. The fire's cron COMPLETION can report
  "silent (empty output)" even when the payload succeeded and its
  deliverables landed — the delivery view is not the verdict; make every
  payload copy its deliverables into the bind before exiting 0 and judge
  the run from those copies, never from the completion block.
- The publish payload: clone or update the host clone at `$HOME/git/<repo>`
  with `-c credential.helper="$HOME/.config/git/gh-token-helper.sh"` (the
  proven push path where bare `gh` is unauthenticated); `git fetch origin
  <default>`; `git checkout -f -B design/<name> origin/<default>`; copy the
  doc from the workspace bind; stage the DESIGN-INDEX row as its own snippet
  file in the bind and make it a payload precondition (a doc-only payload
  that needs the row fails mid-fire); insert the row into MAIN's index copy
  after the last `^|` line (`sed "${LAST}r $ROW"`), never the tree's copy
  (the tree index can lag or lead main); grep-count the row to exactly 1 and
  fail if it already exists (idempotent re-run); commit with a conventional
  subject; push. Keep it idempotent (`git diff --cached --quiet` no-op exit)
  and fatal loudly, banner plus exit 1, on every precondition miss (missing
  helper, missing source file, missing row snippet).
- Then open the PR via the MCP github tools and squash-merge via MCP with the
  FULL 40-character head SHA. On a protected default branch the merge attempt
  is itself the CI gate: check-runs listing 403s on the PAT, so wait a few
  minutes after opening, attempt the merge, and retry on refusal. A
  successful merge proves the required checks were green; report that basis.
- Verify every push by diff: reconstruct the pushed file from the PR diff and
  compare it byte-for-byte against the local source. The blob SHA (or `git
  hash-object`) is the arbiter; matching sizes are not. Close the
  verification three ways when the push rode the relay: the local `git
  hash-object` of the source, the blob SHA the payload echoes for the
  committed file, and the remote SHA header a `get_file_contents` fetch at
  the branch reports — all three must equal.
- For a small or structural diff (a one-line index-row insertion beside the
  doc), `pull_request_read get_files` reports each file's additions/changes
  counts and the full patch, so a one-line-count index change plus the doc's
  patch reading byte-identical to the local source proves the push without
  re-fetching large file bodies; the doc's own blob-SHA three-point check
  still runs.
- After the merge, refresh the synced design tree in a second relay fire:
  fetch `main` in the host clone, copy `DESIGN-INDEX.md` and the merged
  `PROPOSED/<name>-design-final.md` into the tree (the final-named copy lands
  beside the working doc, the tree's existing `<name>-design.md` /
  `-final.md` pair shape), and grep-verify the index row. The tree is what
  sibling sessions read and it lags the repo after every merge otherwise.
  Then reset the relay slot to an idle no-op payload so no stale payload
  waits for the next fire.
- The shared slot is CONTENDED whenever a parallel session publishes through
  it: a session can re-stage the slot between your staging and your fire, so
  your fire executes THEIR payload and their fire can execute yours.
  Marker-gating (grep your marker, exit 3 otherwise) protects a payload from
  running STALE content but does not stop cross-fires; both directions are
  harmless only when every staged payload is self-contained and re-runnable.
  Identify what actually ran from the fire's stdout banner in the cron
  record, disclose any cross-session side effect (a branch the foreign
  payload pushed) and leave its recovery to its owner, and re-fire with an
  ABSOLUTE one-shot timestamp immediately after re-staging — relative
  'in Nm' schedules can drift to the next day, and each re-stage/fire cycle
  is cheap while the marker check makes a stolen run loud in the out-file.
- When the slot is hot, do the post-merge tree refresh WITHOUT the relay:
  the MCP `get_file_contents` result's persisted spillover copy is
  byte-exact — strip the `successfully downloaded text file (SHA: <blob>)`
  header line, verify the git blob SHA of the remainder (a trim loop over
  trailing lines absorbs any persistence footer), and write the body into
  the tree. Build the refreshed DESIGN-INDEX.md as tree-bytes + the row
  snippet and accept it only when its computed blob SHA equals MAIN's
  current index blob (fetch the index via MCP for the oracle) — the hash
  comparison is the transcription guard: an exact match proves the
  construction is byte-identical to main without any manual copying, and a
  mismatch means the tree lags or leads main beyond this row, which belongs
  to the row owners.
- For an adoption transition (PROPOSED to ADOPTED), extract the replacement
  index row from the adopted doc's own registry-template fence at publish
  time (grep the line from the copied doc inside the payload) instead of
  staging a separate row snippet — the row then cannot drift from the doc,
  and the payload asserts the old row is the PROPOSED one before replacing.
  When the doc carries NO index-row fence (its template fence is the kit's
  own registry, not the index), compose the row by editing the CURRENT row's
  cells in place — path, status, the Rev cell (newest rev first, prior revs
  retained), the rollout cell (COMPLETE + the remaining attended items), and
  the round-history cell — and compute the new doc blob with `git
  hash-object` BEFORE the commit so the history cell can cite it. The
  transition's sibling-status sweep greps the doc's sibling list for every
  sibling the index shows as moved (an ADOPTED sibling still cited PROPOSED
  in a Relationship paragraph is exactly the stale reference the fold's
  sweep exists to catch), and the fresh-clone scratch dir must be RE-CLONED
  on a re-fire, not resumed: a first fire whose transition script aborts
  after its `git mv` leaves the moved tree behind, and a resumed run reads
  the moved path where the script expects the original.

## Kit PRs in no-CI repos (the gate review is the merge gate)

A deployment design's Block A turns the doc's embedded kit artifacts into the
kit repo's files, and the services-monorepo kit PR merges on the operator's click
with no CI behind it — so the adversarial kit review IS the merge gate, and
the operator's merge-on-pass instruction delegates the loop: dispatch the gate
reviewer, fix in one pass per round, merge at zero findings, and sync the
tree after. The kit authoring rules (self-contained de-referenced comments,
the self-containment grep as a commit gate, exec bits on scripts, per-file
blob verification, the merge hand-off turn) live in the kit-authoring section
below; the review-side rules that cost a round this pass:

- The HAND-WRITTEN kit docs take the gate review's findings while the
  doc-fence-derived scripts inherit the design loop's review — a fresh
  RUNBOOK's four majors were all flow defects (a deploy step sudo-wrapped so
  the kit state dir re-rooted and broke the freshness chain; a restore-test
  curl missing the retry-all shape; a password rotation that deleted rows
  without the env edit its create-once mechanism requires, silently restoring
  the old password; an update flow that could apply nothing for lack of a box
  pull, spelled apply-changes, and a running-image digest check). Write the
  RUNBOOK at script-level rigor: every command runnable as written under the
  recorded box state, the elevation form on every container-addressing
  command, retry-all on every boot gate, a failure signal for every
  silent-failure pipeline, and the environment edit wherever a recreate-from
  mechanism reads one.
- Structure relay fix passes to tolerate already-applied state: per-edit
  counts (0 = already applied, skip; 1 = apply; >1 = flag and stop that edit),
  a self-containment + syntax gate inside the pass, and a COMMIT of whatever
  landed before the pass exits. A pass that dies mid-edit leaves the host
  clone dirty, and the next pass's `checkout -f` wipes those edits — so
  either commit-what-landed before exiting, or make the next pass
  re-apply-tolerantly instead of trusting the tree. Report per-edit
  applied/missed counts in the out-file so the follow-up pass knows what
  remains without re-deriving. THE COUNT MUST READ THE POST-PATCH STATE:
  a guard that counts the pre-patch ANCHOR (the find string) is blind to its
  own application, because the anchor survives the insert beside it — a
  re-fired pass re-inserted the same block twice (Nov 18 2026: a doubling
  the next review round caught as its only MINOR). The robust guard counts
  the INSERTED text (0 = apply; 1 = already applied; >1 = dedup or stop),
  and an already-doubled state is repaired by replacing the doubled block
  with the single one under a count==1 assertion, never by a blind anchor
  edit.
- Enumerate in the payload's `git add` EVERY file the commit message claims;
  stage the kit script and the tests dir as two entries, never one, because
  a partial staging plus a plan-derived message ships a commit whose message
  records fixes the diff does not carry — a reviewer byte-compares head
  against the prior round and reads it as a false record at full round cost.
  The patch's success line ("N hunks applied") reports the WORKING TREE,
  never the commit; the only read-back is the commit's own file list (`git
  show --stat --oneline HEAD`) run inside the payload after staging and
  before push, and the parent treats the fire's OK as unverified until that
  list names every claimed file. Word the message from the STAGED diff, not
  the fix plan: staging is where an omission becomes invisible.
- Compose a payload's embedded logic as a standalone file staged via the
  workspace bind and called by path (`python3 <bind>/patch.py`), never as a
  never as a python heredoc inside the payload's own heredoc — the two quoting
  layers mangle each other (a triple-quoted find string's trailing quotes collide
  with the payload's delimiters) and the fire dies on a syntax error before
  any edit runs. The bind copy is also re-runnable after a failed fire
  without re-staging anything. When the payload runs a test harness as a
  COMMIT GATE (the ladder must be green before the commit lands), the
  harness's own failures then block the fire — run the gate AFTER the patch
  but BEFORE `git add`, and copy the harness's own failure log into the bind
  on the fatal exit so the parent can read the failing asserts without a
  second diagnostic fire.

### Committing an offline test ladder into the repo (packaging rules)

A workspace test harness becomes a repo asset only when it RUNS from its
committed location; each of these has shipped broken and been caught by a
reviewer running the committed bytes:

- Anchor the script's paths to the COMMITTED layout (tests/ inside the kit
dir), and resolve them with a probe (if the script exists at
`$HERE/../<name>` use that layout, else the author layout) — anchors written
for the author's workspace layout resolve to nonexistent paths once
committed, and every launch then exits 127 while absence-asserts pass
vacuously (7 of 87 'passes' with the tested process never running). A verdict
drawn from a pass count without reading WHICH asserts passed is unsafe;
read the pass lines.
- Never hardcode dates into fixture data a check compares against today (a
staleness check keys on date equality): stamp the report dates at build time
and re-stamp at run time in the runner, so the green record cannot expire one
day after it was recorded; keep the deliberately-stale fixture untouched.
- chmod the stubs inside the runner (`chmod +x "$HERE"/stubs/*`) and commit
them mode 755 — a 644 stub fails the version read it exists to answer.
- Regenerate mutable test assets (re-pointed registries, report copies) under
a scratch/run directory inside the runner, never in place over committed
files — an in-place run leaves git-status noise and a crashed run leaves a
tracked file in a test state.
- Re-earn the green record on the COMMITTED bytes: run the ladder from the
clone (the committed layout) after staging, before the tally goes into the
results file; a tally copied from the author-layout run is not evidence the
committed tree reproduces it. Disclose in the results file every external
prerequisite a fresh clone needs (fixture source paths, working clones, stub
modes) — an undisclosed prerequisite makes the record unreproducible and the
disclosure itself is the finding otherwise.
- Every ladder case a reviewer prescribes (a confirmed-hit line, a reordered-
pin binding) lands as a committed assert in the same round the mechanism
fixes — a fix verified only by reading the code leaves the regression
uncatchable by the ladder and the gap re-opens as a finding.

## The per-phase implementation loop (adopted multi-phase design)

- File the tracking issue FIRST via the MCP github tools: the repo's spec
  convention is issue-keyed, so a placeholder in a pushed spec filename is a
  defect. The issue body is self-contained (no links to the private design
  repo).
- Ship the spec and plan INSIDE the implementation PR, under the repo's own
  docs convention and in the repo's format, and make them self-contained: the
  repo reader cannot see the private design doc, so inline the mechanics
  (token values, pair sets, selectors, commands) and keep design-doc cites as
  acknowledged attribution only. A committed file that dangles on unshared
  context re-teaches content no reader can verify.
- Draft and test locally in a workspace clone before pushing: sync the
  toolchain, run the full suite, and compare any failures against a
  PRISTINE-WORKTREE baseline. Error-node IDs identical without the change are
  environment fixtures, not regressions; report them as such instead of
  fixing ghosts. Where the design defines a gate (a checker script, a unit
  test), run it BOTH ways: it must fail on the pre-change state and pass on
  the new one. That asymmetry is the acceptance evidence.
- Review loop: dispatch an adversarial reviewer with MINIMAL context: the
  PR, its in-repo spec (that spec is the contract), and the issue; not the
  design-doc narrative. The reviewer verifies the diff against the spec,
  recomputes claimed numbers itself, executes what it can (the shipped
  checker, the new tests), posts findings as PR comments signed
  'reviewer', and posts APPROVE or CHANGES REQUIRED. Fix every remark in
  ONE push per round, then dispatch a verification round until APPROVE, and
  squash-merge under the standing merge authority (pre-authorized in-flight
  means zero open remarks plus green CI; otherwise ask).
- Registry: an adopted design's PROPOSED-to-ADOPTED flip rides implementation
  evidence (first phase merged), through the same relay plus PR. In the same
  PR, sync the moved copy to the doc's CURRENT local revision so the repo
  copy never lags the working tree, and update the local DESIGN-INDEX row to
  match the merged state.
- Extend the CI gates earlier phases pinned when your phase adds a surface
  they cover: a first phase that ships a contrast pair set, invariant
  greps, or markup-pinning tests makes those the standing acceptance
  rules, and a later phase's PR that renders a new visible state adds its
  rows and pins in the SAME PR — a new surface left outside the gate is a
  review finding, and the fix touches the checker, its spec text, and any
  row count the tests reference.

## Kit authoring for a deployment design (the rollout's Block A)

A deployment design's Block A turns the doc's embedded kit artifacts into the
kit repo's files. The kit copies are SELF-CONTAINED variants, not raw copies:
comment-only de-referencing strips design-doc references, probe ids, section
numbers, and sibling-design names, because the repo reader cannot verify any
of them (executable lines untouched; the doc's fences keep the cited variants
as the spec). Then:

- Run the self-containment gate over the built kit before push: grep the kit
  dir for probe-id patterns (P0N, P1N), 'design-final', 'Block [A-H]', 'open
  decision', 'section N', and sibling-design names — every hit is a comment
  edit, and a CODE hit is a real defect. Wrap grep matches as a check
  (report-and-fail) inside the push payload too, so a re-derived kit cannot
  reintroduce references.
- Ship the three companion docs every kit needs: CHANGELOG.md (applied-digest
  history, newest first — the update runbook's rollback memory), README.md
  (file inventory + deploy order, self-contained), RUNBOOK.md (the doc's
  rollout Blocks as executable checklists with the exact commands, executor
  labels kept as OPERATOR/AGENT, password-rotation and teardown included).
- Push via the relay clone (clone-or-update the host clone, branch
  `kit/<name>` off the default, copy the kit dir from the bind, exec bits on
  scripts, commit, push) and verify per-file git blob SHAs via
  get_file_contents against local `git hash-object` — one call lists the
  whole directory's shas. No transcription step exists, so blob equality is
  expected on the first push, not a repair.
- The kit merge is the repo owner's per its merge policy (agent authors the
  PR and stops at the merge gate); hand the user the merge link together with
  the attended rollout Blocks' exact command fences — one hand-off turn
  carries the PR link and the next attended steps, so the user runs them
  while the kit PR waits.
- After a fix lands on a deployed kit script, run the deployed script ONCE
  through the relay before the next scheduled fire — the fixed defect's
  WARN-class signature is the assertion (the fixed WARNs absent = landed;
  a standing-state WARN persisting confirms the unattended item, not the
  fix), and a same-day re-run correctly reports zero hits where the day's
  first fire already advanced the baselines — that silence is the delta
  design, not a missed check. When the user asks to see the current status,
  the same fire doubles as the demo: copy the report file into the bind and
  present it as an attachment with the hits/WARN summary inline.

## Three fold-phase pitfalls

- Status-line freshness: a design doc's Status line goes stale the moment
  implementation starts ('nothing has started' contradicts an open PR). Write
  the status against the live state at every rev and refresh it when a phase
  merges; otherwise the reviewer flags the stale form and costs a round.
- Decision card versus pre-written rollout text: when a kickoff card overrides
  something the doc already specced, grep the rollout and governance sections
  for the OLD decision's verbs ('ask the operator to merge', 'after each phase',
  'same deploy', 'consistent with ask-to-merge'). Those sentences predate the
  card and re-teach the overridden behaviour unless each one is reconciled in
  the same pass.
- Treat a 'subagent modified files the parent previously read' banner as a
  hypothesis, not evidence: read-only reviewers tripped it on files that git
  status and grep proved unchanged. Verify on disk (git status, marker grep)
  before treating it as a concurrent-writer race.
