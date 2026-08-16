"""SpCas9 candidate cutting-site orchestration.

This module intentionally contains no biological calculation. It validates
workflow inputs, calls existing VEYRA tools, and assembles their evidence.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

from Bio import SeqIO

from .base import Skill, SkillError, SkillMetadata


SPCAS9_TOOLS = [
    "pam_scan", "pam_scan_region", "compute_cut_site", "compute_gc_content",
    "check_homopolymer_runs", "compute_melting_temp", "compute_secondary_structure",
    "compute_positional_features", "compute_dinucleotide_composition", "compute_seed_gc",
    "predict_ontarget_efficiency", "offtarget_search", "analyze_mismatch_seed",
    "score_offtargets", "rank_candidates",
]


class SpCas9GeneCuttingSkill(Skill):
    metadata = SkillMetadata(
        skill_id="spcas9_gene_cutting",
        name="SpCas9 gene-cutting site prediction",
        description="Find computationally predicted SpCas9 PAM/guide candidates and collect backend evidence.",
        version="1.0.0",
        required_inputs=[{
            "name": "sequence_or_region", "type": "one of sequence, input_id, or genomic region",
            "required": True,
        }],
        optional_inputs=[
            {"name": "calibration_input_id", "type": "string", "default": None},
            {"name": "depth", "type": "string", "default": "quick", "allowed": ["quick", "full"]},
            {"name": "strand", "type": "string", "default": "both", "allowed": ["both", "fwd", "rev"]},
            {"name": "chrom", "type": "string", "default": None},
            {"name": "model", "type": "string", "default": "auto", "allowed": ["auto", "both", "rule_set_3", "rule_set_2", "doench_2014"]},
            {"name": "max_candidates", "type": "integer", "default": 100, "minimum": 1, "maximum": 1000},
        ],
        allowed_tools=SPCAS9_TOOLS,
        workflow=[
            "validate input", "discover NGG PAMs", "compute canonical cut sites",
            "collect requested sequence evidence", "optionally predict on-target efficiency",
            "optionally search and score off-targets", "rank candidates", "return provenance",
        ],
        output_schema={
            "status": "complete|partial|failed",
            "candidates": "list[structured candidate]",
            "warnings": "list[string]",
            "errors": "list[string]",
        },
        validation_rules=[
            "Exactly one of sequence, input_id, or complete genomic region is required.",
            "calibration_input is OPTIONAL. Gene-cutting works normally with only analysis input.",
            "Sequence input must be non-empty DNA/IUPAC text; candidate feature tools require concrete A/C/G/T guides.",
            "Genomic regions use 1-based half-open [start, end) coordinates.",
            "depth must be quick or full; full requires genome_id for off-target search.",
            "No experimental cleavage certainty is inferred from computational results.",
        ],
    )

    def validate(self, request: dict[str, Any], control_plane: Any) -> None:
        sequence = request.get("sequence")
        input_id = request.get("input_id") or request.get("analysis_input_id") or request.get("analysis_input")
        region_fields = [request.get(key) for key in ("chrom", "start", "end")]
        has_region = any(value is not None for value in region_fields)
        modes = int(sequence is not None) + int(input_id is not None) + int(has_region)
        if modes != 1:
            raise SkillError("invalid_skill_input", "Provide exactly one of sequence, input_id, or genome_id/chrom/start/end.")
        if input_id:
            control_plane.inputs.get_analysis_input(input_id)
        if sequence is not None:
            if not isinstance(sequence, str) or not sequence.strip():
                raise SkillError("empty_sequence", "Sequence input must be non-empty.", "sequence")
            if any(ch.upper() not in "ACGTRYSWKMBDHVN" for ch in sequence if not ch.isspace()):
                raise SkillError("invalid_sequence", "Sequence contains characters outside the IUPAC DNA alphabet.", "sequence")
        if has_region:
            if not request.get("genome_id") or not all(value is not None for value in region_fields):
                raise SkillError("invalid_region", "genome_id, chrom, start, and end are all required for region mode.")
            if not isinstance(request["start"], int) or request["start"] < 1:
                raise SkillError("invalid_region", "start must be an integer >= 1.", "start")
            if not isinstance(request["end"], int) or request["end"] <= request["start"]:
                raise SkillError("invalid_region", "end must be greater than start.", "end")
        calib_id = (
            request.get("calibration_input_id")
            or request.get("calibration_input")
            or request.get("calibration_id")
        )
        if calib_id:
            control_plane.inputs.get_calibration_input(calib_id)
        depth = request.get("depth", "quick")
        if depth not in {"quick", "full"}:
            raise SkillError("invalid_depth", "depth must be 'quick' or 'full'.", "depth")
        strand = request.get("strand", "both")
        if strand not in {"both", "fwd", "rev"}:
            raise SkillError("invalid_strand", "strand must be 'both', 'fwd', or 'rev'.", "strand")
        max_candidates = request.get("max_candidates", 100)
        if not isinstance(max_candidates, int) or not 1 <= max_candidates <= 1000:
            raise SkillError("invalid_max_candidates", "max_candidates must be between 1 and 1000.", "max_candidates")
        if depth == "full" and not request.get("genome_id"):
            request["depth"] = "quick"
            warnings_list = request.setdefault("_pre_warnings", [])
            warnings_list.append("Full analysis requested without genome_id; performed quick in-sequence analysis.")

    @staticmethod
    def _records(control_plane: Any, request: dict[str, Any]) -> list[tuple[str | None, str]]:
        if request.get("sequence"):
            seq_str = "".join(request["sequence"].split()).upper()
            if len(seq_str) > 25000:
                seq_str = seq_str[:25000]
                warnings_list = request.setdefault("_pre_warnings", [])
                warnings_list.append("Input sequence exceeds 25,000 bp; analyzed the first 25,000 bp for candidate selection.")
            return [(request.get("chrom"), seq_str)]
        input_id = request.get("input_id") or request.get("analysis_input_id") or request.get("analysis_input")
        item = control_plane.inputs.get_analysis_input(input_id)
        fmt = {"fasta": "fasta", "fastq": "fastq", "genbank": "genbank"}[item.detected_format]
        records = list(SeqIO.parse(StringIO(item._content.decode("utf-8")), fmt))
        records_out = []
        for record in records:
            seq_str = str(record.seq).upper()
            if len(seq_str) > 25000:
                seq_str = seq_str[:25000]
                warnings_list = request.setdefault("_pre_warnings", [])
                warnings_list.append(f"Record '{record.id}' exceeds 25,000 bp; analyzed the first 25,000 bp.")
            records_out.append((record.id, seq_str))
        return records_out

    @staticmethod
    def _spacer_start(row: dict[str, Any], length: int = 20) -> int | None:
        if row.get("start") is None or row.get("end") is None or not row.get("protospacer"):
            return None
        # PAM coordinates are 1-based half-open. Protospacer start is the
        # 0-based reference start required by compute_cut_site.
        return row["start"] - 1 - length if row.get("strand") == "+" else row["end"] - 1

    @staticmethod
    def _context(sequence: str, row: dict[str, Any], length: int = 20) -> str | None:
        if not row.get("protospacer") or row.get("start") is None or row.get("end") is None:
            return None
        pam_start, pam_end = row["start"] - 1, row["end"] - 1
        if row.get("strand") == "+":
            start, end = pam_start - length - 4, pam_end + 3
            return sequence[start:end] if start >= 0 and end <= len(sequence) else None
        start, end = pam_start - 3, pam_end + length + 4
        if start < 0 or end > len(sequence):
            return None
        ref = sequence[start:end]
        return _reverse_complement(ref)

    async def _features(self, guide: str, *, call_tool: Any, include_structure: bool) -> tuple[dict[str, Any], list[str]]:
        features: dict[str, Any] = {}
        warnings: list[str] = []
        calls = [
            ("gc", "compute_gc_content", {"sequence": guide}),
            ("homopolymer", "check_homopolymer_runs", {"sequence": guide}),
            ("tm", "compute_melting_temp", {"sequence": guide}),
            ("positional", "compute_positional_features", {"sequence": guide}),
            ("dinucleotide", "compute_dinucleotide_composition", {"sequence": guide}),
            ("seed_gc", "compute_seed_gc", {"sequence": guide}),
        ]
        if include_structure:
            calls.append(("secondary_structure", "compute_secondary_structure", {"sequence": guide, "return_structure_string": True}))
        for label, tool, arguments in calls:
            result = await call_tool(tool, arguments)
            features[label] = {"summary": result.summary, "rows": result.rows}
            if result.errors:
                warnings.extend(f"{tool}: {error}" for error in result.errors)
        return features, warnings

    async def execute(self, request: dict[str, Any], *, control_plane: Any,
                      call_tool: Any, emit: Any) -> dict[str, Any]:
        self.validate(request, control_plane)
        depth = request.get("depth", "quick")
        warnings: list[str] = list(request.get("_pre_warnings", []))
        errors: list[str] = []
        candidates: list[dict[str, Any]] = []
        is_region = any(request.get(key) is not None for key in ("chrom", "start", "end"))

        # Validate the registered genome before a regional PAM scan or a
        # full sequence-mode off-target workflow. This avoids sending an
        # invalid genome identifier to the expensive downstream operation.
        if request.get("genome_id"):
            genome = await call_tool("genome_info", {"genome_id": request["genome_id"]})
            if genome.errors:
                return {"skill": self.metadata.skill_id, "status": "failed", "candidates": [],
                        "warnings": [], "errors": genome.errors}

        records = self._records(control_plane, request) if not is_region else [(request.get("chrom"), "")]

        if is_region:
            pam_result = await call_tool("pam_scan_region", {
                "genome_id": request["genome_id"], "chrom": request["chrom"],
                "start": request["start"], "end": request["end"], "pam_pattern": "NGG",
                "protospacer_len": 20, "strand": request.get("strand", "both"),
            })
            pam_results = [(pam_result, None)]
        else:
            pam_results = []
            for chrom, sequence in records:
                result = await call_tool("pam_scan", {"sequence": sequence, "pam_pattern": "NGG",
                                                       "protospacer_len": 20, "strand": request.get("strand", "both"),
                                                       "chrom": chrom})
                pam_results.append((result, sequence))

        max_limit = min(request.get("max_candidates", 5), 5 if depth == "quick" else 50)
        for pam_result, sequence in pam_results:
            if pam_result.errors:
                errors.extend(pam_result.errors)
                continue
            for row in pam_result.rows:
                row = row if isinstance(row, dict) else row
                row_dict = row if isinstance(row, dict) else row.model_dump()
                if not row_dict.get("protospacer"):
                    continue
                if len(candidates) >= max_limit:
                    warnings.append("max_candidates reached; remaining PAM hits were not evaluated.")
                    break
                candidate_id = f"candidate_{len(candidates) + 1}"
                await emit("candidate_discovered", candidate_id=candidate_id, pam=row_dict.get("pam"), strand=row_dict.get("strand"))
                guide = row_dict["protospacer"].upper()
                candidate_warnings: list[str] = []
                candidate: dict[str, Any] = {
                    "candidate_id": candidate_id, "chrom": row_dict.get("chrom"),
                    "strand": row_dict.get("strand"), "pam": row_dict.get("pam"),
                    "pam_start": row_dict.get("start"), "pam_end": row_dict.get("end"),
                    "protospacer": guide, "cut_site": {"relative": None, "genomic": None},
                    "features": {}, "ontarget": {"score": None, "model": None},
                    "specificity": {"offtarget_count": None, "worst_cfd": None},
                    "rank": None, "cutting_site_string": None, "provenance": ["pam_scan"],
                }
                spacer_start = self._spacer_start(row_dict)
                if spacer_start is None:
                    continue
                cut = await call_tool("compute_cut_site", {
                    "spacer_start": spacer_start, "spacer_length": 20,
                    "strand": row_dict.get("strand"), "pam_position": "3prime",
                    "return_genomic_coord": bool(row_dict.get("chrom")),
                    "return_relative_coord": True, "chrom": row_dict.get("chrom") or "",
                })
                candidate["cut_site"] = {"relative": cut.summary.get("cut_site_relative"),
                                         "genomic": cut.summary.get("cut_site_genomic")}
                candidate["provenance"].append("compute_cut_site")
                if cut.errors:
                    candidate_warnings.extend(cut.errors)
                if set(guide) <= set("ACGT"):
                    features, feature_warnings = await self._features(guide, call_tool=call_tool,
                                                                        include_structure=depth == "full")
                    candidate["features"] = features
                    candidate_warnings.extend(feature_warnings)
                else:
                    candidate_warnings.append("Feature tools skipped because protospacer contains ambiguous bases.")
                context = self._context(sequence, row_dict) if sequence else None
                if context and set(context) <= set("ACGT"):
                    on_target = await call_tool("predict_ontarget_efficiency", {
                        "context_sequence": context, "model": request.get("model", "auto"),
                        "spacer_length": 20,
                    })
                    candidate["ontarget"] = {"score": on_target.summary.get("ontarget_score"),
                                             "model": on_target.summary.get("model_used")}
                    candidate["provenance"].append("predict_ontarget_efficiency")
                    candidate_warnings.extend(on_target.errors)
                elif depth == "full":
                    candidate_warnings.append("On-target context was unavailable; no on-target score was fabricated.")

                if depth == "full" and request.get("genome_id"):
                    off_targets = await call_tool("offtarget_search", {
                        "spacer_sequence": guide, "genome_id": request["genome_id"], "pam_pattern": "NGG",
                        "max_mismatches": request.get("max_mismatches", 4), "backend": request.get("offtarget_backend", "bwa"),
                        "search_scope": "genome", "strand_search": "both", "max_results": request.get("max_results", 1000),
                    })
                    candidate["specificity"]["offtarget_count"] = len(off_targets.rows)
                    candidate_warnings.extend(off_targets.errors)
                    if off_targets.rows:
                        scored = await call_tool("score_offtargets", {"spacer_sequence": guide,
                                                                         "candidates": off_targets.rows, "pam_pattern": "NGG"})
                        cfd = [row.get("cfd_score") for row in scored.rows if row.get("cfd_score") is not None]
                        candidate["specificity"]["worst_cfd"] = max(cfd) if cfd else None
                        candidate_warnings.extend(scored.errors)
                        candidate["provenance"].extend(["offtarget_search", "score_offtargets"])
                elif depth == "full":
                    candidate_warnings.append("Full specificity evidence was not run because genome_id is unavailable.")
                candidate["warnings"] = candidate_warnings
                candidate["cutting_site_string"] = _cutting_site_string(candidate)
                candidates.append(candidate)
                await emit("candidate_evaluated", candidate_id=candidate_id, warning_count=len(candidate_warnings))

        if candidates:
            guides = [{"chrom": c["chrom"], "start": c["pam_start"], "end": c["pam_end"],
                       "strand": c["strand"], "protospacer": c["protospacer"], "pam": c["pam"],
                       "pam_type": "SpCas9"} for c in candidates]
            on_target_scores = {c["protospacer"]: c["ontarget"]["score"] for c in candidates if c["ontarget"]["score"] is not None}
            ranked = await call_tool("rank_candidates", {"guides": guides, "on_target_scores": on_target_scores,
                                                           "sort_by": "composite"})
            if ranked.errors:
                warnings.extend(ranked.errors)
            else:
                rank_by_guide = {row.get("protospacer"): index for index, row in enumerate(ranked.rows, 1)}
                for candidate in candidates:
                    candidate["rank"] = rank_by_guide.get(candidate["protospacer"])
                await emit("ranking_completed", candidate_count=len(candidates))

        status = "failed" if errors and not candidates else ("partial" if errors or warnings else "complete")
        return {"skill": self.metadata.skill_id, "status": status, "candidates": candidates,
                "warnings": warnings, "errors": errors}


def _reverse_complement(sequence: str) -> str:
    table = str.maketrans("ACGTN", "TGCAN")
    return sequence.translate(table)[::-1]


def _cutting_site_string(candidate: dict[str, Any]) -> str:
    chrom = candidate.get("chrom") or "sequence"
    cut = candidate.get("cut_site", {}).get("genomic")
    cut_text = str(cut) if cut is not None else "relative=" + str(candidate.get("cut_site", {}).get("relative"))
    return f"{chrom} | cut={cut_text} | {candidate.get('strand')} | PAM={candidate.get('pam')} | guide={candidate.get('protospacer')}"
