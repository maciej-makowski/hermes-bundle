# Mermaid diagrams in design docs — validation recipe

Extract each fence before validating (awk between the ```mermaid opener and the closing ``` marker), then render it under the current npm mermaid parser — the same generation as GitHub's renderer.

## Validate (never via kroki.io)

1. One scratch dir: `npm init -y && npm i mermaid jsdom` (~15 s).
2. Extract: `awk '/```mermaid/{n++; f="/tmp/d" n ".mmd"; next} /^```$/{f=""; next} f{print > f}' <doc>.md`
3. Run this skill's `scripts/check-mermaid.js` on the extracted files; exit 1 on any failure, and FAIL lines carry the mermaid parse error.

Why not kroki.io: its mermaid build is version-skewed and 400s VALID current syntax — quoted `subgraph id["title"]` forms and a bare `%` inside a label are the two that bit. Bisecting against it burns dozens of calls proving kroki's skew, not the doc's; both constructs render fine under the current parser.

## Scope of the check

jsdom does no layout, so the harness stubs `SVGElement.prototype.getBBox` with a fixed box: a pass proves the syntax parses and renders, not that the visual layout (node sizing, edge routing) looks right on GitHub. Read the rendered SVG size only as sanity, not as truth.

## Fold conventions

A the operator diagram request folds like any other decision: numbered M-block in the decision record, fresh review round. The Architecture section is the home — the two shapes he asks for are an interaction/federation sequence diagram and an accounts-and-artefacts flowchart. Derive every value shown in a diagram from the doc's own facts (ports, users, cron slots, limits); a diagram that invents or rounds a number is a reviewer finding.
