#!/usr/bin/env bash
# Install every component in bundle.yaml. Non-interactive when --yes is set.
set -euo pipefail

REPO="maciej-makowski/hermes-bundle"
_src="${BASH_SOURCE[0]:-$0}"
ROOT="$(cd "$(dirname "$_src")/.." 2>/dev/null && pwd)" || ROOT=""
HERMES="${HERMES_HOME:-$HOME/.hermes}"
COMPONENT=""; REF=""; DRY=0; YES=0; DEPS=0; FORCE=0; CAUTION=0; ENABLE_MODE="default"

# When piped (curl ... | bash) there is no repo checkout; fetch the manifest.
MANIFEST="$ROOT/bundle.yaml"
if [ ! -f "$MANIFEST" ]; then
  MANIFEST="$(mktemp)"
  curl -fsSL "https://raw.githubusercontent.com/$REPO/main/bundle.yaml" -o "$MANIFEST"
  trap 'rm -f "$MANIFEST"' EXIT
fi

usage() {
  cat <<'EOF'
install.sh [--component ID] [--ref SHA] [--dry-run] [--enable|--no-enable] [--yes] [--yes-deps] [--force] [--allow-caution]

  --component ID   install one component from bundle.yaml
  --ref SHA        pin the plugin install to a full 40-character commit
  --dry-run        print the exact commands, run nothing
  --enable         enable installed plugins (default for components with enable: true)
  --no-enable      install disabled; the enable step is skipped
  --yes            non-interactive; required without a TTY
  --yes-deps       answer the Python dependency consent prompt
  --force          reinstall over an existing copy
  --allow-caution  pass --force to skills install, accepting a caution scan verdict
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --component) COMPONENT="${2:?}"; shift 2 ;;
    --ref) REF="${2:?}"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --yes) YES=1; shift ;;
    --yes-deps) DEPS=1; shift ;;
    --force) FORCE=1; shift ;;
    --allow-caution) CAUTION=1; shift ;;
    --enable) ENABLE_MODE="on"; shift ;;
    --no-enable) ENABLE_MODE="off"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown flag: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ ! -t 0 ] && [ "$YES" -ne 1 ]; then
  echo "refusing to run without a TTY unless --yes is set" >&2
  exit 2
fi

run() {
  if [ "$DRY" -eq 1 ]; then printf 'DRY: %s\n' "$*"; else "$@"; fi
}

manifest() {
  awk '
    /^[[:space:]]*- id:/ { if (id != "") print id "\t" type "\t" path "\t" en; id=$3; type=""; path=""; en=""; next }
    /^[[:space:]]*type:/ { type=$2 }
    /^[[:space:]]*path:/ { path=$2 }
    /^[[:space:]]*enable:/ { en=$2 }
    END { if (id != "") print id "\t" type "\t" path "\t" en }
  ' "$MANIFEST"
}

plugin_installed() {
  local out
  out="$(hermes plugins list --json 2>/dev/null || true)"
  if [ -z "$out" ]; then echo False; return 0; fi
  printf '%s' "$out" | python3 -c '
import json, sys
data = json.load(sys.stdin)
rows = data if isinstance(data, list) else data.get("plugins", [])
print(any(r.get("name") == sys.argv[1] for r in rows))
' "$1" 2>/dev/null || echo False
}
skill_installed() {
  hermes skills list --source hub 2>/dev/null | awk -v s="$1" '$1==s {found=1} END {exit(found?0:1)}'
}

ensure_clone() {
  if [ -n "${CLONE:-}" ]; then return 0; fi
  CLONE="$(mktemp -d)"
  trap 'rm -rf "$CLONE"' EXIT
  run git clone --depth 1 "https://github.com/$REPO.git" "$CLONE/repo" >/dev/null
}

install_plugin() {
  local id="$1" src="$2"
  local enable_flag="--enable"
  [ "$ENABLE_MODE" = "off" ] && enable_flag="--no-enable"
  if [ "$(plugin_installed "$id")" = "True" ] && [ "$FORCE" -ne 1 ]; then
    echo "already installed, skipping: $id"; return 0
  fi
  local args=(hermes plugins install "$src" "$enable_flag")
  [ -n "$REF" ] && args+=(--ref "$REF")
  [ "$DEPS" -eq 1 ] && args+=(--yes-deps)
  [ "$FORCE" -eq 1 ] && args+=(--force)
  run "${args[@]}"
  if [ "$ENABLE_MODE" != "off" ] && [ "$(plugin_installed "$id")" = "True" ]; then
    run hermes plugins enable "$id"
  fi
}

