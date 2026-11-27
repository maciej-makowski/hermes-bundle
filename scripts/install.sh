#!/usr/bin/env bash
# Install every component in bundle.yaml. Non-interactive when --yes is set.
set -euo pipefail

REPO="maciej-makowski/hermes-bundle"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." 2>/dev/null && pwd || true)"
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
skill_installed() { hermes skills list --source hub 2>/dev/null | grep -qx "$1"; }

clone_once() {
  if [ -z "${CLONE:-}" ]; then
    CLONE="$(mktemp -d)"
    trap 'rm -rf "$CLONE"' EXIT
    run git clone --depth 1 "https://github.com/$REPO.git" "$CLONE/repo" >/dev/null
  fi
  printf '%s' "$CLONE/repo"
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
  local src; src="$(clone_once)/$path"
  run mkdir -p "$dest"
  run cp -R "$src" "$dest/"
}

TAP_ADDED=0
while IFS=$'\t' read -r id type path en; do
  [ -n "$COMPONENT" ] && [ "$id" != "$COMPONENT" ] && continue
  case "$type" in
    plugin) install_plugin "$id" "$REPO/$path" ;;
    catalog-plugin) install_plugin "$id" "$id" ;;
    skill)
      if [ "$TAP_ADDED" -eq 0 ]; then run hermes skills tap add "$REPO"; TAP_ADDED=1; fi
      install_skill "$id" "$path" ;;
    widget|skin|pet) copy_component "$type" "$id" "$path" ;;
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
        if [ "$(plugin_installed "$id")" != "True" ]; then echo "FAIL: $id not installed" >&2; exit 1; fi
        if [ "$en" = "true" ] && [ "$ENABLE_MODE" != "off" ]; then
          if ! hermes plugins list --json 2>/dev/null | grep -q "\"name\": \"$id\""; then
            echo "FAIL: $id missing after enable" >&2; exit 1
          fi
        fi ;;
      skill)
        if ! skill_installed "$id"; then echo "FAIL: skill $id not installed" >&2; exit 1; fi ;;
      widget|skin|pet)
        if [ ! -e "$HERMES/$path" ] && [ ! -e "$HERMES/$(basename "$path")" ]; then echo "FAIL: $id not copied" >&2; exit 1; fi ;;
    esac
  done < <(manifest)
  echo "OK"
fi
