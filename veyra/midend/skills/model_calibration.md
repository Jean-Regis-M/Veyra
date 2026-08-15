# Model Calibration Skill (`model_calibration`)

The `model_calibration` skill provides deterministic statistical fitting and validation for VEYRA models from user-supplied experimental CSV/TSV datasets.

## Core principles

- **Calibration is OPTIONAL.** Ordinary VEYRA analyses operate without calibration data.
- **Deterministic statistical fitting.** Numerical parameters are fitted via deterministic least-squares without fabricating coefficients.
- **AI isolation.** The AI reasoning layer is provided with structured calibration summaries, sample counts, fitted coefficients, and evaluation metrics—never raw CSV datasets.

## Input requirements

- `calibration_input`: Validated CSV or TSV tabular dataset ID (`calib_...`).
- Optional column overrides: `target_column`, `guide_column`, `sh_column`, `binding_column`, `ca_column`.

## Workflow

1. Validate tabular structure and headers.
2. Normalize rows and filter valid numeric entries.
3. Map experimental columns to semantic model features.
4. Obtain backend-derived features (GC, Tm, homopolymers, secondary structure) for guide sequences.
5. Deterministically fit model coefficients ($\alpha, \beta, \gamma, \epsilon$).
6. Compute evaluation metrics ($R^2$, MSE, MAE, Pearson $r$).
7. Register the calibrated coefficient model in the runtime registry.
8. Generate a structured calibration report.
