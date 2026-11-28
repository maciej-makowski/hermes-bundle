# App security-review recipes (hardening reviews of self-hosted apps)

Method for the class where the operator asks for a security review of an app inside a design. The loop, unslop, evidence-dir, and publish rules come from the main SKILL.md; this file is the app-level method. Shape reference: the fediverse-app-security-review doc and its evidence dir.

## Scope

- The app + its build/distribution path + the deployment-path components (container runtime, ingress connector, host packages it leans on). Adjacent consumers (companion apps holding app tokens) get named but not deep-dived — their own designs own them.
- State the sandbox constraint up front when the terminal is sealed: every box claim is recorded-baseline from the design's probe records; nothing may be upgraded to a live claim.

## Trust profile (checklist)

- Maintainer org and named individuals, project age, release cadence (fetch the FULL release history and tabulate lines/dates), adoption trackers (JS-rendered pages need a browser session; record the render method), funding sources, governance, license.
- Audit status: search for third-party audits; check for security.md, CNA status, bug bounty. Small projects carry a stub — quote the stub's own wording; it is the disclosure path.
- Beta/alpha label: quote it and derive the operational consequences (feature churn, migration weight) from the release bodies themselves, not from the label.

## Advisory pipeline: test every database BEFORE trusting it

- The negative result is the finding. Query NVD (keyword and CPE), GHSA affects-by-module-path (keyed by Go module path, so it works for non-GitHub-hosted modules), OSV (both historical module paths, plus the bare-name rejection), and the Go vuln DB index; record each as a table row with the exact query.
- Apps with zero entries are the rule for small projects: the serious fixes exist ONLY in release notes. Enumerate the security-relevant items across the full fetched release history in a table, and design monitoring around release watching, not CVE feeds.
- A stdlib/toolchain advisory the app mitigates by bumping its build is a real exposure for the deployment: trace it end to end (issue, backport, OSV id, carrying release) and confirm the pin is clear of it.

## Embedded-runtime caveat

- An up-to-date app tag does not prove the image was built with the patched toolchain. Verifiable from outside: the go.mod go directive at the tag, the CI pipeline files (builder image, digest-pinned or not, any signing/SBOM/provenance steps), the release notes' build statement, the registry record (digests, timestamps, attestation fields — usually absent). Only verifiable post-deploy: `go version -m` on the extracted binary (reads buildinfo on stripped binaries; fallback `grep -a 'go1\.'`), and the instance endpoint's version field (prefix-check it — the format carries a `+git-<sha>` suffix, so an equality assert false-alarms daily).
- Convert that into a first-deploy gate: extract the binary under the owning user's elevation, assert the toolchain version, write the result to kit state for the monitoring cron.

## Supply-chain enumeration order

1. Image path: tag vs digest pin (immutability by docs Tip is publisher discipline, not mechanism — mark the never-re-pointed half as inference); signing/SBOM/provenance (grep CI files and release bodies; absence is the finding); builder image pin; registry digests recorded for the pin.
2. Dependency tree at the tag: CGO or pure Go (a WASM-in-wazero sqlite is pure Go; flag any C); self-forked protocol deps (small blast radius, self-reviewed, same advisory blindness); high-blast-radius parsers (image, codec, html).
3. Media/WASM parsing: where the blobs ship, what the sandbox guarantees, what the design's caps bound, and the not-recommended variant to avoid.
4. The untrusted-input channel: which parsers face it and which component produced the historical bugs.
5. Update path: what each update trusts, plus the digest re-derivation step to add at update time.

## Monitoring design

- Test each candidate source credential-free and record worked/flaky/dead with the exact query in one table. Do not recommend a source that returned 504 or that went untested.
- For Go apps include the stdlib query at the embedded version (OSV `/v1/query` with `{"package":{"name":"stdlib","ecosystem":"Go"},"version":"<embedded>"}`) — stdlib advisories ride URGENT track and are invisible to app-CVE watches. Validate the query with a control version known to hit so an empty result is proven a true negative.
- Weekly cadence; one read-only script in the kit plus one cron entry; a hit prints component and advisory and exits nonzero into the existing cron output channel. Cover: the app (releases API primary), the stdlib build, the runtime package via the Debian tracker column, the ingress connector releases and advisories. Baselines for unmeasured box components are recorded by the script's own first run (say so; an install-time baseline claim for a pre-existing service has no mechanism).

## Sufficiency verdict shape

- Control-map table: threat → the design's existing control (cited) → assessment (covered / partial / gap).
- Residual risks R1-Rn, each with priority and the cheapest fix; separate irreducible trust (monitorable, not removable) from fixable items.
- An ordered additions-before-first-deployment list, then follow-ups. Check the app's own hardening docs and state which guides do and do not apply to this deployment shape (a firewall guide needs inbound ports; a container-sandboxing caution is answered by rootless userns).
- Upstream-recommended hardening that needs an unmeasured host feature (AppArmor) is marked optional-pending-measurement, not recommended-and-scheduled.

## Pitfalls

- Flag every affected-version range a release body does not state as inferred, with the reason — ranges read from patch notes are the commonest silent invention.
- Fast fleet uptake is NOT a supply-chain mitigation (it spreads an artifact faster; nothing downstream verifies). Never list it as one.
- Count maintainer/publisher sets from the evidence file that actually names them — a README credit list and a Team section can disagree, and the publisher-set argument rests on that count.
- Read release timestamps with their timezone offsets — bodies commonly print +02:00 local times; a UTC-vs-local slip inverts an hours-after claim.
- Container-adjacent commands in doc sketches (podman cp/exec) carry the owning-user elevation; rootless podman storage is per-user.
- A quote attributed to a release body must exist in THAT body — boilerplate warnings repeat across bodies and get mis-attributed; grep the specific body.
