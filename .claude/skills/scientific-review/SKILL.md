---
name: scientific-review
description: Use before shipping any UI copy, score, or AI-generated explanation that presents genomic/CRISPR analysis results — checks for fabricated numbers or unsupported clinical claims.
---

# Scientific Review

Checklist to run over any screen or response that shows analysis output:

1. **Every score has a traceable source.** Can you point to the exact deterministic-engine function ([[genomic-engine]]) that produced this number? If not, it must not be displayed as a score.
2. **AI text is labeled as interpretation, not fact.** Phrases like "may indicate", "based on the seed-mismatch pattern above" are fine. Presenting AI output as an independent measurement is not.
3. **No clinical/regulatory language.** No "safe to use", "approved", "diagnostic", "recommended dose/treatment". This is a research prototype — say so where it matters (e.g. results page footer).
4. **No invented references or data.** Don't cite a paper, database ID, or off-target site that wasn't actually looked up or computed.
5. **Off-target scope is honest.** If off-target search only covers the provided sequence/context window (no genome-wide index — see docs/scientific-assumptions.md), the UI must not imply genome-wide coverage.

If a screen fails any check, fix the copy or the data source before merging — don't just soften the wording around a fabricated number.
