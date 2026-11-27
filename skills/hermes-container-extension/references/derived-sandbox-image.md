# Derived sandbox image: build, publish, auto-update

Use this when the sandbox needs tools that must be present at every container start. It replaces the per-session apt and pip install pattern.

## What the live sandbox is

- The gateway runs natively; the sandbox is a podman container created from `terminal.docker_image` (default `nousresearch/hermes-sandbox:desktop`).
- The image is Debian 13 arm64 on the host. It is built from `nikolaik/python-nodejs:python3.13-nodejs26` plus a display stack, Playwright Chromium, cua-driver, and Pillow.
- The image contains no Hermes code and no credentials. The gateway shells into it.
- The `pn` user (uid 1000) is part of the contract; the gateway and the display stack run commands as that user.

## The durable route

1. Build a derived image `FROM docker.io/nousresearch/hermes-sandbox:desktop@<arm64 digest>`. Keep the entrypoint and the `pn` user unchanged.
2. Add the tools as image layers: Debian packages first, Python packages second, pinned release binaries last.
3. Publish the image to a registry the host can pull from. A public GHCR package pulls without a token on the Pi.
4. Set `terminal.docker_image` to the image digest. The next spawn uses it; a changed image recreates the container.
5. Keep an idempotent `~/install_<tool>.sh` in the home bind for heavy stacks that do not belong in the image (JDK, Android SDK, qemu, LibreOffice). Re-run it after any recreate.

## Upstream contract

- The upstream image is built by `NousResearch/hermes-agent` from `docker/sandbox-desktop.Dockerfile`.
- Build triggers: a PR that edits the Dockerfile, the smoke script, or the workflow itself; a completed Stable Release; a Monday 04:23 UTC weekly rebuild; and manual dispatch.
- Tags: `:<version>-desktop` only on a Stable Release run; the weekly and manual runs publish the rolling `:desktop` only.
- Docker Hub API: `https://hub.docker.com/v2/repositories/nousresearch/hermes-sandbox/tags/desktop` returns the manifest-list digest and one child digest per architecture. Pin the arm64 child, not the list digest.
- The upstream smoke runs `docker run -d` and then `docker exec -u pn`; the entrypoint keeps the container alive with no command. Use the same pattern for a self-check.

## Auto-update recipe

- CI daily check: read the arm64 child digest from Docker Hub, compare it with the `org.opencontainers.image.base.digest` label on the published `latest`, and rebuild only when it moves.
- The check job runs on an amd64 runner while the image is arm64 only. `skopeo inspect --config docker://...` selects the index instance by the host architecture, so it fails on an arm64-only index; pass `--override-arch arm64`. An attestation entry with `unknown/unknown` does not count as a matching instance.
- Build on `ubuntu-24.04-arm`. GitHub hosts free arm64 runners for public repos; private repos are billed.
- Push traceability tags (`sha-<12>`, `date-YYYYMMDD`, `upstream-<digest12>`), run the image's self-check, then move `latest` with `docker buildx imagetools create`. The digest is the pin; the tags are labels, and a second build on the same day (or the same upstream digest) overwrites them. A failed build or smoke leaves `latest` on the previous image.
- The Pi timer: pull `latest`, read the local digest with `podman image inspect --format '{{.Digest}}'`, run the self-check, pin the digest in `terminal.docker_image`, restart the user gateway, and roll back if the gateway does not become active.
- Keep the self-check inside the image at `/usr/local/bin/sandbox-selfcheck` so CI and the Pi run the same script.
- Cover the base contract in the self-check, not only the added tools: the `pn` user (uid 1000), `cua-driver --version`, `Xvnc`, the headed Chromium under `/opt/playwright`, and `python3 -c "from PIL import ImageGrab"`. A self-check that tests only the new packages lets a broken display stack reach the gateway.

## Upstream detection and the 60-day schedule risk

