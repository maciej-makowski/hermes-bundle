#!/usr/bin/env bash
# Remove every component this repo installed. User data is backed up, never deleted.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$HERMES/backups"

manifest() {
  awk '
    /^[[:space:]]*- id:/ { if (id != "") print id "\t" type "\t" path; id=$3; type=""; path=""; next }
    /^[[:space:]]*type:/ { type=$2 }
    /^[[:space:]]*path:/ { path=$2 }
    END { if (id != "") print id "\t" type "\t" path }
  ' "$ROOT/bundle.yaml"
}

while IFS=$'\t' read -r id type path; do
  case "$type" in
    plugin|catalog-plugin)
      if [ -d "$HERMES/plugins/$id" ]; then
        cp -R "$HERMES/plugins/$id" "$HERMES/backups/$id-$(date -u +%Y%m%dT%H%M%SZ)"
        hermes plugins remove "$id"
      fi ;;
    skill) hermes skills uninstall "$id" --yes || true ;;
    widget|skin|pet)
      dest="$HERMES/$(case "$type" in widget) echo tui-widgets;; skin) echo skins;; pet) echo pets;; esac)"
      target="$dest/$(basename "$path")"
      if [ -n "$target" ] && [ "$target" != "$dest" ] && [ -e "$target" ]; then
        rm -rf -- "$target"
      fi ;;
  esac
done < <(manifest)
