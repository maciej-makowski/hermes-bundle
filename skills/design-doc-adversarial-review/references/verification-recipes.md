# Verification recipes — compact probes for design research

Reusable probes for verifying third-party claims at the pinned version. Each is one command; record the script and raw output in the evidence dir per the evidence-discipline rules.

## Docker Hub image tags and architectures

Hub tag pages are JS-rendered and extract as empty — use the API:

```bash
curl -s 'https://hub.docker.com/v2/repositories/<org>/<image>/tags?page_size=3' \
  | jq -r '.results[] | .name, (.images[] | "\(.architecture)/\(.os) \(.size)")'
```

- Answers the arm64-availability deploy-blocker question and gives per-tag layer sizes.
- Empty output means rate-limit, wrong repo path, or a redirect — retry or resolve the canonical Hub path before concluding "no arm64". Absence must be proven, not assumed from one empty response.

## Cross-architecture gate probes

When a design's gate runs on a different architecture than the review host, reproduce the gate's environment before trusting a clean result:

```bash
skopeo inspect --config --override-arch arm64 docker://<image>:<tag>
```

- `skopeo` selects the index instance by the host architecture. On an amd64 runner an arm64-only index (one arm64 manifest plus `unknown/unknown` attestations) fails without `--override-arch arm64`; the attestation entries do not count as a matching instance.
- A review host that matches the artifact's architecture proves nothing about an amd64 CI runner. Treat a "verified clean" gate claim as environment-scoped until it is reproduced on the runner's architecture, and re-check it in the next round.

## Config-surface discovery at the pinned tag

```bash
curl -s 'https://raw.githubusercontent.com/<org>/<repo>/<tag>/.env.example'
```

- The example env file carries the whole config knob surface AND the dangerous defaults (registration-on-by-default, SMTP wired in, debug flags) that docs pages omit — the hardening set and the "deliberately unset" list come from here.
- Same pattern for the Dockerfile (base image, exposed port, entrypoint / migrations-at-boot) and docker-compose.yml (what the official stack bundles). Never fetch main for a shipped-version claim — fetch at the tag the design pins.

## Live webfinger lookup (ActivityPub identity)

```bash
curl -s 'https://<domain>/.well-known/webfinger?resource=acct:<user>@<domain>' \
  -H 'Accept: application/jrd+json'
```

- Verify the JRD: `subject` echoes the queried handle and the `rel: self` link (type `application/activity+json`) is the actor ID. Grounds handle-resolution and split-domain claims without a browser; fetching that actor URL is the follow-up step (bio, fields, inbox, keys).

## Doc fence vs staged-file byte comparison

The close-out check for any doc that embeds kit artifacts — extract every fenced block, classify each staged file against the set:

```python
import re, pathlib
fences = re.findall(r'```[^\n]*\n(.*?)\n```', doc, re.S)
for f in sorted(staging.iterdir()):
    data = f.read_text()
    exact = any(data == c for c in fences)
    stripped = any(data.strip('\n') == c.strip('\n') for c in fences)
    # BYTE-EQUAL: ship-ready. Equal-mod-trailing-newline: fine (the doc fence
    # drops the trailing newline). NOT-in-fences: a defect ONLY if the doc's
    # own fence-vs-file rule claims that file is embedded - some kit files are
    # legitimately staged-only; check the rule sentence before flagging.
```

- Run it as part of the one-script close-out (alongside new-marker presence, old-marker absence, and the sha256/line-count pin) rather than as four hand-greps - the classification, not the diff, is what catches a fence that drifted from its file mid-loop.

## Mermaid fence render check

For any doc that embeds mermaid diagrams (a fold that adds them, or any new diagram fence), prove the fence parses and renders under the CURRENT mermaid before the reviewer round sees it:

```bash
npm init -y && npm install mermaid jsdom          # once, in the script's directory
awk '/```mermaid/{n++; f="/tmp/d" n ".mmd"; next} /^```$/{f=""; next} f{print > f}' doc.md
node scripts/mermaid-render-check.js /tmp/d1.mmd /tmp/d2.mmd     # relative to this skill's directory
```

