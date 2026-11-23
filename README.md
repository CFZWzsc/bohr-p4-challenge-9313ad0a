# Runtime contract

Bohrium Playground Period 4 submission — challenge `challenge-9313ad0a` (track: `academic-writing`).

This repository holds the complete skill package for the challenge: the skill
definition, its executable entry point and all supporting scripts. No precomputed
answers, private data or credentials are included.

## Skill

- Name: `evidence-mindmap-builder`
- Summary: Use when a case supplies notes, a paper section, or a project brief and asks for a mind map or concept structure; parses headings and paragraphs into a typed node tree (question, method, evidence, conclusion, risk, limitation, task), attaches a source- and character-level evidence locator to each node, reports per-material coverage, detects duplicates and overloaded branches, adds causal/contrast edges, and emits Mermaid plus JSON in /app/output/result.json while preserving case_id and every output_contract field. Deterministic standard library only; no network.

## Contents

| File |
|------|
| `SKILL.md` |
| `scripts/run_skill.py` |
| `README.md` |

## How to run

```bash
python scripts/run_skill.py --case /input/case.json --output /app/output/result.json
```

The entry point is `SKILL.md`; input/output contracts, error handling and a minimal
usage example are documented there.

## Notes

- Pure Python standard library; no network access required.
- The result JSON keeps the input case id, the main results, per-item evidence,
  a run status and an uncertainty section.
