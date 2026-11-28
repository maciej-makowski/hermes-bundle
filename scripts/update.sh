#!/usr/bin/env bash
# Update every component. Per-name plugin updates; skills and copy-type re-sync.
set -euo pipefail
REPO="maciej-makowski/hermes-bundle"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES="${HERMES_HOME:-$HOME/.hermes}"

manifest() {
  awk '
    /^[[:space:]]*- id:/ { if (id != "") print id "\t" type "\t" path; id=$3; type=""; path=""; next }
    /^[[:space:]]*type:/ { type=$2 }
    /^[[:space:]]*path:/ { path=$2 }
    END { if (id != "") print id "\t" type "\t" path }
  ' "$ROOT/bundle.yaml"
}

CLONE=""
need_clone() {
  [ -n "$CLONE" ] || { CLONE="$(mktemp -d)"; trap 'rm -rf "$CLONE"' EXIT; git clone --depth 1 "https://github.com/$REPO.git" "$CLONE/repo" >/dev/null; }
}

while IFS=$'\t' read -r id type path; do
  case "$type" in
    plugin|catalog-plugin)
      hermes plugins update "$id" || echo "WARN: update failed for $id" >&2 ;;
    skill)
      hermes skills update || true ;;
    skill-local)
      need_clone
      dest="$HERMES/skills/$id"
      src="$CLONE/repo/$path"
      if [ -d "$dest" ] && ! diff -rq "$src" "$dest" >/dev/null 2>&1; then
        mkdir -p "$HERMES/backups"
        cp -R "$dest" "$HERMES/backups/$id-$(date -u +%Y%m%dT%H%M%SZ)"
        echo "archived diverged copy: $id"
      fi
      mkdir -p "$HERMES/skills"; cp -R "$src" "$HERMES/skills/" ;;
    widget|skin|pet)
      need_clone
      dest="$HERMES/$(case "$type" in widget) echo tui-widgets;; skin) echo skins;; pet) echo pets;; esac)"
      src="$CLONE/repo/$path"
      if [ -e "$dest/$(basename "$path")" ] && ! diff -rq "$src" "$dest/$(basename "$path")" >/dev/null 2>&1; then
        mkdir -p "$HERMES/backups"
        cp -R "$dest/$(basename "$path")" "$HERMES/backups/$(basename "$path")-$(date -u +%Y%m%dT%H%M%SZ)"
        echo "archived diverged copy: $(basename "$path")"
      fi
      mkdir -p "$dest"; cp -R "$src" "$dest/" ;;
  esac
done < <(manifest)