- The harness stubs SVG geometry (jsdom does no layout); a successful render still proves the syntax parses and renders. OK/FAIL per fence, exit 1 on any FAIL.
- Do not use a hosted render proxy (kroki.io etc.) as the oracle: its mermaid build can lag the current parser and 400 valid modern syntax (quoted subgraph titles, a bare % inside a quoted label), so a proxy failure is not evidence the fence is invalid.
- When the skill's check scripts are not materialized in the sandbox (linked files can be absent on some backends; `ls` the script path before relying on it), hand-validate the fence and disclose 'validated by inspection only' in three places — the doc's honest notes, the evidence README's corrections index, and the reviewer dispatch — so an unvalidated diagram never reads as machine-checked; a reviewer told the validation state attacks the syntax deliberately instead of assuming it.
- When transcribing such content for a push, remember read_file elides very long lines (multi-KB table rows); fetch them byte-exact with `sed -n 'Np'` through terminal, which prints full lines where read_file truncates.

## Fix-verification close-out: byte-identity by reconstruction

When a fix-verification round hits a pin mismatch between the dispatched sha and the sha of the file it read (a concurrent touch, a newline normalization, or a stale dispatch figure), close it by reconstruction instead of arguing about whose pin is stale:

1. Take the previous round's pinned bytes (its recorded sha256) and this round's declared delta list — the exact replacement pairs the fix applied.
2. Reconstruct: start from the pinned bytes, apply only the declared deltas, recompute the sha.
3. If the reconstruction equals the CURRENT disk file's sha, the disk file is proven to be reviewed-content plus exactly the declared deltas: no concurrent writer intervened, and the final round reviewed the real bytes. Record that proof in the comments file — it is what lets a round close on a pin discrepancy instead of burning another round re-reading everything.
4. If the reconstruction does NOT match, the gap localizes the unexplained delta: re-read the differing region and either attribute it honestly (mask-span redaction, trailing-newline normalization) or re-run the fix. Never reconcile by inventing masked content.

- The same technique works forward for pushes: certify a pushed blob equals the intended content by reverting the declared deltas from the pushed bytes and comparing against the declared base, or by diffing the PR patch (each file's patch carries main's exact bytes beside the changes) — the diff, not expectation, is the arbiter of byte parity.
- Dispatch figures are computed by whichever hand last wrote the file; trust the reconstruction over any remembered sha when they disagree, and say in the round record that the dispatched figure was stale rather than patching history to match.

## Baseline source compile-and-parse sweep

For any design that pins a repo tip and whose rollout or verification commands run against that tree, compile-and-parse the verbatim copies at write time, before the first review round:

```bash
find src-at-<sha>/ -name '*.py' -exec python3 -m py_compile {} +
find src-at-<sha>/ -name '*.sh' -exec bash -n {} +
find src-at-<sha>/ -name '*.toml' -exec python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],"rb"))' {} +
```

