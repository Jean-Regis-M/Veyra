# Scientific Assumptions & Limitations

VEYRA's deterministic engine is a **simplified, illustrative implementation** of CRISPR guide-RNA design and off-target scoring principles, built for a hackathon demo. It is not a validated clinical or research-grade tool. This document exists so nothing in the UI or AI layer overstates what the math actually does.

## What's implemented

- **PAM search**: SpCas9 `NGG` PAM, scanned on both strands of the input sequence.
- **Candidate filtering**: standard 20 nt protospacer length upstream of the PAM, no ambiguous bases (N).
- **GC content**: fraction of G/C in the 20 nt protospacer. Extremely low (<20%) or high (>80%) GC is flagged as lower quality — this is a widely-used heuristic, not a precise efficiency predictor.
- **Off-target search**: mismatch-tolerant scan **within the input sequence/context window only** — there is no genome-wide reference index in this MVP. Any "off-target" found is a near-match elsewhere in the same provided sequence, not a genome-wide result.
- **Seed-region weighting**: mismatches in the 10-12 nt PAM-proximal "seed" region are weighted more heavily than distal mismatches when computing a specificity penalty, reflecting the well-established observation that seed mismatches are more disruptive to Cas9 binding.
- **Ranking**: candidates are ordered by a combined score (GC quality + specificity penalty from off-target/mismatch analysis). This is a simplified heuristic score, not a calibrated efficiency or safety prediction like CFD or a trained model's output.

## What's explicitly NOT implemented (and must not be implied)

- **No chromatin/epigenetic context** — no accessibility, methylation, or 3D genome data. The problem statement's "long-range context blindness" is a real gap this MVP does not fully close; the 3D visualization shows sequence/positional context, not chromatin state.
- **No genome-wide off-target index** (no reference genome alignment/BWA/Bowtie-style search).
- **No wet-lab validated efficiency model** (no CFD, no Rule Set 2/3, no trained deep model) — scores are heuristic, not empirically calibrated.
- **No clinical or regulatory validity.** Nothing here should be presented as diagnostic, treatment-related, or regulatory-grade.

## AI reasoning layer

The AI layer receives the deterministic engine's structured output (candidates + scores + which heuristic produced each number) and generates a plain-language explanation. It must:

- Reference only the numbers it was given — never state a new score.
- Be explicit when it's offering a hypothesis vs. restating a computed fact.
- Inherit the same "illustrative prototype" framing — it should not claim more certainty than the underlying heuristic supports.

## Why these simplifications are acceptable for this MVP

The goal is to demonstrate the **pipeline shape** (deterministic scoring → context → AI interpretation → visualization) end-to-end and to show *transparent, traceable* reasoning — not to ship a clinically accurate off-target predictor in 2 hours. Every simplification above is a scope cut, not a hidden inaccuracy, as long as the UI and AI copy stay honest about it (see the `scientific-review` skill).
