"""Reference genome configuration for VEYRA.

Manages reference genome paths, index locations, and metadata.
Uses symlinks/configuration rather than duplicating genome files.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Base paths
_VEYRA_BACKEND = Path(__file__).resolve().parent.parent
_REFERENCES_DIR = _VEYRA_BACKEND / "references"
_CACHE_DIR = Path(os.environ.get("VEYRA_CACHE_DIR", str(_VEYRA_BACKEND / "cache")))
_VEYRA_ROOT = Path(os.environ.get("VEYRA_ROOT", str(_VEYRA_BACKEND.parent)))
_DATA_DIR = Path(os.environ.get("VEYRA_DATA_DIR", str(_VEYRA_ROOT / "data")))

# CRISPOR CFD scoring resources
# Primary: VEYRA-local copy under data/resources/crispor_cfd/
# Fallback: refrences.local (read-only reference infrastructure)
_CFD_LOCAL = _DATA_DIR / "resources" / "crispor_cfd"
_CFD_REFLOCAL = _VEYRA_ROOT / "refrences.local" / "data" / "benchmarks" / "crisporPaper" / "CFD_Scoring"

CRISPOR_CFD_DIR = _CFD_LOCAL if (_CFD_LOCAL / "mismatch_score.pkl").is_file() else _CFD_REFLOCAL
CFD_MISMATCH_SCORES = CRISPOR_CFD_DIR / "mismatch_score.pkl"
CFD_PAM_SCORES = CRISPOR_CFD_DIR / "pam_scores.pkl"


@dataclass
class GenomeConfig:
    """Configuration for a reference genome."""

    genome_id: str
    display_name: str
    fasta_path: str  # absolute path to the .fna/.fa file
    fai_path: str | None = None  # samtools faidx index
    bwa_index_prefix: str | None = None  # BWA index prefix (without .bwt etc.)
    bowtie2_index_prefix: str | None = None
    blast_db_name: str | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def has_fai(self) -> bool:
        return self.fai_path is not None and os.path.isfile(self.fai_path)

    @property
    def has_bwa_index(self) -> bool:
        if self.bwa_index_prefix is None:
            return False
        return os.path.isfile(self.bwa_index_prefix + ".bwt")

    @property
    def has_bowtie2_index(self) -> bool:
        if self.bowtie2_index_prefix is None:
            return False
        return os.path.isfile(self.bowtie2_index_prefix + ".1.bt2")

    def fasta_checksum(self) -> str:
        """Compute a fast checksum of the FASTA file for cache invalidation."""
        if not os.path.isfile(self.fasta_path):
            return ""
        h = hashlib.sha256()
        with open(self.fasta_path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Registered genomes
# ---------------------------------------------------------------------------

_GENOMES: dict[str, GenomeConfig] = {}


def _find_candidate_file(rel_paths: list[Path | str]) -> Path | None:
    """Find first existing file from candidate relative or absolute paths."""
    for p in rel_paths:
        path_obj = Path(p) if not isinstance(p, Path) else p
        if path_obj.is_file():
            return path_obj
    return None


def _get_reference_search_roots() -> list[Path]:
    """Get candidate base directories for external reference genome files."""
    roots: list[Path] = []
    for env_var in ["GENOME_REFERENCES_DIR", "VEYRA_REFERENCES_DIR", "HCK15_REFS_DIR"]:
        val = os.environ.get(env_var)
        if val:
            roots.append(Path(val))
    roots.extend([
        _DATA_DIR,
        _DATA_DIR / "references",
        _VEYRA_ROOT / "data" / "references",
        _VEYRA_ROOT / "refrences.local",
        _VEYRA_ROOT / "refrences",
        _VEYRA_ROOT / "references",
        _VEYRA_ROOT.parent / "refrences",
        _VEYRA_ROOT.parent / "references",
        _VEYRA_ROOT.parent / "data" / "references",
        _VEYRA_ROOT.parent / "veyra" / "data" / "references",
    ])
    # Deduplicate while preserving order
    seen: set[Path] = set()
    deduped: list[Path] = []
    for r in roots:
        resolved = r.resolve() if r.exists() else r
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(r)
    return deduped


def _register_defaults() -> None:
    """Register known reference genomes from deployment environment."""
    ref_roots = _get_reference_search_roots()

    # GRCh38.p14 — full assembly
    grch38_env = os.environ.get("GRCH38_FASTA_PATH")
    grch38_candidates: list[Path | str] = []
    if grch38_env:
        grch38_candidates.append(grch38_env)
    for root in ref_roots:
        grch38_candidates.extend([
            root / "refs" / "ncbi_dataset" / "data" / "GCF_000001405.40" / "GCF_000001405.40_GRCh38.p14_genomic.fna",
            root / "ncbi_dataset" / "data" / "GCF_000001405.40" / "GCF_000001405.40_GRCh38.p14_genomic.fna",
            root / "GRCh38.p14" / "GCF_000001405.40_GRCh38.p14_genomic.fna",
        ])
    grch38_fna = _find_candidate_file(grch38_candidates)
    if grch38_fna:
        fai = str(grch38_fna) + ".fai"
        _GENOMES["GRCh38.p14"] = GenomeConfig(
            genome_id="GRCh38.p14",
            display_name="Human GRCh38.p14 (NCBI GCF_000001405.40)",
            fasta_path=str(grch38_fna),
            fai_path=fai if os.path.isfile(fai) else None,
            bwa_index_prefix=str(grch38_fna),
            metadata={"organism": "Homo sapiens", "assembly": "GRCh38.p14"},
        )

    # GRCh38 chr1 test region
    chr1_env = os.environ.get("GRCH38_CHR1_TEST_PATH")
    chr1_candidates: list[Path | str] = []
    if chr1_env:
        chr1_candidates.append(chr1_env)
    for root in ref_roots:
        chr1_candidates.extend([
            root / "refs" / "grch38_chr1_test.fasta",
            root / "grch38_chr1_test.fasta",
        ])
    chr1_test = _find_candidate_file(chr1_candidates)
    if chr1_test:
        fai = str(chr1_test) + ".fai"
        _GENOMES["GRCh38_chr1_test"] = GenomeConfig(
            genome_id="GRCh38_chr1_test",
            display_name="Human GRCh38 chr1:1000000-1001000 (test)",
            fasta_path=str(chr1_test),
            fai_path=fai if os.path.isfile(fai) else None,
            metadata={"organism": "Homo sapiens", "region": "chr1:1000000-1001000"},
        )

    # CIRCLE-seq test genome
    circle_env = os.environ.get("CIRCLESEQ_TEST_PATH")
    circle_candidates: list[Path | str] = []
    if circle_env:
        circle_candidates.append(circle_env)
    for root in ref_roots:
        circle_candidates.extend([
            root / "data" / "tools" / "changeseq" / "test" / "data" / "input" / "CIRCLEseq_test_genome.fa",
            root / "tools" / "changeseq" / "test" / "data" / "input" / "CIRCLEseq_test_genome.fa",
            root / "CIRCLEseq_test_genome.fa",
        ])
    circle_fna = _find_candidate_file(circle_candidates)
    if circle_fna:
        fai = str(circle_fna) + ".fai"
        _GENOMES["CIRCLEseq_test"] = GenomeConfig(
            genome_id="CIRCLEseq_test",
            display_name="CIRCLE-seq test genome",
            fasta_path=str(circle_fna),
            fai_path=fai if os.path.isfile(fai) else None,
            bwa_index_prefix=str(circle_fna),
            metadata={"organism": "test"},
        )

    # Guide-seq test genome / chr19
    guideseq_env = os.environ.get("GUIDESEQ_TEST_PATH")
    guideseq_candidates: list[Path | str] = []
    if guideseq_env:
        guideseq_candidates.append(guideseq_env)
    for root in ref_roots:
        guideseq_candidates.extend([
            root / "data" / "tools" / "guideseq" / "test" / "test_genome.fa",
            root / "tools" / "guideseq" / "test" / "test_genome.fa",
            root / "test_genome.fa",
        ])
    guideseq_fa = _find_candidate_file(guideseq_candidates)
    if guideseq_fa:
        fai = str(guideseq_fa) + ".fai"
        _GENOMES["guideseq_test"] = GenomeConfig(
            genome_id="guideseq_test",
            display_name="Guide-seq test genome",
            fasta_path=str(guideseq_fa),
            fai_path=fai if os.path.isfile(fai) else None,
            metadata={"organism": "test"},
        )

    # E. coli K-12 MG1655 (integration test genome)
    ecoli_env = os.environ.get("ECOLI_FASTA_PATH")
    ecoli_candidates: list[Path | str] = []
    if ecoli_env:
        ecoli_candidates.append(ecoli_env)
    for root in ref_roots:
        ecoli_candidates.extend([
            root / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
            root / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
            root / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
        ])
    ecoli_candidates.extend([
        _DATA_DIR / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
        _VEYRA_ROOT / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
        _VEYRA_ROOT.parent / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
        _VEYRA_ROOT.parent / "veyra" / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta",
    ])
    ecoli_fa = _find_candidate_file(ecoli_candidates)
    if ecoli_fa:
        fai = str(ecoli_fa) + ".fai"
        _GENOMES["ecoli_k12_mg1655"] = GenomeConfig(
            genome_id="ecoli_k12_mg1655",
            display_name="E. coli K-12 MG1655 (NCBI GCF_000005845.2)",
            fasta_path=str(ecoli_fa),
            fai_path=fai if os.path.isfile(fai) else None,
            bwa_index_prefix=str(ecoli_fa),
            metadata={
                "organism": "Escherichia coli str. K-12 substr. MG1655",
                "assembly": "ASM584v2",
                "accession": "GCF_000005845.2",
                "chromosome": "NC_000913.3",
                "length": 4641652,
                "source": "NCBI RefSeq",
            },
        )


_register_defaults()


def get_genome(genome_id: str) -> GenomeConfig:
    """Retrieve a registered genome configuration.

    Raises ValueError if genome_id is not found.
    """
    if genome_id not in _GENOMES:
        available = ", ".join(sorted(_GENOMES.keys())) or "(none)"
        raise ValueError(
            f"Unknown genome: {genome_id}. Available: {available}"
        )
    return _GENOMES[genome_id]


def list_genomes() -> list[GenomeConfig]:
    """Return all registered genome configurations."""
    return list(_GENOMES.values())


def register_genome(config: GenomeConfig) -> None:
    """Register a custom genome configuration."""
    _GENOMES[config.genome_id] = config


def get_cfd_resources() -> tuple[str, str]:
    """Return paths to CFD scoring pickle files.

    Returns (mismatch_score_path, pam_scores_path).
    Raises FileNotFoundError if resources are missing.
    """
    if not CFD_MISMATCH_SCORES.is_file():
        raise FileNotFoundError(
            f"CFD mismatch scores not found: {CFD_MISMATCH_SCORES}"
        )
    if not CFD_PAM_SCORES.is_file():
        raise FileNotFoundError(
            f"CFD PAM scores not found: {CFD_PAM_SCORES}"
        )
    return str(CFD_MISMATCH_SCORES), str(CFD_PAM_SCORES)