- A pinned tip whose source cannot parse is a BLOCKER the reviewer should not be the first to find: it voids every CI-gated rollout command and every verification command in the doc, and a baseline that describes CI as green at that state is internally false. If the sweep fails, the doc gains a repair phase that lands before any feature work (line-count-neutral fixes keep every existing file:line cite valid), or re-pins to a state that parses.
- When the pinned tip cannot import but the deployed app demonstrably runs, record the runtime divergence in the honest notes (the box's runtime source differs from master; how is not derivable from a sealed sandbox) instead of assuming they match.
- Date a baseline defect before characterizing it: list the path's commits (mcp list_commits on the file path) and fetch the file at the earliest commit that touched it, so the doc does not blame a recent squash for a defect the initial commit carried. The git blob sha of a copy (sha1('blob <len>\\0' + bytes)) is the byte-fidelity oracle for any suspect transcription.

## Version-scoped parse and capability claims

A parse/import/capability defect claim is VERSION-SCOPED until proven against the project's own floor. A `SyntaxError under the sandbox's Python` can be legal syntax under the repo's pinned floor (PEP 758 legalized unparenthesized except tuples in 3.14; the sandbox's 3.13 ast mis-generalized it into an always-true defect that had already propagated into a withdrawn design's repair plan and a fact-store row). Before writing 'cannot parse/import' into a doc:

1. Read the floor pins first: pyproject `requires-python`, `.python-version`, the CI toolchain step.
2. Run the check under that exact floor (`uv run --no-project --python <floor> python ...`): ast.parse + compile the exact bytes, print the PARSE and COMPILE results as SEPARATE lines (a combined 'OK' line under-evidences the compile step a reviewer will ask for), and quote the suspect line in the capture.
3. Run the project's linter at the floor's target version (`uvx ruff@<ver> check --isolated --target-version py<floor> <file>`); current ruff removed rule E999 — syntax errors surface as always-on diagnostics, so emitted lint findings prove a successful parse, and an E-class absence plus lint-only findings is the pass shape.
4. Capture the upstream feature's identity from the canonical source (PEP page title, Status, Python-Version, Resolution) as part of the same numbered probe.
5. Reconcile with CI: a green run on the same tip corroborates the floor-side result; record the run id, head sha, and per-step conclusions via the Actions jobs endpoint.

If the claim holds only under pre-floor versions, scope every doc statement and fact-store row to the version range — an unscoped 'the tip is broken' sentence and an unscoped memory fact are both false records the next session inherits.

## Pricing-page capture

- Vendor pricing domains move under you: the cited URL can redirect to a renamed platform domain. Capture the redirect TARGET, verify the pricing claims against it, and record both URL forms in the sources line.
- 'Latest'-style FX and price aliases 301-redirect and move daily: cite the DATED endpoint (the date the payload itself carries). A `/latest` capture is unreproducible next round, and a payload dated before the capture day is the tell that the alias, not the dated endpoint, was used; re-fetch the dated URL with redirects followed and confirm the payload date matches.
- When a vendor's pricing TABLE does not render in extraction, capture the page's rules text (cache multipliers, batch percentages, tiering sentences), which usually does render, and mark the table-dependent figures third-party-verified in the honest notes — one load-bearing multiplier with no captured source is a finding.
- A full-page web_extract saves the complete page text to a cache file whose path appears in the result footer: copy that file into the evidence dir as the numbered probe (add the provenance header with a patch at the top) instead of hand-transcribing — the cache copy is byte-complete where the inline extract is head+tail truncated.

## GitHub username existence and creation timing

```bash
curl -s https://api.github.com/users/<name>   # 200 = taken (created_at, type, repos); 404 = no active account
```

- The browser fallback once the unauthenticated API budget (60 requests/hour/IP) is spent: `github.com/<name>` title reads "Page not found · GitHub" when free, a profile title when taken.
- `created_at` distinguishes two sibling registrations (which account was minted when) without any authenticated call; pair it with a browser title check to confirm both names live at the same moment.
- A 404 means no active account, not guaranteed registrable — reserved or suspended logins can still 404, so the signup form stays the final check before registration.

## Pinned-release binary capture (CLI contract without an account)

When a design wraps a CLI binary and the identity holding its live session is operator-only (a sudo-gated container user), the help surface is still capturable: download the pinned release binary into the sandbox, checksum-verify it, and run --help for every subcommand the design wires. Help needs no login, no session, and no mailbox state.

```bash
curl -sL -o /tmp/tool.tar.gz 'https://github.com/<org>/<repo>/releases/download/<tag>/<asset>'
sha256sum /tmp/tool.tar.gz          # record as the provenance base in the evidence dir
tar -xzf /tmp/tool.tar.gz && ./tool <subcommand> --help > evidence/NN-<verb>-help.md
```

- This turns an operator-only blocked boundary into captured ground truth for every flag-set, subcommand-tree, and argv-contract claim. Only runtime claims (envelopes, real mutations) still need the live runbook phase. State the split in the doc: captured bytes vs live run.
- Write the provenance file FIRST: the release page's published checksum against the downloaded artifact's sha256, the binary's own version output, and the architecture (an x86_64 binary on an arm64 host verifies but never runs). Every --help capture cites that provenance file.
- Check the container image recipe for a version pin before trusting one: the pin can live in the deployment (a host-installed binary mounted into the container) rather than in the repo. The operative pin is the deployed binary's version; corroborate it from sibling docs' recorded baselines when the box is unreachable, and record the corrected assumption in the doc.

## GitHub docs source capture

- docs.github.com pages have canonical markdown: `raw.githubusercontent.com/github/docs/main/content/<path-under-/en>.md`. Site-policy pages (ToS, privacy) live in a different repo, `github/site-policy`, under `Policies/<category>/<file>.md` — locate those paths with a repo-scoped code search, not a guess.
- Fetch each candidate separately with per-URL HTTP-code output; an `&&`-chained or `-f` curl batch aborts at the first 404 and writes nothing.
- REST-reference pages (`content/rest/**`) are generated stubs (a few hundred bytes of frontmatter and includes): capture the RENDERED page instead. The rendered capture can still cut mid-table at a ~50k-character cap — check the file tail for a cut before citing line numbers past it, and for permission-shaped claims prefer the runtime `X-Accepted-GitHub-Permissions` response header (documented in the captured page head) over a truncated static table.
- Sibling design docs live in a PRIVATE repo: raw.githubusercontent.com returns 404 unauthenticated even at exact paths. Capture them from the local synced design tree instead (copy the working file), record the copy's mtime and sha plus the may-trail-unmerged-edits caveat in the manifest, and mark the provenance in the doc's honest notes — a synced-tree capture is not a @main capture. A commit RECORD (a publish squash sha) has no synced-tree copy: capture it via the authenticated GitHub API (`get_commit` on the sha) into a provenance-stamped evidence file, and never read a private-repo commit's existence off an unauthenticated page fetch — the 404 on a valid sha manufactures a fabricated-sha false finding.

## Prior-art freshness and scheduled detectors

- Re-read each candidate skill's `linked_files` at write time, not from an earlier `skill_view`: a reference file can land mid-session, and a prior-art row that says no skill exists is a guaranteed reviewer finding. The catalog search and the skill view are point-in-time snapshots.
- **The plugin catalog is not the whole catalog.** `plugin-catalog.json` is keyed by `name` and lists plugins only; community skills (`agentic-factory`, `overnight-factory`, `worktree-agents`, `worktree-manager`) exist only in the live `manage_catalog` search, which returns id, kind, display and tier but no description. Search both before writing a "does not exist" row; when the hub is the only source, record the name as unread rather than rejected.
- A GitHub `schedule` is not a reliable detector on its own. A public repository auto-disables scheduled workflows after 60 days without repository activity, and the workflow's own runs do not reset that clock. A pipeline whose only activity is the build is exactly that shape. Require a second trigger (the consumer's own timer reads the upstream digest and dispatches the workflow) or a keepalive, and have the reviewer check the schedule's liveness as a gate-integrity item.

## Host-identity and reachability probes

Before any doc records "host X unreachable" or "tool Y absent", capture the container's own identity in the same batch: hostname, `uname -m`, the mount-table line for the tree in question (`mount | grep <path>`), and presence probes for every binary/directory the claim concerns (`command -v <tool>; ls <dir>`).

- An ssh refusal to a host ALIAS from inside a container is not evidence of host distance: the container may sit ON that host (an ARM design-tree mount from /dev/mmcblk0p2 is a Pi-class tell). Record what the probes show ("runs on an ARM host; the alias refuses from inside") instead of the conclusion ("the target host is unreachable") — the corrected record can flip a runbook phase from impossible to executable and hand a runbook step a custody argument it lacked.
- The same absence probe can carry the design's security case: a secret store provably absent from every agent sandbox (binary and directory both missing in-container) IS the custody boundary. Probe it explicitly and cite it as one, instead of leaning on gates that agent ptys defeat.
- State in the doc which host conclusions ARE captured and which are not ("not established by capture"), and correct a superseded probe record in place (add a v2 section) rather than deleting it — the v1 output stays the historical record and the correction stays auditable.
