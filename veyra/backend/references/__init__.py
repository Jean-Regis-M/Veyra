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
_HCK15 = Path("/home/hrirake/Desktop/hck15")
_VEYRA_BACKEND = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REFERENCES_DIR = _VEYRA_BACKEND / "references"
_CACHE_DIR = _VEYRA_BACKEND / "cache"
_DATA_DIR = _VEYRA_BACKEND / "data"

# CRISPOR CFD scoring resources
# Primary: VEYRA-local copy under data/resources/crispor_cfd/
# Fallback: refrences.local (read-only reference infrastructure)
_VEYRA_ROOT = _VEYRA_BACKEND.parent  # veyra/ root
_CFD_LOCAL = _VEYRA_ROOT / "data" / "resources" / "crispor_cfd"
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


def _register_defaults() -> None:
    """Register known reference genomes from the hck15 environment."""

    # GRCh38.p14 — full assembly
    grch38_fna = _HCK15 / "refrences" / "refs" / "ncbi_dataset" / "data" / "GCF_000001405.40" / "GCF_000001405.40_GRCh38.p14_genomic.fna"
    if grch38_fna.is_file():
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
    chr1_test = _HCK15 / "refrences" / "refs" / "grch38_chr1_test.fasta"
    if chr1_test.is_file():
        fai = str(chr1_test) + ".fai"
        _GENOMES["GRCh38_chr1_test"] = GenomeConfig(
            genome_id="GRCh38_chr1_test",
            display_name="Human GRCh38 chr1:1000000-1001000 (test)",
            fasta_path=str(chr1_test),
            fai_path=fai if os.path.isfile(fai) else None,
            metadata={"organism": "Homo sapiens", "region": "chr1:1000000-1001000"},
        )

    # CIRCLE-seq test genome
    circle_fna = _HCK15 / "refrences" / "data" / "tools" / "changeseq" / "test" / "data" / "input" / "CIRCLEseq_test_genome.fa"
    if circle_fna.is_file():
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
    guideseq_fa = _HCK15 / "refrences" / "data" / "tools" / "guideseq" / "test" / "test_genome.fa"
    if guideseq_fa.is_file():
        fai = str(guideseq_fa) + ".fai"
        _GENOMES["guideseq_test"] = GenomeConfig(
            genome_id="guideseq_test",
            display_name="Guide-seq test genome",
            fasta_path=str(guideseq_fa),
            fai_path=fai if os.path.isfile(fai) else None,
            metadata={"organism": "test"},
        )

    # E. coli K-12 MG1655 (integration test genome)
    ecoli_fa = _HCK15 / "veyra" / "data" / "references" / "ecoli_k12" / "genome" / "GCF_000005845.2.fasta"
    if ecoli_fa.is_file():
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
