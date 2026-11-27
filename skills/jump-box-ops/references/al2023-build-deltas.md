# AL2023 build deltas (Ubuntu -> Amazon Linux 2023 jump box)

The jump-box repo's init script and configs were written for Ubuntu; a t3.micro AL2023 build needs these deltas. Each was a real failure on a live build, not a preference.

## fail2ban: a jail can count a ban and enforce nothing

- The AL2023 package defaults `banaction` to `firewallcmd-rich-rules`, and the AMI ships firewalld installed but its service inactive. Every ban then fails while the jail still reports the address as banned: the log shows `'FirewallD is not running'` and `killed with signal 124`, and no rule is inserted anywhere.
- Fix: set `banaction = iptables-multiport` in the jail (the `[sshd]` section is fine). The iptables here is nf_tables-backed and works.
- Verify enforcement from the packet-filter rule table — `iptables -S` or `nft list ruleset` — and confirm the address appears; the jail counter and banned list are not evidence.
- Ban state persists in `/var/lib/fail2ban/fail2ban.sqlite3` across restarts, so an address whose ban failed stays listed and re-banning it is a no-op that inserts nothing: clear it with `unbanip` first, then `banip`, then check the rule table.
- Probe with a TEST-NET address (192.0.2.1), never a real client address.
- The FILTER path (journalmatch on the drop-in's log target) is only exercised by a deliberate bad auth from a non-whitelisted address; that is a separate post-build check from an external vantage — the ban/unban proof does not cover it.

## sshd and hardening

- The ssh configuration directory is root-only (mode 0700), so a read as the login user fails with EACCES and presents as a missing file. Run such checks with elevated read, and have the fail branch list the directory so a permission problem shows as one instead of a build defect.
- The AL2023 OpenSSH build supports the repo's key-option grammar (permitopen, permitlisten, restrict). Confirm the effective configuration with `sshd -T` and check the three that matter: maxauthtries 3, passwordauthentication no, gatewayports no.
- journald is persistent by default on AL2023 — confirm before calling a sizing verdict final, since the sizing gate depends on it.

## The init script's environment and apt surface

- The init sources its env file under `set -u`, so a hand-written subset dies at the first variable it does not set (`TUNNEL_USER: unbound variable`). Provision the env by COPYING the original `config/jumpbox.env` and changing only the keys that must change (host, address, admin user); the device arrays and ports carry over verbatim.
- The apt surface is larger than a naive delta table: `DEBIAN_FRONTEND=noninteractive apt-get install -y fail2ban` (prefixed form — replace the whole line including the prefix, or the prefix survives as a Debian artefact) plus a separate `DEBIAN_FRONTEND=noninteractive apt-get update -y` line. After patching, assert that no apt-get or DEBIAN_FRONTEND residue remains, and print any offending line before asserting — the printed line is the next round's fix.

## Sizing verdict (measured, full build)

- 8 GiB gp3 after the complete build: 3.7 GiB used, 4.3 GiB available (47%), plus a 2 GiB swapfile. Sufficient with headroom; `/` is the only volume. The old Ubuntu box used 19 GiB of 30 GiB mostly for downloaded media that never belonged on it.

## Source discipline

- Stage the init script from the design-pinned blob through the clone's object store (`git cat-file blob <sha>`), never from the clone's working tree — a stale tree silently ships a version the delta table was not derived from.
- When the repo copy is unreachable from the relay, the OLD box's deployed files are the legitimate source (verified byte-identical to the repo at phase 0); name that verification in the payload log and record the provenance divergence for the doc fold.

## What a green build looks like

Every exit gate carries its own failure path: users exist with nologin shells, the drop-in is installed and `sshd -t` is clean, the host-key digest equals the audited old-box key, fail2ban is active with an insertion-proven ban/unban, exactly two admin keys, tunnel/socks key counts match the old box, swap is in fstab and active, and `ss -tlnp` shows nothing beyond :22.
