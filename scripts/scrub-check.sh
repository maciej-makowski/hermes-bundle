#!/usr/bin/env bash
# Section 7.1 gate: no machine-specific content in skills/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
fail=0

if grep -rIniE 'rpi5\b|rpi4b|hermes-pi|maciek|maciej|makowski|@maciej|maciej\.dev|192\.168\.|10\.[0-9]+\.[0-9]+\.|172\.(1[6-9]|2[0-9]|3[01])\.' skills/*/ 2>/dev/null; then
  echo "FAIL: identity or address pattern in skills/" >&2; fail=1
fi

if [ -s scripts/private-names.txt ]; then
  if grep -rIniF -f scripts/private-names.txt skills/*/ 2>/dev/null; then
    echo "FAIL: private name in skills/" >&2; fail=1
  fi
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    if [ -d "skills/$name" ]; then
      echo "FAIL: private name '$name' matches a shipped skill directory" >&2; fail=1
    fi
  done < scripts/private-names.txt
fi

[ "$fail" -eq 0 ] && echo "scrub gate: clean"
exit "$fail"
