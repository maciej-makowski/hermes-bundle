# Migration-runbook reviewer checklist

Attack classes for any design doc that moves a live service between providers, zones, or ingress paths. Each item is a finding class the generic attack-angle list misses; every one has cost a full review round somewhere. Verify against the doc's own probe baseline, not prose.

## Ordering and circularity

- Walk the runbook end to end as the operator: for each step, can its exit criteria actually be evaluated when stated? An exit criterion that requires a later step's artifact is an ordering bug, not prose.
- Hunt circular dependencies between DNS authority, certificate issuance, and reachability: HTTP-01 fails for names that do not yet resolve to the issuer; mid-propagation issuance fails from some vantage points. The standard break is pre-issuing via DNS-01 against the still-authoritative zone (manual TXT placement; no API token needed) and loading the certs as files, then handing renewal to HTTP-01 after the switch. If the doc relies on 'certificates issue live within seconds', find the outage it hides.
- After any renumbering, re-grep every 'step N' cross-reference in the runbook, the risks section, and the open decisions.

## Rollback claims

- Reconcile each rollback window with the state-changing steps inside it: anything that publishes trust anchors (DS), changes registrar lock, or caches data at a third party closes the window. Scope the window to the first such step; spell out the escalated post-window sequence with its cache/TTL cost.
- For each rollback, state what still functions after it: which path serves which hostname, and what the user sees during the rollback itself.

## Firewall and admin path

- The plan's own firewall rules must admit the runbook's administration path: trace each step's executing host (who runs it, from where) and its network reach to every box it touches. Default-deny without the admin port deadlocks the runbook; established connections only delay the lockout.
- Verify each user-executed step's credential assumption against the user's actual client-side setup before handing over the commands: a step assigned to 'the laptop' implicitly assumes the laptop holds the identity that target key uses — read the user's ssh config (aliases, IdentityFile lines, and the target user each alias logs in as) and confirm the identity exists client-side before composing the operator's command blocks; a nologin service user on the far end means a tunnel identity can forward ports but can never run sudo-class work, so the step is impossible as written no matter how correct its syntax. When the assumption fails, re-assign the step to an identity that exists and is already authorized (the agent relay's own key on the host, or an emergency console path such as EC2 Instance Connect installing the relay's public half first) and record the executor reassignment as an explicit deviation for the next doc fold — silently re-running the impossible step from a different vantage without the record is how the runbook and reality drift apart.
- A runbook step whose input is console-only (security-group rules, registry state, anything the box's own metadata cannot show) is verified by the operator's screenshots, and each console-read id is cross-checked against an independent capture where one exists (the box's own metadata read) — two independent paths agreeing is the verification; a screenshot alone is one source.
- Check stated listening addresses against actual binds for every service a later step reaches over a NEW path: loopback-only binds are invisible over tunnel/interface IPs; the fix is an explicit rebind or relay step, and the exit criteria must curl each backend from the new vantage point.

## Address families

- A migration that serves A records on names that today also serve AAAA must decide the v6 family explicitly: name the new v6 endpoint (or declare the drop as a stated behaviour change). 'A/AAAA pre-pointed at the VPS IP' with one address is an operator dead-end. Inventory both families from the probe baseline (proxied origins answer both even when only A is quoted).

## Cutover arithmetic

- Model the residual error class honestly, cache layer by cache layer: delegation (NS) caches held past TTL, address caches at each provider, and which path keeps answering during the wait. A stop criterion phrased as 'traffic at/near zero for > one TTL AND > delegation TTL since the switch' is the sound shape; any 'brownout near one minute' claim that ignores NS-cache staleness is fiction. State the worst-case straggler bound from the doc's own propagation analysis, not a rounder nicer number.
- Records whose TTL cannot be lowered (proxied origin answers, server-set zone floors) bound the window from below; design around the floor, not around a lowered TTL that requires a support exception.

## Gated and private resources

- Walk every step asking 'is the gated resource published ungated here?'. A record staged early can publish a private app open to the internet for the length of a propagation window; the fail-closed shape is: no record until the replacement gate exists, and exit criteria asserting the gate answers and the app never does.
- When the old gate lives at a provider being exited, its policy internals may be unreadable without an API token; mark that as an honest-note gap that gates the migration decision, not as known config.
- An edge-level gate shadows origin-path verification: while a Cloudflare Access application still exists on the hostname, an unauthenticated edge probe answers the gate (302) no matter what the origin or tunnel ingress does, so it can never verify an ingress/origin removal. Verify such edits through the box-side config greps and the post-restart all-hostnames loop, and reserve the public edge probe for after the step that changes the edge's own answer (the DNS record deletion, where NXDOMAIN is the criterion).

## Decommission inventory

- Reconcile the decommission step's delete list against every artifact the earlier steps created (staging records, challenge TXTs, test names) plus the original inventory; a leftover staging record or tunnel credential is either a security residue or a broken rollback vehicle. Keep the old zone/account dormant one propagation-and-error cycle past cutover, and say when it may be closed.
- Reconcile the inventory against the LIVE box, not only the doc's own text: a discovery probe on the source box (running services, /home contents) finds undocumented roles (a leftover proxy daemon with zero observed consumers) and forgotten bulk data (a downloads directory holding gigabytes) that neither the design's author nor any earlier review knew about. Fold each find as an explicit disposition decision (retired with the instance vs copied off before the stop) with the user's confirmation named — never silently drop an undocumented role into the delete list.
