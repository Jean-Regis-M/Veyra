# Reference Genomes

VEYRA maintains a registry of reference genomes for indexed operations (PAM region scanning, off-target search).

## Genome Registry

The registry lives in `references/__init__.py` and is populated at import time via `_register_defaults()`.

**Python API:**

```python
from references import get_genome, list_genomes, register_genome, GenomeConfig

# List all registered genomes
genomes = list_genomes()

# Get a specific genome
genome = get_genome("GRCh38.p14")

# Register a custom genome
from references import GenomeConfig, register_genome
config = GenomeConfig(
    genome_id="my_genome",
    display_name="My custom genome",
    fasta_path="/path/to/genome.fa",
)
register_genome(config)
```

## Registered Genomes

| Genome ID | Description | FASTA Path |
|-----------|-------------|------------|
| `ecoli_k12_mg1655` | E. coli K-12 MG1655 (NCBI GCF_000005845.2, 4.6 Mbp) | `veyra/data/references/ecoli_k12/genome/GCF_000005845.2.fasta` |
| `GRCh38.p14` | Human GRCh38.p14 assembly (NCBI GCF_000001405.40) | `refrences/refs/ncbi_dataset/data/GCF_000001405.40/GCF_000001405.40_GRCh38.p14_genomic.fna` |

Additional test genomes are registered if their FASTA files exist:
- `GRCh38_chr1_test` — chr1:1000000-1001000 test region
- `CIRCLEseq_test` — CIRCLE-seq test genome (contig name: `2`)
- `guideseq_test` — Guide-seq test genome (contig name: `chr19`)

These test genomes are registered conditionally and may not be present on all systems.

## GenomeConfig

```python
@dataclass
class GenomeConfig:
    genome_id: str
    display_name: str
    fasta_path: str          # absolute path to FASTA
    fai_path: str | None     # .fai index path (auto-detected)
    bwa_index_prefix: str | None  # BWA index prefix
    bowtie2_index_prefix: str | None
    blast_db_name: str | None
    metadata: dict
```

**Properties:**
- `has_fai` — True if `.fai` index file exists
- `has_bwa_index` — True if `.bwt` file exists at the index prefix
- `fasta_checksum()` — SHA256-based checksum for cache invalidation

## Index Requirements

### samtools .fai index

Required for: `pam_scan_region`, `offtarget_search` (PAM extraction).

Build:

```bash
samtools faidx /path/to/genome.fa
```

Creates `genome.fa.fai` alongside the FASTA.

### BWA index

Required for: `offtarget_search`, `build_offtarget_index`.

Build:

```bash
bwa index /path/to/genome.fa
```

Creates `genome.fa.bwt`, `genome.fa.pac`, `genome.fa.ann`, etc.

VEYRA's `build_offtarget_index` tool handles BWA index creation automatically and caches the result.

## Adding a New Genome

### Option 1: Register at runtime

```python
from references import GenomeConfig, register_genome

config = GenomeConfig(
    genome_id="my_genome",
    display_name="My genome",
    fasta_path="/absolute/path/to/genome.fa",
)
register_genome(config)
```

### Option 2: Add to `_register_defaults()`

Edit `references/__init__.py` and add a conditional registration block in `_register_defaults()`. The genome is only registered if the FASTA file exists on disk.

## Cache/Index Lifecycle

1. `build_offtarget_index` creates BWA indexes and caches metadata in SQLite (`cache/veyra_cache.db`)
2. Cache key includes genome ID, cas variant, and FASTA checksum
3. If the FASTA file changes, the checksum changes and the cache is invalidated
4. `force_rebuild=True` bypasses the cache
5. Cache TTL is 30 days for indexes

## File Layout

```
refrences/
├── refs/
│   └── ncbi_dataset/
│       └── data/
│           └── GCF_000001405.40/
│               └── GCF_000001405.40_GRCh38.p14_genomic.fna
│               └── GCF_000001405.40_GRCh38.p14_genomic.fna.fai  (if indexed)
├── data/
│   └── tools/
│       ├── changeseq/test/data/input/CIRCLEseq_test_genome.fa
│       └── guideseq/test/test_genome.fa
```

## E. coli K-12 MG1655 (Integration Test Genome)

**Genome ID:** `ecoli_k12_mg1655`

| Property | Value |
|----------|-------|
| Organism | Escherichia coli str. K-12 substr. MG1655 |
| Assembly | ASM584v2 |
| Accession | GCF_000005845.2 |
| Chromosome | NC_000913.3 |
| Length | 4,641,652 bp |
| FASTA | `veyra/data/references/ecoli_k12/genome/GCF_000005845.2.fasta` |
| FASTA index | `genome/GCF_000005845.2.fasta.fai` |
| BWA index | `genome/GCF_000005845.2.fasta.*` (`.amb`, `.ann`, `.bwt`, `.pac`, `.sa`) |
| MD5 | `92c997bcd88e983ffdb21b2712ed3736` |
| Source | NCBI RefSeq FTP |

This is the recommended genome for integration testing. It is small enough for fast CI runs while being a real, fully assembled bacterial chromosome.

**Verify registration:**

```bash
python -m cli.main genome list
python -m cli.main genome info --genome-id ecoli_k12_mg1655
```

## Notes

- Genomes are **not** duplicated by VEYRA. The registry stores paths to existing FASTA files.
- The `GRCh38.p14` genome is ~3.2 Gbp. BWA index creation takes several minutes.
- The `ecoli_k12_mg1655` genome is ~4.6 Mbp. BWA index creation takes ~2 seconds.
- Always build `.fai` before BWA index (`samtools faidx` is fast).
- BWA index files (`.bwt`, `.pac`, etc.) are created alongside the FASTA file, not in a separate directory.
