# CI-built arm64 images for the Pi fleet (GitHub Actions)

The standing rule lives in SKILL.md: images are built in CI, never on the Pi. This file is the working recipe when no upstream arm64 image fits the target hardware, plus how to monitor runs when the agent's toolset cannot reach the Actions API.

## Cross-compile on a standard amd64 runner (no QEMU)

1. `apt-get install -y --no-install-recommends g++-aarch64-linux-gnu gcc-aarch64-linux-gnu cmake`.
2. `rustup update stable` BEFORE `rustup target add aarch64-unknown-linux-gnu` — `rustup update` replaces the toolchain and installed targets do not carry across versions (symptom: E0463 "can't find crate for `core`" on the first crate).
3. A project can pin a toolchain via `rust-toolchain.toml`; rustup targets are PER-TOOLCHAIN. After cloning, resolve what cargo will actually use — `rustup show active-toolchain` run INSIDE the project — and `rustup target add ... --toolchain "$TC"`. E0463 recurring after a correctly-ordered `target add` means the target landed on a different toolchain than the build uses.
4. C/C++ deps driven by pkg-config (RustDB's io-uring → liburing is the common one): cross pkg-config refuses without a sysroot ("pkg-config has not been configured to support cross-compilation"). Build the C dep for the target arch into a minimal sysroot — clone it, `CC=<target-gcc> ./configure && make && make install DESTDIR=/opt/target-sysroot`, keep it static-only (delete the .so files so the final binary carries no runtime dep on the sysroot) — then export `PKG_CONFIG_ALLOW_CROSS=1`, `PKG_CONFIG_SYSROOT_DIR=/opt/target-sysroot`, `PKG_CONFIG_PATH=<sysroot pkgconfig dir>` (GITHUB_ENV so later steps inherit).
5. Some build scripts consume only the LIBS half of the pkg-config probe, not Cflags — the compile then dies with `fatal error: <header>.h: No such file or directory` even though the probe passed and the feature macro was defined. Inject the include path directly: `CFLAGS`/`CXXFLAGS` with `-I<sysroot>/usr/include` (cc-rs passes both through; an extra -I is harmless for the other -sys crates).
6. Guard the cargo step with `... | tee build.log | tail -5; exit "${PIPESTATUS[0]}"` — the default Actions bash has `-e` but NOT `pipefail`, so a bare pipe through tee masks the compiler's exit code, and the teed log doubles as machine-readable failure evidence.
7. Runtime image: COPY-only arm64 stage (no RUN steps → buildx needs no emulation). Copy `libstdc++.so.6` + `libgcc_s.so.1` from the cross toolchain next to the binary and set `LD_LIBRARY_PATH`.
8. Slim bases (debian:*-slim) ship NO CA certificates — COPY the bundle (`/etc/ssl/certs/ca-certificates.crt` from the runner) and set `SSL_CERT_FILE`/`SSL_CERT_DIR`. Without it the app's TLS client builder dies at startup with a bare `Request error: builder error` long before any request is made.

## jemalloc page size (the Pi 5 16K-page kernel)

- Rust binaries bundling jemalloc (tikv-jemalloc-sys) default to 4K allocator granularity on aarch64; on a 16K-page kernel they abort at startup (`<jemalloc>: Unsupported system page size`, often systemd exit 133 with no useful log). Page size is compile-time — the env fix must be in the build: `JEMALLOC_SYS_WITH_LG_PAGE=14` (16K granularity runs on 4K and 16K hosts; granularity must be ≥ the runtime page size — a 4K build can't be fixed at runtime).
- Check the host with `getconf PAGESIZE`. A native on-host build (`LG_PAGE=14` + plain user unit, no container) is the no-CI fallback; the CI cross-compile with the same env keeps the container model.

## Run monitoring when the Actions API is unreachable

The external GitHub MCP connector carries no Actions endpoints, and a private ghcr package 403s anonymous manifest probes — so neither run status nor publish-success is observable from outside without help. Make the workflow publish its own state:

- On success, create a release `image-<tag>` (body: image refs); on failure, create `failed-<run_id>` with the build-log tail as the body. Both readable via `list_releases` / `get_latest_release`.
- Put the marker steps at the END of the job — a mid-job `if: success()` marker fires before later steps (image push) can fail and lies about the outcome.
- Don't mark the failure release as a prerelease if the reader polls `/releases/latest` — it excludes prereleases; `list_releases` sees them either way.
- If gh is authorized for the repo: poll `gh api repos/<o>/<r>/actions/runs/<id>` in a background loop with notify — `gh run watch` itself aborts on the annotations 403 (token lacks the checks scope); and `--log-failed` may NOT contain a build script's stderr when cc-rs swallows it — read the failed-<run_id> release body (the teed build log) for the real compiler error.
