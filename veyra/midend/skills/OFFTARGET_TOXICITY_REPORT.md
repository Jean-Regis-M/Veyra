# Off-target Toxicity Risk Report

## 1. Blueprint formula and audit

Section 4.4 proposes:

```text
T = 100 * sigma(alpha*Sh + beta/DeltaG_binding + gamma*(1-Ca))
```

with negative binding free energy, `Sh=0` for perfect complement and `Sh=1`
for maximal mismatch, and `Ca` as accessibility.

The proposed bounded rewrite is not monotonic in the claimed direction under
the same positive-beta convention. With `x=abs(DeltaG)`, the original binding
term is `beta/(-x)=-beta/x`, whose derivative is positive for beta > 0. The
proposed `-beta*x/(x+epsilon)` has a negative derivative for beta > 0.
Therefore the blueprint's claim that the rewrite preserves the direction is
mathematically false without changing coefficient convention.

The positive `alpha*Sh` term also raises risk as mismatch increases, contrary
to an off-target cleavage-risk interpretation. Finally, positive
`gamma*(1-Ca)` raises risk as accessibility decreases. These directions are
not silently retained.

## 2. Implemented formulation

```text
B = abs(DeltaG_binding) / (abs(DeltaG_binding) + epsilon)
z = alpha*Sh + beta*B + gamma*Ca
T = 100 * stable_logistic(z)
```

`epsilon` defaults to `0.001` kcal/mol and must be finite and positive. The
logistic implementation avoids exponential overflow. `DeltaG_binding` must be
finite and zero or negative; zero is valid and produces `B=0`.

Feature meanings and expected fitted signs:

| Feature | Larger value means | Contribution | Expected sign |
|---|---|---|---|
| `Sh` | more sequence mismatch | `alpha*Sh` | usually negative |
| `B` | more stable binding | `beta*B` | usually positive |
| `Ca` | more accessible chromatin | `gamma*Ca` | usually positive |

These are calibration expectations, not hard-coded biological signs.

## 3. Actual backend evidence

The current VEYRA backend can run `offtarget_search`, `cas_offinder_search`,
`analyze_mismatch_seed`, and `score_offtargets`. Those outputs are retained as
provenance/evidence, but none is silently mapped to exact full-locus `Sh`.
The backend has no gRNA-DNA hybridization binding free-energy provider and no
calibrated chromatin-accessibility provider. `compute_secondary_structure` is
not used as binding DeltaG, and AI/provider attention is not used as `Ca`.

Consequently, ordinary executions return explicit unavailable feature records
and no final toxicity score unless all three features are supplied through an
explicit request.

## 4. Calibration

The coefficient registry records model ID, coefficients, epsilon, feature
definition version, dataset/version, fitting method, status, fitted time, and
metrics. The built-in model is `offtarget_toxicity_prototype` with no
coefficients and `uncalibrated` status. User coefficients are marked
`user_supplied`; they produce `prototype` results only. A result is
`validated: true` only for `calibrated` or `external_calibration` metadata with
an identified dataset and fit metrics.

No GUIDE-seq or other labels were downloaded or fabricated.

## 5. Exposure and tests

The skill is registered at `GET /skills` and executes through the existing
`POST /skills/offtarget_toxicity_risk` execution/SSE system. The same skill is
available through MCP `skill_metadata` and `execute_skill`. Results expose
feature availability, contributions, formula version, calibration, warnings,
errors, and provenance.

Tests cover stable logistic extremes, bounded binding monotonicity, epsilon and
invalid-positive-DeltaG handling, sign semantics, missing evidence, coefficient
validation, calibration status, scientific non-substitution, and exposure.

## 6. Smoke result and limitations

The real smoke execution used spacer `CTAGCCTACGGATCAGCCTC` and the requested
`guideseq_test` genome. The current backend registry exposed only
`ecoli_k12_mg1655`, so genome preflight reported the genome unavailable; the
skill returned `partial`, `validated: false`, null toxicity risk, and explicit
unavailable `Sh`, binding DeltaG, and `Ca`. This is a successful scientifically
honest outcome, not a failed attempt to manufacture a toxicity score. No result
is an experimentally validated toxicity prediction.
