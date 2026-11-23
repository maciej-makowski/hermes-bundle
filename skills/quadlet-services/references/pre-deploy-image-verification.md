# Pre-deploy image verification without a container runtime

Purpose: prove a freshly merged ghcr image boots and serves BEFORE the host deploy touches live quadlet state, from inside the agent sandbox (no docker/podman available there). The image carries its own runtime — pull the layers anonymously, extract, and run the image's own interpreter and baked venv.

## 1. Pull anonymously (public ghcr, registry v2 over urllib)

1. `GET https://ghcr.io/token?service=ghcr.io&scope=repository:<owner>/<name>:pull` → `token`.
2. `GET https://ghcr.io/v2/<owner>/<name>/manifests/latest` with Accept: oci-index + docker-list + manifest types → the index.
3. Pick the linux/arm64 manifest; GET it with the manifest Accepts → layers + config digest.
4. Read the config blob first: `Env` (baked MCP_HOST/MCP_PORT), `WorkingDir`, `Cmd` tell you the run contract.
5. Stream every layer blob to `/root/layers/` (1 MB chunks). Save `{token, layers, config}` to a meta file in the same script so re-runs skip re-downloads.

## 2. Extract in layer order

- gzip layers: `tar -xzf`.
- buildx layers may be zstd (magic `28 b5 2f fd`): `apt-get install zstd`, then `zstd -d` each to `.tar` and `tar -xf`.
- Extract 0..N IN ORDER into one root (`/root/<name>-image`); later layers override earlier files.

## 3. Run the baked stack from the extracted root

The extracted tree keeps the image layout. Three adjustments make the image's own interpreter + venv usable outside a runtime:

- **Symlink the image-absolute prefix into place**: baked uv editable-install finders point at build-context paths (`/app/...`), so `ln -sfn /root/<name>-image/app /app`. Also `mkdir -p /app/data` when the server hardcodes its token store there.
- **Loader path**: run `/root/<name>-image/usr/local/bin/python3.X` with `LD_LIBRARY_PATH=/root/<name>-image/usr/local/lib` (libpython lives there). A slim-Debian python binary runs fine on a newer host glibc.
- **Module path**: `PYTHONPATH=<root>/app/<pkg>/.venv/lib/python3.X/site-packages:/app/_shared`. Two traps: the venv's `bin/python3` is a broken symlink outside the image (it targets image-absolute `/usr/local/bin/python3.X`), so invoke the base interpreter directly; and a bare import of the editable path-dependency package fails even though the venv declares it — add its parent dir (`/app/_shared`) to PYTHONPATH as a plain path entry.

Run a sanity import of every runtime dep plus both packages before booting.

## 4. Transport ladder (no real credentials)

Boot in a background terminal session (foreground `&` is refused by the terminal tool): `MCP_BEARER=<throwaway> MCP_PORT=<port> MCP_HOST=127.0.0.1 python -m <pkg>.server`. Then, from a follow-up call:

- initialize, correct bearer → 200 (serverInfo name/version comes back).
- initialize, wrong bearer → 401; no auth header → 401.
- tools/list → the exact tool set and action enums.

Keep the session alive when the live ladder is next; kill it when done.

## 5. Live read ladder (user-supplied credentials, file handoff)

Credentials never pass through chat. **The sandbox bind set is narrow**: `/home/mcp` is invisible, and only selected `/home/hermes` subpaths are mounted (the designs tree) — a staging dir the user creates elsewhere under `/home/hermes` does NOT reach the sandbox. The working handoff is a 0600 file in `/srv/mcp_files/send/` (shared spool; tmpfs volatility is a feature for secrets — it self-wipes at boot, and the copy is removed right after install). Never stage secrets inside the designs tree: that is the canonical repo, and pushed content sits next to it.

1. The user stages client id + secret (and runs the authorize + code exchange himself, per the package README's flow) into `test.env` / `token-store.json`; the agent reads the files and never echoes values.
2. Install the store at the server's hardcoded path (`/app/data/token.json`, 0600). A full exchange payload goes in verbatim (it carries refresh_token, expires_at, athlete id). From a bare access token, synthesize `expires_at = now + 6h` so the idle-refresh loop stays dormant — an early refresh returns the same access token while still rotating the refresh token, which quietly invalidates the pair the user handed over.
3. Fire reads only, in budget (~4-5 reads of the daily bucket): athlete get, one small list page, one downsampled streams call, rate status (the tracker must show the real X-RateLimit numbers).
4. Afterwards: kill the server, shred the token store and the staged test file. The real deploy env stays the user's (host step 20); the staged deploy as the service user proceeds on his word.
