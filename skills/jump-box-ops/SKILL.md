---
name: jump-box-ops
description: "Use when AWS jump-box or tunnel SSH access misbehaves."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [ssh, jumpbox, fail2ban, ec2, network, the host]
---

# AWS jump box and reverse tunnels — ops

## When to Use

Any SSH failure involving the AWS jump box or the reverse tunnels behind it: the box refuses or times out on :22, the `the host` / `the Pi-x` aliases stop working, autossh tunnels drop, or the operator asks "did I sshban myself?".

Standing infrastructure for reaching the Pis from anywhere. When SSH to the box or through it fails, work the ladder below before touching anything: the failure is usually a fail2ban ban of the home IP, and the fix belongs to the operator (console), not the agent.

A jail listing an IP as banned does NOT prove the ban enforces anything — check the packet-filter rule table, not the jail counter (`references/al2023-build-deltas.md` has the failure mode and the fix).

## System shape (verify before assuming)

- Jump box: `ec2-18-156-118-124.eu-central-1.compute.amazonaws.com` = 18.156.118.124 (eu-central-1). Fail2ban and sshd hardening are live; `MaxAuthTries 3`.
- Reverse tunnels (autossh, loopback-only binds on the box): the host→127.0.0.1:10022 (hermes), the second host→10023, the third host→10024, desktop→10025. Clients reach Pis via per-device ed25519 certs + ProxyJump through the nologin `tunnel` user.
- The one local ubuntu admin identity is the agent's `hermes-admin` on the the host HOST (`~/.ssh/hermes-admin`, the relay executor's key); the operator's LAPTOP holds no ubuntu admin key — its ssh config carries only the two `tunnel`-user entries, and `tunnel` is nologin, so the laptop can forward ports but can never run sudo-class admin work on the box. The the host sandbox still holds NO key, by design. Never hunt for one; treat reaching `Permission denied (publickey)` as a SUCCESS signal, not a failure. For build/migration work the executor is the relay (hermes-admin on both legs); on a brand-new box that accepts no relay key yet, EC2 Instance Connect (browser SSH from AWS IPs, works regardless of a ban) installs the relay's PUBLIC half first — a paste of the pubkey line, not a secret transfer.
- Config repo: private GitHub `<your-org>/jump-box` (also `~/jump-box` host-side). The GitHub MCP PAT may 403 on it and the sandbox env carries no GitHub token — when you need jail values (bantime, ignoreip), ask the operator to read them from the console session he already has open instead of burning calls on repo access.
- SSH aliases (`the host`, `the second host`, `the third host`) live in the operator's laptop-config dotfiles, usable from his laptop only.
- **A replacement box stands built alongside** (migration off the Ubuntu t3.small): AL2023 t3.micro, admin `ec2-user`, DNS-only `jump.example.com` -> its EIP, hardened and key-identical to the old box, with the same tunnel/socks certs, both admin keys, a 2 GiB swap and no listener beyond :22. Production traffic still rides the old hostname until the client flip. Build deltas and their failure modes: `references/al2023-build-deltas.md`.

## Diagnosis ladder (start from the host; network probes before anything host-side)

1. BatchMode probe from the sandbox:
   `ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new ubuntu@<host> true`
   Read the error before concluding anything:
   - `Connection refused` = active RST = packet-level reject at the box. Two causes: fail2ban (its default action REJECTs) or sshd not listening. A closed AWS security group gives TIMEOUT, not refused — do not diagnose a ban from a timeout.
   - `Permission denied (publickey)` = box fully reachable; the problem is key selection, not a ban.
   - `Host key verification failed` on first contact with BatchMode = the client cannot answer the new-host prompt; rerun with `-o StrictHostKeyChecking=accept-new` (or a throwaway `UserKnownHostsFile`). By itself not a MITM signal.
2. Multi-vantage test to split "his IP is banned" from "box down for everyone": fire check-host.net TCP probes from 5 external nodes —
   `curl -s -H 'Accept: application/json' 'https://check-host.net/check-tcp?host=<ip>%3A22&max_nodes=5'` (the colon MUST be `%3A`), then poll `https://check-host.net/check-result/<request_id>` about 6 s later; each node reports a connect time on success. External nodes connect while the home IP is refused = source-IP ban confirmed without any box access.
3. Recovery is the operator's, from the AWS Console: EC2 → Connect → EC2 Instance Connect (browser SSH sources from AWS IPs, so the ban does not apply), then:
   ```bash
   sudo fail2ban-client status sshd                     # banned IPs + what tripped
   sudo fail2ban-client set sshd unbanip <HOME_IP>
   ```
   autossh re-establishes the tunnels on its own after unban — no restart needed.
4. Verify after unban, three levels:
   - the host BatchMode probe again reaches `Permission denied (publickey)`.
   - Tunnel listeners back — box console: `sudo ss -tlnp | grep -E ':1002[2-5]'`.
   - End-to-end from the operator's laptop: `ssh the host true && echo OK`.
   On the the host host, plain `systemctl is-active` can report the tunnel unit inactive while tunnels are established — check `systemctl --user` before declaring a tunnel dead.

## Crash-loop signature (benign)

A tunnel unit cycling `activating (auto-restart)` with `status=1/FAILURE` and ~100 ms process lifetimes during a ban window is expected, not broken: a refused connect dies instantly, autossh treats a child death inside its start-gate as fatal and exits 1, systemd restarts it, repeat. It self-recovers on the first retry after unban (observed Nov 21 2026: last crash 22:40:41, running again 22:41:13, stable for 6+ min, no restart needed). Confirm recovery with `systemctl --user status` + a sandbox BatchMode probe; do not restart the unit or hunt host-key/auth causes while the ban explanation fits.

## Cutover pre-verification (second unit, zero downtime)

- Prove the new box end to end while the old one still serves by cloning the deployed tunnel unit to a second unit (`aws-reverse-tunnel-new.service`) with ONLY the dial target changed (`sed 's|tunnel@<old-name>|tunnel@<new-name>|'`); the cert path and `-R 127.0.0.1:10022:localhost:22` stay untouched. Escape the dots when substituting a hostname with awk/sed, or a near-miss name is rewritten too. The diff against the deployed unit should show exactly the intended hunks and nothing else: the dial target, the two `-o` lines, and rewritten header comments — a clone that still carries the deployed unit's path and another user's name in its `#` header comments misreports itself in `systemctl status`.
- Start it, never enable it: an enabled test unit competes for the same `permitlisten` bind on the new box after the flip. Retire it (stop, disable, delete) once the client-side probes pass.
- Verify from the receiving side: `ss -tlnp | grep -c '127.0.0.1:10022'` ON THE NEW BOX must be exactly 1. A client that connects proves the client, not the bind. Assert the PRE-state too (0 listeners before the start), so a leftover bind from an earlier attempt cannot satisfy the only end-to-end gate, and have the remote side print a marked count (`echo COUNT:$n`) so an ssh failure or a parse miss cannot masquerade as zero, and capture the counting command's OWN status (`o=$(ss -tln 2>/dev/null) || { echo COUNT:ERR; exit 0; }`) — `command -v ss` only catches a missing binary, while a present-but-failing one yields a plain 0 that reads as "no listener".
- Pin the new hostname in known_hosts BEFORE any admin ssh to it — a `StrictHostKeyChecking=yes` admin hop cannot run before its own pin exists, so ordering the pin after the remote preflights deadlocks the first run. Gate the scanned digest against the audited old-box key; identical host keys are what make the later flip invisible to existing client pins. Only an EXACT plaintext host field may count as "our pin": `ssh-keygen -F` also matches `*.domain` wildcard and hashed entries, so filtering by key type alone turns a wildcard line into a false "this pins the host with the wrong key" FATAL and blocks the run — treat those as "also matches, left untouched" and append the exact line instead. Before appending, add a newline if the file's last line lacks one (`tail -c1`), or the pin is concatenated onto that line and the file is corrupted.
- Make the payload idempotent on its OWN success state, not just on already-done work: the intended steady state after a pass is one live test unit plus one listener, so a retry must print the OK banner and exit 0 when that state is found (the relay alerts on any non-zero exit, so a FATAL there is a false alarm). Distinguish it from a foreign leftover — one listener with the test unit inactive means someone else's bind, which is the case that must fail.
- Run the payload's `systemctl --user` calls with `XDG_RUNTIME_DIR=/run/user/$(id -u)` exported and its existence checked (otherwise a bus failure surfaces as a misleading 'daemon-reload failed'); poll `is-active` to a deadline instead of one `sleep` (`Type=simple` reports active at exec), then poll the listener; and stop the test unit on every failure path, because a cloned unit inherits `Restart=always` and an auth attempt every 10 s can trip the jail. Put `-o IdentitiesOnly=yes` and `-o BatchMode=yes` into the cloned unit's ExecStart, not only into the payload's own ssh calls.
- Flip order: the second host, the third host, then the host last — flipping the host drops the user's own live sessions through the old listener once, and autossh re-dials within RestartSec (~10 s). Do it when a dropped session is acceptable, or from SSM/LAN.

## Recurrence controls

- The home IP is dynamic and churns between incidents, so `ignoreip` is not durable. Durable options: `IdentitiesOnly yes` + explicit `IdentityFile` in every client config that talks to the box (an agent offering many keys against `MaxAuthTries 3` is the recurring trigger), or `ignorecommand` with a dynamic-DNS hostname.
- After recovering access, capture the live host keys (`ssh-keyscan -t ed25519,ecdsa,rsa <host>` piped to `ssh-keygen -lf`) so any later "host key changed" warning is checked against a known-good fingerprint instead of assumed benign or assumed compromised.
- After installing a box's host keys onto another machine (or replacing a box's keys wholesale), refresh the EXECUTING client's pins for that hostname BEFORE the next connection: strict checking validates every key type the server offers, so a stale pin in a different type rejects the session with `REMOTE HOST IDENTIFICATION HAS CHANGED` / `Offending <type> key in known_hosts:N` even while the negotiated-type pin matches. Sequence: verify the copied fingerprint against the known-good gate FIRST (the change must be explained, not assumed), then `ssh-keygen -R <host>`, re-pin from the live server (`ssh-keyscan -t ed25519,ecdsa,rsa <host> >> ~/.ssh/known_hosts`), and record all digests as the new pin record. Two format traps make a digest gate fail on a CORRECT key: on OpenSSH 10+ `ssh-keyscan` writes its `# host:22 SSH-2.0-…` banner to STDOUT, so `| head -1` feeds a comment line to `ssh-keygen -lf -` and the gate can never pass — filter `grep -v '^#'` before taking the first key line; and a hostname-prefixed line piped in raw is rejected as "(stdin) is not a public key file", so strip to `awk '{print $2" "$3}'` as well. Scan the address DNS was just verified against, not the name. When checking whether a pin already exists, use `ssh-keygen -F <host> -f <file>` — `awk '$1==host'` cannot see hashed entries (Debian ships `HashKnownHosts yes`) — and compare the key MATERIAL to the audited digest, since a presence-only check passes over a stale or foreign key and the failure then surfaces at the tunnel, pointing the diagnosis at the wrong layer.
