#!/usr/bin/env python3
"""Footprint census for a design-doc fold: changed-line counts per section.

Usage: python3 fold-census.py <pre-fold-base.md> <staged-doc.md>

Prints per-heading changed-line counts (both directions) plus totals. The fold
rules require this census from the ACTUAL diff before composing an M-block's
Touches claims or a reviewer dispatch: run it against the byte-verified base
(fetch the pre-fold blob from main first) and the staged doc."""
import difflib
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: fold-census.py <base.md> <staged-doc.md>")

base = open(sys.argv[1], encoding="utf-8").read().splitlines()
doc = open(sys.argv[2], encoding="utf-8").read().splitlines()

heads = []
for i, line in enumerate(doc, 1):
    if line.startswith("## ") or line.startswith("### "):
        heads.append((i, line))


def section_of(new_ln):
    best = "(preamble)"
    for ln, title in heads:
        if ln <= new_ln:
            best = title
        else:
            break
    return best


sm = difflib.SequenceMatcher(None, base, doc, autojunk=False)
census = {}
added = removed = 0
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal":
        continue
    for j in range(j1, j2):
        sec = section_of(j + 1)
        census[sec] = census.get(sec, 0) + 1
    added += j2 - j1
    removed += i2 - i1

print(f"base: {len(base)} lines, doc: {len(doc)} lines, +{added}/-{removed} changed lines")
for sec, n in sorted(census.items(), key=lambda kv: -kv[1]):
    print(f"  {n:4}  {sec[:100]}")
