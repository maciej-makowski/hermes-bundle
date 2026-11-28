#!/usr/bin/env bash
# Report drift between installed components and this repo's HEAD.
set -euo pipefail
REPO="maciej-makowski/hermes-bundle"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HERMES="${HERMES_HOME:-$HOME/.hermes}"
CLONE="$(mktemp -d)"; trap 'rm -rf "$CLONE"' EXIT
git clone --depth 1 "https://github.com/$REPO.git" "$CLONE/repo" >/dev/null

status=0
manifest() {
  awk '
    /^[[:space:]]*- id:/ { if (id != "") print id "\t" type "\t" path; id=$3; type=""; path=""; next }
    /^[[:space:]]*type:/ { type=$2 }
    /^[[:space:]]*path:/ { path=$2 }
    END { if (id != "") print id "\t" type "\t" path }
  ' "$ROOT/bundle.yaml"
}

for dir in "$CLONE"/repo/plugins/*/; do
  id="$(basename "$dir")"
  installed="$HERMES/plugins/$id"
  if [ ! -d "$installed" ]; then echo "MISSING plugin: $id"; status=1; continue; fi
  if diff -rq "$dir" "$installed" >/dev/null 2>&1; then echo "ok plugin: $id"; else echo "DRIFT plugin: $id"; status=1; fi
done

hermes plugins check-updates --json 2>/dev/null | python3 -c '
import json,sys
for row in json.load(sys.stdin).get("plugins", []):
    if row.get("update_available"): print("UPDATE:", row.get("name"))
' || true

for surface in tui-widgets skins pets; do
  for src in "$CLONE"/repo/"$surface"/*; do
    [ -e "$src" ] || continue
    name="$(basename "$src")"
    if diff -rq "$src" "$HERMES/$surface/$name" >/dev/null 2>&1; then echo "ok $surface: $name"; else echo "DRIFT $surface: $name"; status=1; fi
  done
done

while IFS=$'\t' read -r id type path; do
  [ "$type" = "skill-local" ] || continue
  installed="$HERMES/skills/$id"
  if [ ! -d "$installed" ]; then echo "MISSING skill-local: $id"; status=1; continue; fi
  if diff -rq "$CLONE/repo/$path" "$installed" >/dev/null 2>&1; then echo "ok skill-local: $id"; else echo "DRIFT skill-local: $id"; status=1; fi
done < <(manifest)

exit "$status"
