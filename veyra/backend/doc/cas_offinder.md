# Cas-OFFinder Integration

VEYRA integrates Cas-OFFinder 3.0.0 for real CRISPR off-target detection with DNA/RNA bulge support. This document describes the integration, installation, and usage.

## Overview

Cas-OFFinder is a GPU-accelerated tool for searching CRISPR off-target sites with DNA/RNA bulges. VEYRA uses it as the primary backend for comprehensive off-target detection.

## Installation

### Prerequisites

- OpenCL runtime (POCL for CPU-only)
- OpenCL development headers
- CMake 3.10+
- C++ compiler (g++)
- Git

### Build Process

```bash
# Install system packages (requires sudo)
sudo apt-get update
sudo apt-get install -y ocl-icd-opencl-dev opencl-headers pocl-opencl-icd cmake g++

# Clone Cas-OFFinder
cd data/tools
git clone https://github.com/pinellolab/Cas-OFFinder.git cas-offinder
cd cas-offinder

# Build
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

### Installation Location

VEYRA installs Cas-OFFinder at:

```
data/tools/cas-offinder/
├── build/
│   └── cas-offinder          # Compiled executable
├── src/                      # Source code
├── PROVENANCE.md             # Version and build information
└── test/                     # Test data
```

## Usage

### MCP Tool: cas_offinder_search

```python
from mcp.tools.cas_offinder_search import cas_offinder_search

result = cas_offinder_search(
    spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
    genome_id="ecoli_k12_mg1655",
    pam_pattern="NGG",
    max_mismatches=3,
    max_dna_bulge=1,
    max_rna_bulge=0,
)
```

### Python API

```python
from api import search_offtargets

result = search_offtargets(
    spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
    genome_id="ecoli_k12_mg1655",
    pam_pattern="NGG",
    max_mismatches=3,
    allow_bulge=True,
    max_dna_bulge=1,
    max_rna_bulge=0,
)
```

### CLI

```bash
python -m cli.main offtarget search \
  --spacer GCGCGCGCGCGCGCGCGCGC \
  --genome ecoli_k12_mg1655 \
  --pam NGG \
  --mismatches 3 \
  --allow-bulge \
  --max-dna-bulge 1 \
  --max-rna-bulge 0
```

### HTTP API

```bash
curl -X POST http://localhost:8000/offtarget/search \
  -H "Content-Type: application/json" \
  -d '{
    "spacer_sequence": "GCGCGCGCGCGCGCGCGCGC",
    "genome_id": "ecoli_k12_mg1655",
    "pam_pattern": "NGG",
    "max_mismatches": 3,
    "allow_bulge": true,
    "max_dna_bulge": 1,
    "max_rna_bulge": 0
  }'
```

## Input Format

Cas-OFFinder requires a specific input format:

```
<genome_fasta_dir>
<pattern> <dna_bulge> <rna_bulge>
<query> <mismatches>
```

### Pattern Construction

For a 20-nt spacer with NGG PAM:
- Pattern: `NNNNNNNNNNNNNNNNNNNNNGG` (23 characters)
- Query: `<spacer_sequence>NGG` (23 characters)

### Bulge Parameters

- `dna_bulge`: Maximum number of DNA bulges (0 = no DNA bulges)
- `rna_bulge`: Maximum number of RNA bulges (0 = no RNA bulges)

## Output Format

Cas-OFFinder output is TAB-separated:

| Column | Description |
|--------|-------------|
| 1 | Id (query index) |
| 2 | Bulge Type (X/DNA/RNA) |
| 3 | crRNA (aligned with gaps) |
| 4 | DNA (aligned, lowercase=mismatch) |
| 5 | Chromosome |
| 6 | Location (0-based) |
| 7 | Direction (+/-) |
| 8 | Mismatches |
| 9 | Bulge Size |

## Regional Search

To limit search to a specific genomic region:

```python
result = cas_offinder_search(
    spacer_sequence="GCGCGCGCGCGCGCGCGCGC",
    genome_id="ecoli_k12_mg1655",
    search_scope="region",
    chrom="NC_000913.3",
    start=288400,
    end=288500,
)
```

## Limitations

- **CFD scoring**: Not supported for bulged candidates
- **CPU-only mode**: Slower than GPU-accelerated mode
- **Maximum bulge size**: Limited by tool constraints
- **Bulge position accuracy**: Depends on alignment quality

## Provenance

- **Tool**: Cas-OFFinder 3.0.0
- **Source**: https://github.com/pinellolab/Cas-OFFinder
- **License**: BSD 3-Clause
- **Build**: CPU-only via POCL (AMD Ryzen 5 5600G)
- **Commit**: 0a9ac00

## Testing

Run Cas-OFFinder-specific tests:

```bash
python -m pytest tests/test_mcp.py::TestCasOFFinderSearch -v
python -m pytest tests/test_mcp.py::TestAnalyzeMismatchSeed -v
python -m pytest tests/test_interfaces.py::TestCasOFFinderInterfaceParity -v
python -m pytest tests/test_interfaces.py::TestAnalyzeMismatchSeedInterfaceParity -v
```

## Troubleshooting

### "Total 1 device(s) found" Error

This indicates Cas-OFFinder cannot find the POCL runtime. Ensure:
- `pocl-opencl-icd` is installed
- OpenCL ICD loader can find the ICD

### Length Mismatch Error

The query length must match the pattern length. For 20-nt spacer + 3-nt PAM:
- Pattern: 23 characters (20 N's + PAM)
- Query: 23 characters (spacer + PAM)

### No Candidates Found

- Check if the spacer sequence is valid (A/C/G/T only)
- Verify the genome ID is registered
- Ensure the search scope is appropriate