install_skill() {
  local id="$1" path="$2"
  if skill_installed "$id" && [ "$FORCE" -ne 1 ]; then
    echo "already installed, skipping: $id"; return 0
  fi
  if skill_installed "$id" && [ "$FORCE" -eq 1 ]; then
    run hermes skills uninstall "$id" --yes
  fi
  local args=(hermes skills install "$REPO/$path" --yes)
  if [ "$CAUTION" -eq 1 ]; then
    echo "accepting a caution scan verdict for $id (--allow-caution)"
    args+=(--force)
  fi
  run "${args[@]}"
}

copy_component() {
  local type="$1" id="$2" path="$3" dest=""
  case "$type" in
    widget) dest="$HERMES/tui-widgets" ;;
    skin) dest="$HERMES/skins" ;;
    pet) dest="$HERMES/pets" ;;
    *) echo "unknown copy type: $type" >&2; return 2 ;;
  esac
  local src; ensure_clone; src="$CLONE/repo/$path"
  run mkdir -p "$dest"
  run cp -R "$src" "$dest/"
}

copy_skill_local() {
  local id="$1" path="$2"
  local dest="$HERMES/skills/$id"
  if [ "$DRY" -eq 1 ]; then
    printf 'DRY: cp -R %s %s/skills/\n' "$path" "$HERMES"
    return 0
  fi
  local src; ensure_clone; src="$CLONE/repo/$path"
  if [ -d "$dest" ] && [ "$FORCE" -ne 1 ] && diff -rq "$src" "$dest" >/dev/null 2>&1; then
    echo "already installed, skipping: $id"; return 0
  fi
  if [ -d "$dest" ]; then
    mkdir -p "$HERMES/backups"
    cp -R "$dest" "$HERMES/backups/$id-$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  mkdir -p "$HERMES/skills"
  cp -R "$src" "$HERMES/skills/" || return 1
  [ -f "$dest/SKILL.md" ] || { echo "copy failed: $dest" >&2; return 1; }
  echo "copied $id into $HERMES/skills (a copied skill is not scanned by the tap)"
}

TAP_ADDED=0
FAILURES=0
fail() { echo "FAILED: $*" >&2; FAILURES=$((FAILURES + 1)); }

while IFS=$'\t' read -r id type path en; do
  [ -n "$COMPONENT" ] && [ "$id" != "$COMPONENT" ] && continue
  case "$type" in
    plugin) install_plugin "$id" "$REPO/$path" || fail "$id" ;;
    catalog-plugin) install_plugin "$id" "$id" || fail "$id" ;;
    skill)
      if [ "$TAP_ADDED" -eq 0 ]; then
        run hermes skills tap add "$REPO" || fail "tap"
        TAP_ADDED=1
      fi
      install_skill "$id" "$path" || fail "$id" ;;
    skill-local) copy_skill_local "$id" "$path" || fail "$id" ;;
    widget|skin|pet) copy_component "$type" "$id" "$path" || fail "$id" ;;
    desktop-plugin) echo "manual: install $id from the Desktop Install from Git dialog, pinned to a reviewed commit" ;;
    *) echo "unknown component type for $id: $type" >&2; exit 2 ;;
  esac
done < <(manifest)

if [ "$DRY" -eq 0 ]; then
  echo "post-check:"
  while IFS=$'\t' read -r id type path en; do
    [ -n "$COMPONENT" ] && [ "$id" != "$COMPONENT" ] && continue
    case "$type" in
      plugin|catalog-plugin)
        if [ "$(plugin_installed "$id")" != "True" ]; then fail "$id not installed"; fi
        if [ "$en" = "true" ] && [ "$ENABLE_MODE" != "off" ]; then
          if ! hermes plugins list --json 2>/dev/null | grep -q "\"name\": \"$id\""; then
            fail "$id missing after enable"
          fi
        fi ;;
      skill)
        if ! skill_installed "$id"; then fail "skill $id not installed"; fi ;;
      skill-local)
        if [ ! -f "$HERMES/skills/$id/SKILL.md" ]; then fail "skill $id not copied"; fi ;;
      widget|skin|pet)
        if [ ! -e "$HERMES/$path" ] && [ ! -e "$HERMES/$(basename "$path")" ]; then fail "$id not copied"; fi ;;
    esac
  done < <(manifest)
  if [ "$FAILURES" -gt 0 ]; then
    echo "$FAILURES component(s) did not install; the rest are in place. A 'dangerous' scan verdict cannot be overridden; a blocked skill needs a reword or has to stay local." >&2
    exit 1
  fi
  echo "OK"
fi
