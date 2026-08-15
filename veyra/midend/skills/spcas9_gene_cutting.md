# SpCas9 gene-cutting skill

`spcas9_gene_cutting` is an orchestration skill for computationally predicted
SpCas9 candidates. It uses the existing VEYRA `pam_scan` or `pam_scan_region`
tool, then delegates cut-site, feature, on-target, off-target, CFD, and ranking
work to the tools listed in `midend.md`.

It does not calculate biological values itself and never claims experimentally
confirmed cleavage. Missing model, genome, index, or optional runtime evidence
is reported as unavailable/partial evidence, never as a fabricated score.

The structured candidate object is authoritative. `cutting_site_string` is a
display convenience only. Reverse-strand candidates preserve backend PAM
coordinates and use the backend-provided guide orientation.
