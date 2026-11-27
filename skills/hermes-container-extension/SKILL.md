---
name: hermes-container-extension
description: Extend and update the Hermes sandbox image.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Hermes Container Extension Guide

This skill documents how to extend the Hermes agent container image and manage its systemd quadlet configuration.

## System Overview

The Hermes agent runs on a Raspberry Pi using podman quadlets managed by systemd. The setup includes:

- Container image built from `/home/cfiet-hermes/host-setup/images/hermes/Containerfile`
- Quadlet configuration in `/home/cfiet-hermes/host-setup/quadlets/hermes.container`
- Access to host resources via volume mounts and network configuration
- Integration with Cloudflare Tunnel for external access

## Extending the Container Image

**Reality check.** On the host the agent runs in the gateway's `terminal.backend: docker` sandbox (podman, Debian 13), not inside the quadlet this skill describes, and the host user is `hermes`, so the `/home/cfiet-hermes/...` paths below are stale. For the sandbox, the durable-install route is a derived image set via `terminal.docker_image` (base: the documented default `nousresearch/hermes-sandbox:desktop`; verify the running tag on the host). Independently of deployment: apt/pip installs inside the sandbox are container-local and die at every recreate, while the home bind survives, so keep an idempotent `~/install_<tool>.sh` in the home and re-run it after a swap; credential dirs (`~/.config/gh`, `~/.android`) survive while the binaries do not. Measured base gaps: gh, ffmpeg, pdftotext, sqlite3, pandoc, yq, shellcheck, age, sops, cmake, zstd, JDK.

For the derived-image build, publish, and auto-update recipe, see `references/derived-sandbox-image.md`.

To add new tools to the Hermes container:

1. **Modify the Containerfile**:
   - Edit `/home/cfiet-hermes/host-setup/images/hermes/Containerfile`
   - Add installation commands for your desired tool
   - Example for adding GitHub CLI (gh):
     ```
     # Install GitHub CLI (gh)
     RUN apt-get update && apt-get install -y wget gnupg && \
         mkdir -p /etc/apt/keyrings && \
         wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null && \
         chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
         echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
         apt-get update && \
         apt-get install -y gh
     ```

2. **Rebuild the image**:
   ```bash
   cd /home/cfiet-hermes/host-setup
   docker build -t localhost/hermes-agent-google:v2026.6.19 -f images/hermes/Containerfile images/hermes
   ```

3. **Restart the service**:
   ```bash
   systemctl --user restart hermes.container
   ```

## Checking for Upstream Updates

Before bumping the upstream tag in the Containerfile, check whether a newer base image exists:

1. **List available Docker Hub tags** (newest first):
   ```bash
   curl -s "https://hub.docker.com/v2/repositories/nousresearch/hermes-agent/tags?page_size=25" \
     | python3 -c "import json,sys; [print(t['name']) for t in json.load(sys.stdin)['results']]"
   ```
   Compare the latest `vYYYY.M.D` tag against the one in your `FROM` line.

2. **Read the release notes** to understand what changed and whether config migration is needed:
   - Navigate to https://github.com/NousResearch/hermes-agent/releases
   - Look for the matching tag — release notes list new features, breaking changes, and migration steps
   - Or fetch via API: `curl -s "https://api.github.com/repos/NousResearch/hermes-agent/releases?per_page=3"`

3. **If there's a newer version**, follow the rebuild steps below (bump the `FROM` tag and the local image tag together).

4. **After rebuilding**, run config migration inside the container:
   ```bash
   podman exec hermes hermes config check    # see what's stale
   podman exec hermes hermes config migrate  # apply updates
   ```

The Docker Hub `latest` and `main` tags are rolling — they may stay in sync with the latest dated release, or `main` may carry unreleased changes. Pin to a dated tag (`v2026.X.Y`) for stability.

## Managing the Service

The Hermes container is managed via systemd quadlets:

- **Start**: `systemctl --user start hermes.container`
- **Stop**: `systemctl --user stop hermes.container`
- **Restart**: `systemctl --user restart hermes.container`
- **Status**: `systemctl --user status hermes.container`

## Session Persistence

When the container restarts:
- Sessions are preserved in `/home/cfiet-hermes/.hermes/` volume mount
- The conversation context is maintained through the SQLite session store
- All skills and configuration persist in the mounted volume

To resume work after a restart, simply start the container service. Hermes will automatically resume with the previous conversation state.

## Access to Host Resources

The container has access to:
- Host filesystem via volume mounts (`~/.hermes` and `~/`)
- Host podman socket for container management
- Network configuration to communicate with host services

## Adding Authenticated Tools (e.g. `gh` CLI)

When adding tools that need authentication (like `gh`), **don't rely on environment variables** for the token. Hermes' `security.redact_secrets` (on by default) replaces token-looking values with `***` in tool shell sessions. Setting `GH_TOKEN` in `~/.hermes/.env` won't help — the Hermes process sees it, but the terminal tool's shell gets the redacted version.

### Pattern: Mount the tool's config directory

For `gh`, authenticate on the host, then mount `~/.config/gh` into the container:

```bash
# In the quadlet .container file, add:
Volume=%h/.config/gh:/opt/data/home/.config/gh
```

The container's `$HOME` is `/opt/data/home`, so `gh` finds its credentials at `/opt/data/home/.config/gh/hosts.yml`. No env var needed — `gh auth login` persists credentials there.

This pattern works for any CLI tool that stores auth in `~/.config/` or `~/.<tool>/`: