# Off-target toxicity risk skill

`offtarget_toxicity_risk` is an evidence-gated, interpretable prototype. It
may collect existing VEYRA off-target search evidence, but it does not pretend
that the backend defines the blueprint's scientific features:

- CFD or mismatch count is not the full-locus `Sh` mismatch-penalty feature.
- guide secondary-structure MFE is not gRNA-DNA hybridization `DeltaG_binding`.
- ordinary model attention is not calibrated chromatin accessibility `Ca`.

The audited formula is:

```text
B = abs(DeltaG_binding) / (abs(DeltaG_binding) + epsilon)
z = alpha * Sh + beta * B + gamma * Ca
T = 100 * stable_logistic(z)
```

`Sh` is larger for more mismatch, so calibration is expected to learn a
non-positive alpha for cleavage-risk interpretation. Larger `B` means more
stable binding and larger `Ca` means more accessibility; positive beta/gamma
are expected, but the implementation does not hard-code those signs.

The skill returns `unavailable` or `partial` when features are missing,
`prototype` for a calculated but uncalibrated user-supplied result, and
`complete` only for a calibrated/external-calibration model with all required
features. It never labels guessed coefficients or missing evidence validated.
