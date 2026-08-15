# MIDEND Skills Report

## Registry

Added `midend/skills/base.py` and `registry.py`. Skills expose stable metadata,
validation, allowed backend tools, workflow stages, and output schema. Future
skills can be registered without changing the control-plane execution loop.

## SpCas9 skill

`spcas9_gene_cutting` supports raw sequence, validated FASTA/FASTQ/GenBank input
IDs, and indexed genomic regions. It discovers NGG sites, delegates cut-site
geometry and sequence features to VEYRA, optionally requests on-target and
full off-target/CFD evidence, then delegates ranking. It preserves strand,
PAM coordinates, guide orientation, provenance, warnings, and uncertainty.

The skill does not implement biological algorithms and does not claim
experimental cleavage certainty.

## Exposure

Added HTTP routes:

- `GET /skills`
- `GET /skills/{skill_id}`
- `POST /skills/{skill_id}`

Skill executions use the existing execution IDs, tool-call telemetry, SSE
stream, and structured execution result. MIDEND MCP capabilities now include
`list_skills`, `skill_metadata`, and `execute_skill`.

## Verification

Focused MIDEND tests pass, including discovery, invalid-input rejection,
reverse-strand candidate preservation, structured cut-site output, provenance,
and live execution events.

## Known limitations

State remains process-local. Full analysis requires a registered genome and
available backend index/runtime prerequisites. On-target model availability and
off-target tool availability are reported as warnings/partial evidence; no
values are fabricated. Provider token streaming is still lifecycle-level as
documented by the existing integration contract.
