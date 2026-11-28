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

# Every file the repo ships must exist and match in the installed copy. Extra files the
# runtime writes there (__pycache__, state) are not drift.
first_diff() {
  local repo="$1" inst="$2" rel
  while IFS= read -r rel; do
    cmp -s "$repo/$rel" "$inst/$rel" || { printf '%s' "$rel"; return 0; }
  done < <(cd "$repo" && find . -type f -not -path './__pycache__/*' -not -name '*.pyc' \
             -not -path './.git/*' -not -path './node_modules/*' -not -path './.pytest_cache/*' \
             | sed 's|^\./||')
  return 1
}

for dir in "$CLONE"/repo/plugins/*/; do
  id="$(basename "$dir")"
  installed="$HERMES/plugins/$id"
  if [ ! -d "$installed" ]; then echo "MISSING plugin: $id"; status=1; continue; fi
  if rel="$(first_diff "$dir" "$installed")"; then
    echo "DRIFT plugin: $id ($rel)"; status=1
  else
    echo "ok plugin: $id"
  fi
done

hermes plugins check-updates --json 2>/dev/null | python3 -c '
import json,sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
rows = d if isinstance(d, list) else d.get("plugins", [])
for row in rows:
    if isinstance(row, dict) and row.get("update_available"):
        print("UPDATE:", row.get("name"))
' || true

for surface in tui-widgets skins pets; do
  for src in "$CLONE"/repo/"$surface"/*; do
    [ -e "$src" ] || continue
    name="$(basename "$src")"
    case "$name" in README.md) continue ;; esac
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
