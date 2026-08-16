# VEYRA Test Data

Original test data for VEYRA backend validation and development.

## Directory Structure

```
data/
├── genomes/                  # Reference genome FASTAs
│   └── test_genome.fa       # Small test genome (chr1, chr2, chr3)
├── guides/                   # CRISPR guide spacer files
│   └── test_guides.fasta    # Test guide sequences
├── sequences/                # Input sequence files
│   ├── test_sequences.fastq # FASTQ with quality scores
│   └── test_genbank.gb      # GenBank with features
└── references/               # Reference resources
    └── CFD_Scoring -> ...   # Symlink to CRISPOR CFD scoring pickles
```

## Test Genome

`genomes/test_genome.fa` — Small 3-contig genome for MCP tool testing.

| Contig | Length | Description |
|--------|--------|-------------|
| chr1 | 264 bp | Contains SpCas9 NGG PAM sites |
| chr2 | 120 bp | Contains poly-T/poly-G runs |
| chr3 | 200 bp | Homopolymer and dinucleotide repeats |

Known PAM sites in chr1:
- Position 21-23: `AGG` (SpCas9 PAM) on + strand
- Position 111-113: `GGG` (SpCas9 PAM) on + strand

## Guide Sequences

`guides/test_guides.fasta` — Test CRISPR guide spacers.

| Guide | Target | PAM | Notes |
|-------|--------|-----|-------|
| guide1 | chr1:1-20 | AGG | Valid SpCas9 target |
| guide2 | chr1 reverse | GGG | Reverse strand target |
| guide3 | chr2:1-20 | AGG | Valid SpCas9 target |
| guide4 | none | AAAT | No PAM match (negative control) |
| guide5 | chr1 | TTTV | Cas12a target (5' PAM) |

## FASTQ Data

`sequences/test_sequences.fastq` — 3 read pairs with Phred quality scores.

- SEQ_ID_001: Real genomic-like sequence
- SEQ_ID_002: Perfect quality (all B/I scores)
- SEQ_ID_003: Moderate quality (C/D/E scores)

## GenBank Data

`sequences/test_genbank.gb` — GenBank record with:

- Source feature (1..200)
- guideRNA feature (1..20)
- PAM feature (21..23)
- Gene feature (50..150)
- CDS feature (50..150)

## Reference Resources

`references/CFD_Scoring` — Symlink to CRISPOR CFD scoring resources:

- `mismatch_score.pkl` — Mismatch penalty scores
- `pam_scores.pkl` — PAM efficiency scores

Source: `data/resources/crispor_cfd/` (or external `refrences.local/data/benchmarks/crisporPaper/CFD_Scoring/`)

## Usage

### Ingestion testing

```bash
python veyra.py --input data/genomes/test_genome.fa
python veyra.py --input data/sequences/test_sequences.fastq --json
python veyra.py --input data/sequences/test_genbank.gb --pam
```

### MCP tool testing

```bash
python -m mcp.server pam-scan --sequence ATCGATCGATCGATCGATCGAGG
python -m mcp.server build-index --genome test_genome --force
python -m mcp.server offtarget-search --spacer ATCGATCGATCGATCGATCGAGG --genome test_genome
```

### Python API

```python
from parsers.fasta_parser import parse_fasta
from parsers.fastq_parser import parse_fastq
from parsers.genbank_parser import parse_genbank

# Parse FASTA
records = list(parse_fasta("data/genomes/test_genome.fa"))

# Parse FASTQ
records = list(parse_fastq("data/sequences/test_sequences.fastq"))

# Parse GenBank
records = list(parse_genbank("data/sequences/test_genbank.gb"))
```

## Adding New Test Data

1. Place files in the appropriate subdirectory
2. Use descriptive filenames with `test_` prefix
3. Keep files small (< 10 KB) for fast test runs
4. Document known properties (PAM sites, features, etc.)
5. Update this README
