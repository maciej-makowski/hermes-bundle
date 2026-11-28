#!/usr/bin/env python3
"""Gate the rev-history of a design doc: exactly one pending fix-verification tail, and it
must name the round under review.

Usage: python3 check-tails.py <doc.md> <expected-round|none>

Pass `none` once the loop has closed: the gate then requires zero pending tails.

Run it after every fix batch and before dispatching the verification round. A stale
'Fix-verification pending (RN)' tail on an older node is a false record the reviewer
flags, and resolving only the newest node re-creates the bug every round.
"""
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit(__doc__)

doc = Path(sys.argv[1]).read_text()
expected = sys.argv[2].lstrip("R").lower()
pending = re.findall(r"Fix-verification pending \(R(\d+)\)", doc)

problems = []
if expected == "none":
    if pending:
        problems.append(f"expected no pending tails, found {pending}")
elif len(pending) != 1:
    problems.append(f"expected exactly 1 pending tail, found {len(pending)}: {pending}")
elif pending[0] != expected:
    problems.append(f"pending tail names R{pending[0]}, expected R{expected}")

nodes = len(re.findall(r"- Rev \d+, fix round R\d+", doc))
print(f"nodes: {nodes}, pending tails: {pending}")
if problems:
    for p in problems:
        print("FAIL:", p)
    sys.exit(1)
print("OK")