- Do not rely on a GitHub `schedule` as the only detector. GitHub disables a scheduled workflow in a public repository after 60 days without repository activity, and the workflow's own runs do not reset that clock. A repo whose only activity is the build workflow is exactly that shape.
- Make the consumer the primary detector. A daily user timer on the host reads the arm64 child digest from the Docker Hub tag API, pulls the current `latest`, reads its `org.opencontainers.image.base.digest` label, and compares. When the label is behind, it records the dispatch time, calls the workflow dispatch API (`POST /repos/<owner>/<repo>/actions/workflows/<file>/dispatches` with `{"ref":"main"}`), polls `/actions/runs?event=workflow_dispatch&branch=main&per_page=5`, and takes the earliest run whose `created_at` is at or after that time. The dispatch API returns no run id; a plain `runs[0]` can read a stale push or a second dispatch. Wait for `completed`, check `conclusion == success`, and pull again.
- The dispatch token is a fine-grained PAT with `actions: read and write` on the one repo, stored in the host `.env` (0600). Scope it to the one repository and rotate it replacement-before-removal. The CI schedule stays as a backup for days the Pi is off.
- Do not build on the Pi. Keep the build in CI; the Pi detects, dispatches, pulls, and switches.

## Switching safely on the host

- Pin the digest, not the tag: `hermes config set terminal.docker_image ghcr.io/<owner>/<image>@sha256:<digest>`. Read the active value with `hermes config get terminal.docker_image | tail -1`; a "not a recognized config key" warning is about the schema, not the value (see hermes-sandbox-ops).
- Store the full image reference in the state file (`active`, `previous`, `failed`), not a bare `sha256:<hex>`. A bare digest in `terminal.docker_image` parses as a repository named `sha256`, so a manual rollback that copies it sets an unpullable reference.
- Save the previous config string exactly (a digest, or the tag on the first run) and restore that string on a failed gateway start. Do not assume the previous value is a digest.
- Verify the rollback restart with the same `is-active` loop; an unchecked rollback can report `rolled-back` while the gateway is down.
- Quarantine a digest that failed the gateway check: record it in the state file and skip it until `latest` points at a different image. Without it, the timer retries the same bad image every day and restarts the gateway twice each time.
- The post-switch check can verify the gateway process, not a live sandbox spawn: the container is created on the first tool call. State that limit instead of promising a spawn check.
- Test hooks: a `TEST_REF` local image for the self-check path, a `GATEWAY_UNIT` override for the rollback path, and a `WAIT_SECONDS` override for the loops. A rollback test that requires pushing a bad image to `latest` is not a test.
- `FORCE_REF` is the hook that continues through the switch; `TEST_REF` exits after the self-check, so it can never exercise the rollback. `FORCE_REF` must skip the noop and quarantine gates: a local copy of the current image has the same digest and otherwise noops before the switch.
- `After=network-online.target` is a no-op in a systemd user unit. Retry the pull in the script (three attempts with increasing sleeps) instead.
- The user service is `Type=oneshot`; systemd disables the start timeout by default for oneshot, so a 20-minute dispatch wait is not capped. Do not add a shorter `TimeoutStartSec`.
- Status file: write one JSON line per run with a consistent schema (`result` plus `active`/`previous`/`failed`/`digest` as they apply). The watcher reads it; an inconsistent schema makes OK/STALE/FAILED ambiguous. Map every result to the watcher's state: `updated`/`noop` are OK when `at` is within 26 hours, otherwise STALE; `quarantined`/`rolled-back` are STALE; `failed` is FAILED; `self-check-ok` is a test-hook state and is ignored. Use the `at` timestamp for staleness.

## Pitfalls

- Check the GHCR package visibility after the first push; it can be public or private depending on the repo and account settings. The Pi's anonymous pull is the gate: if it 401s, set the package public once. A package on a public repo can already be public, so do not assume the step is needed.
- Do not change `USER` or `ENTRYPOINT`. The gateway, the display stack, and the `pn` contract depend on the base.
- `gh` auth lives in `~/.config/gh` on the home bind. Never bake a token into the image.
- Debian's `yq` is the old Python implementation; use mikefarah's binary if needed. `sops` is not in Debian 13.
- `pandoc` and `cmake` are the large additions. Measure the layer size before assuming the image stays small.
- The sandbox container appears on the first tool call, not at gateway start. A post-switch check can verify the gateway, not a live spawn.
- `docker buildx imagetools create` from a pushed tag keeps the digest, so a digest pin on the Pi stays stable across tag moves.
