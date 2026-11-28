#!/usr/bin/env python3
"""Gate: exactly one pending fix-node tail, and it must name the expected round.

Usage: python3 check-node-tails.py <doc.md> <expected-round>

Exits 1 on any mismatch, printing every pending tail found. Run it before every
review dispatch: the stale-sibling-tail class is otherwise caught by the reviewer
one node behind, round after round.
"""
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    print("usage: check-node-tails.py <doc.md> <expected-round>")
    sys.exit(2)

doc = Path(sys.argv[1]).read_text(encoding="utf-8")
expected = sys.argv[2].lstrip("R")
pending = re.findall(r"Fix-verification pending \(R(\d+)\)", doc)

problems = []
if len(pending) != 1:
    problems.append(f"expected exactly 1 pending tail, found {len(pending)}: {pending}")
elif pending[0] != expected:
    problems.append(f"pending tail names R{pending[0]}, expected R{expected}")

nodes = len(re.findall(r"^- Rev .*fix round R\d+", doc, flags=re.M))
print(f"nodes: {nodes}, pending tails: {pending}")
for problem in problems:
    print("FAIL:", problem)
sys.exit(1 if problems else 0)
