# CFD Off-Target Scoring

## What is CFD?

The **Cutting Frequency Determination (CFD)** score is a specificity scoring method for CRISPR/Cas9 off-target sites, described in Doench et al. 2016. It predicts the likelihood that a given off-target site will be cleaved by Cas9, based on:

- **Position-specific mismatch penalties** — how much each type of mismatch at each position reduces cleavage
- **PAM compatibility** — how well the off-target PAM matches the canonical NGG PAM

**Score direction:** Higher CFD score = more likely to be cut = more concerning off-target.

## Source

- **Upstream repository:** https://github.com/maximilianh/crisporWebsite
- **Directory:** `CFD_Scoring/`
- **Reference:** Doench et al., "Optimized sgRNA design to maximize activity and minimize off-target effects of CRISPR-Cas9", Nature Biotechnology, 2016

## Resource Files

| File | Description | Size |
|------|-------------|------|
| `mismatch_score.pkl` | Position-specific mismatch penalty matrix (240 entries) | 6.9 KB |
| `pam_scores.pkl` | PAM dinucleotide score matrix (16 entries) | 344 B |
| `cfd-score-calculator.py` | Upstream Python 2 calculator (reference only) | 2.0 KB |

**Checksums:**
- `mismatch_score.pkl`: `sha256:c58e9c1a85f01e423c35fd02aa5a27a23ab27e95c2e98abdcfc71cf4b2667f4b`
- `pam_scores.pkl`: `sha256:ae486444a9135e3acc1f1b9a3973f1069e84efe7a1738a87d10d523bfb46b37e`

**VEYRA location:** `data/resources/crispor_cfd/`

## Algorithm

```
score = 1.0
for each position i in spacer (1-based):
    if WT[i] != off_target[i]:
        key = "r{WT_RNA_base}:d{revcom(off_target_DNA_base)},{i}"
        score *= mismatch_penalty[key]
score *= PAM_score[off_target_PAM]
```

1. Convert T→U (RNA convention) for both spacer and off-target
2. For each mismatch position, look up the penalty using the key format `r<wt_rna>:d<revcom(off_dna)>,<pos>`
3. Multiply all penalties together
4. Multiply by the PAM score (last 2 nt of the off-target sequence)

## Mismatch Key Format

The key format `r{wt}:d{rc},{pos}` encodes:
- `r{wt}` — RNA base from the wild-type spacer (A, C, G, U)
- `d{rc}` — DNA reverse complement of the off-target base at that position
- `{pos}` — 1-based position in the spacer

Example: A mismatch where WT has `A` and off-target has `G` at position 10:
- revcom(G) = C
- Key: `rA:dC,10`
- Penalty: 0.5556

## PAM Scores

| PAM | Score | Notes |
|-----|-------|-------|
| GG | 1.0 | Canonical SpCas9 PAM |
| AG | 0.2593 | Reduced activity |
| GA | 0.0694 | Low activity |
| GC | 0.0222 | Very low |
| GT | 0.0161 | Very low |
| CG | 0.1071 | Moderate |
| TG | 0.0390 | Low |
| All others | 0.0 | No activity |

## VEYRA Implementation

VEYRA implements the CFD algorithm in `mcp/tools/score_offtargets.py`:

- `calc_cfd(wt, sg, pam)` — score a single off-target
- `score_offtargets(spacer, candidates, pam_pattern)` — score a list of candidates

**Function signature:** `score_offtargets(spacer_sequence, candidates, pam_pattern)`

**Input validation:**
- Spacer must be ≥ 15nt
- Off-target protospacer must be ≥ 20nt
- Nucleotide alphabet: A, T, C, G (U accepted, converted to T)

**Output:**
- Each candidate row gets a `cfd_score` field (float, 0–1)
- Summary includes `total_scored`, `mean_cfd`, `max_cfd`, `min_cfd`
- Metadata includes `scoring_source: "CRISPOR CFD"`

## Limitations

- **Not experimentally validated by VEYRA.** CFD is a computational scoring model from Doench et al. 2016.
- **Only for SpCas9** (NGG PAM). Other Cas variants use different PAM rules.
- **No bulge/indel support.** Only mismatches are scored.
- **20nt spacer assumed.** Longer or shorter spacers may produce incorrect scores.

## Usage

### CLI

```bash
python -m cli.main offtarget score \
    --spacer GATTGCCACCAAAGTGATGC \
    --candidates-json candidates.json \
    --pam NGG
```

### Python API

```python
from api import score_offtargets_cfd

result = score_offtargets_cfd(
    spacer_sequence="GATTGCCACCAAAGTGATGC",
    candidates=[...],
    pam_pattern="NGG"
)
```

### HTTP API

```bash
curl -X POST http://localhost:8000/offtarget/score \
    -H "Content-Type: application/json" \
    -d '{"spacer_sequence": "GATTGCCACCAAAGTGATGC", "candidates": [...], "pam_pattern": "NGG"}'
```

### MCP

```python
from mcp.tools.score_offtargets import score_offtargets

result = score_offtargets(
    spacer_sequence="GATTGCCACCAAAGTGATGC",
    candidates=[...],
    pam_pattern="NGG"
)
```

## Missing Resource Behavior

If CFD pickle files are not found, `score_offtargets` returns a structured error:

```json
{
  "errors": ["CFD scoring resources not found: ..."],
  "rows": []
}
```

The system does NOT return `cfd_score = 0` for missing resources — zero would be misleading as it represents real scoring output (no cleavage predicted).
