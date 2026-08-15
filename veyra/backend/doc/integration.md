# VEYRA Integration Manual

## 1. Project Setup

```bash
cd /home/hrirake/Desktop/hck15/veyra/backend
python3 -m venv venv
source venv/bin/activate
pip install biopython numpy fastapi uvicorn httpx pytest
```

**Requirements:**
- Python 3.10+
- Biopython 1.83+
- numpy 1.26+
- FastAPI (for HTTP API)
- bwa, samtools (for off-target analysis)
- Cas-OFFinder 3.0.0 (built from source, CPU-only via POCL)

## 2. Environment/Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| biopython | 1.83+ | Sequence parsing |
| numpy | 1.26+ | CFD scoring |
| fastapi | 0.100+ | HTTP API |
| uvicorn | 0.20+ | HTTP server |
| pytest | 7.0+ | Testing |
| bwa | 0.7.17 | Off-target search (BWA aln) |
| samtools | 1.19.2 | FASTA indexing |
| Cas-OFFinder | 3.0.0 | Bulge-aware off-target search |
| POCL | 2.3+ | OpenCL CPU runtime |

## 3. Reference Configuration

Reference genomes are configured in `references/__init__.py`.

**CFD Scoring Resources:**
- Path: `/home/hrirake/Desktop/hck15/refrences/data/benchmarks/crisporPaper/CFD_Scoring/`
- Files: `mismatch_score.pkl`, `pam_scores.pkl`
- Status: Copied to `data/resources/crispor_cfd/`

**Note:** `refrences.local/` is read-only reference data.

## 4. CLI Usage

### Unified CLI

```bash
# Activate environment
source venv/bin/activate

# Get help
python -m cli.main --help

# Ingest files
python -m cli.main ingest --input file.fasta
python -m cli.main ingest --input file.fastq --pam
python -m cli.main ingest --input file.gb --output-format json

# PAM scanning
python -m cli.main pam scan --sequence "ATCGATCGAGG" --pam-pattern NGG
python -m cli.main pam scan --input file.fasta --pam-pattern NGG --strand both
python -m cli.main pam scan-region --genome-id GRCh38.p14 --chrom chr1 --start 1000000 --end 1001000

# Index building
python -m cli.main index build --genome-id GRCh38.p14
python -m cli.main index build --genome-id GRCh38.p14 --force

# Off-target analysis
python -m cli.main offtarget search --spacer "ATCGATCGATCGATCGATCG" --genome-id GRCh38.p14
python -m cli.main offtarget score --spacer "ATCGATCGATCGATCGATCG" --candidates-json candidates.json

# Ranking
python -m cli.main rank --guides-json guides.json --sort-by composite

# Genome management
python -m cli.main genome list
python -m cli.main genome info --genome-id GRCh38.p14

# Cache management
python -m cli.main cache status
python -m cli.main cache clear --confirm

# Tool introspection
python -m cli.main tools list
python -m cli.main tools describe pam_scan
```

### Legacy CLI

```bash
python veyra.py --input file.fasta
python veyra.py --input file.fasta --json
python veyra.py --input file.fasta --pam
```

## 5. Python API Usage

```python
import sys
sys.path.insert(0, '/home/hrirake/Desktop/hck15/veyra/backend')

from api import (
    pam_scan_raw,
    pam_scan_region,
    ingest_file,
    build_offtarget_index,
    search_offtargets,
    score_offtargets_cfd,
    rank_guides,
    get_genomes,
    get_genome_info,
    get_cache_info,
    clear_cache,
)

# PAM scan
result = pam_scan_raw("ATCGATCGAGG", pam_pattern="NGG")
print(result.rows[0].start)  # 1-based start position

# Ingest file
result = ingest_file("genome.fasta", pam_scan=True)

# Get results as JSON/TSV/text
print(result.to_json())
print(result.to_tsv())
print(result.to_text())
```

## 6. HTTP API Usage

### Start Server

```bash
source venv/bin/activate
uvicorn http_api.app:app --host 0.0.0.0 --port 8000

# Or
python -m http_api.app
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/ingest` | Ingest genomic file |
| POST | `/pam/scan` | Scan sequence for PAM sites |
| POST | `/pam/scan-region` | Scan genomic region |
| POST | `/index/build` | Build BWA index |
| POST | `/offtarget/search` | Search for off-targets |
| POST | `/offtarget/score` | Score with CFD |
| POST | `/rank` | Rank candidates |
| GET | `/genomes` | List genomes |
| GET | `/genomes/{genome_id}` | Get genome info |
| GET | `/cache/status` | Get cache status |
| POST | `/cache/clear` | Clear cache |
| GET | `/tools` | List available tools |

### Interactive Documentation

- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### Example Requests

```bash
# Health check
curl http://localhost:8000/health

# PAM scan
curl -X POST http://localhost:8000/pam/scan \
  -H "Content-Type: application/json" \
  -d '{"sequence": "ATCGATCGAGG", "pam_pattern": "NGG"}'

# List genomes
curl http://localhost:8000/genomes

# List tools
curl http://localhost:8000/tools
```

## 7. MCP Usage

```bash
# List tools
python -m mcp.server list

# Invoke tool
python -m mcp.server invoke pam_scan --args-json '{"sequence": "ATCGATCG..."}'

# Quick shortcuts
python -m mcp.server pam-scan --sequence "ATCGATCG..."
python -m mcp.server pam-scan-region --genome GRCh38.p14 --chrom chr1 --start 1000000 --end 1001000
python -m mcp.server build-index --genome GRCh38.p14
python -m mcp.server offtarget-search --spacer "ATCGATCG..." --genome GRCh38.p14
```

## 8. Tool-by-Tool Command Reference

### pam_scan

| Parameter | Type | Required | Default | Allowed values | Meaning | Caveats |
|-----------|------|----------|---------|----------------|---------|---------|
| sequence | str | Yes | - | DNA/IUPAC | Input sequence | Must be non-empty |
| pam_pattern | str | No | "NGG" | IUPAC codes | PAM motif | - |
| protospacer_len | int | No | 20 | 1-100 | Spacer length | - |
| strand | str | No | "both" | "both","fwd","rev" | Strand filter | - |
| chrom | str | No | None | Any string | Chromosome name | For output only |

**Output fields:** chrom, start, end, strand, protospacer, pam, pam_type, mismatch_count, mismatch_positions, cfd_score, rs2_score

**Coordinates:** 1-based, half-open [start, end)

### pam_scan_region

| Parameter | Type | Required | Default | Allowed values | Meaning | Caveats |
|-----------|------|----------|---------|----------------|---------|---------|
| genome_id | str | Yes | - | Registered genome | Genome ID | Must exist |
| chrom | str | Yes | - | Chromosome name | Chromosome | - |
| start | int | Yes | - | >=1 | Start position | 1-based |
| end | int | Yes | - | >start | End position | Exclusive |
| pam_pattern | str | No | "NGG" | IUPAC codes | PAM motif | - |
| protospacer_len | int | No | 20 | 1-100 | Spacer length | - |
| strand | str | No | "both" | "both","fwd","rev" | Strand filter | - |

**Requires:** `.fai` index for the genome

### build_offtarget_index

| Parameter | Type | Required | Default | Allowed values | Meaning | Caveats |
|-----------|------|----------|---------|----------------|---------|---------|
| genome_id | str | Yes | - | Registered genome | Genome ID | Must exist |
| cas_variant | str | No | "SpCas9" | Any string | Cas variant | Used for cache key |
| force_rebuild | bool | No | False | True/False | Force rebuild | - |

**Cost:** EXPENSIVE (runs `bwa index`)

### offtarget_search

| Parameter | Type | Required | Default | Allowed values | Meaning | Caveats |
|-----------|------|----------|---------|----------------|---------|---------|
| spacer_sequence | str | Yes | - | DNA (no IUPAC) | Guide sequence | Must be >=15nt |
| genome_id | str | Yes | - | Registered genome | Genome ID | Must have BWA index |
| pam_pattern | str | No | "NGG" | IUPAC codes | PAM pattern | - |
| max_mismatches | int | No | 4 | 0-10 | Max mismatches | - |
| allow_bulge | bool | No | False | True/False | Allow bulges | NOT IMPLEMENTED |
| cas_variant | str | No | "SpCas9" | Any string | Cas variant | - |

**Aligner:** BWA aln (quality-weighted mismatches)

### score_offtargets

| Parameter | Type | Required | Default | Allowed values | Meaning | Caveats |
|-----------|------|----------|---------|----------------|---------|---------|
| spacer_sequence | str | Yes | - | DNA, >=15nt | WT spacer | - |
| candidates | list | Yes | - | PAMSiteRow dicts | Candidates to score | - |
| pam_pattern | str | No | "NGG" | IUPAC codes | PAM pattern | - |

**Scoring:** CFD (Doench et al. 2016) via CRISPOR resources

### rank_candidates

| Parameter | Type | Required | Default | Allowed values | Meaning | Caveats |
|-----------|------|----------|---------|----------------|---------|---------|
| guides | list | Yes | - | PAMSiteRow dicts | Candidate guides | - |
| off_targets | list | No | None | PAMSiteRow dicts | Off-target results | - |
| on_target_scores | dict | No | None | {spacer: score} | On-target scores | - |
| sort_by | str | No | "composite" | "composite","cfd_max","offtarget_count","on_target" | Sort criterion | - |

## 9. Output Schemas

### JSON

```json
{
  "tool": "pam_scan",
  "rows": [
    {
      "chrom": "chr1",
      "start": 100,
      "end": 103,
      "strand": "+",
      "protospacer": "ATCG...",
      "pam": "AGG",
      "pam_type": "SpCas9",
      "mismatch_count": null,
      "mismatch_positions": null,
      "cfd_score": null,
      "rs2_score": null
    }
  ],
  "summary": { ... },
  "errors": [],
  "warnings": [],
  "metadata": {}
}
```

### TSV

Tab-separated values with header row. Empty fields for null values.

### Text

Human-readable format with tool name, summary, and results.

## 10. Exit Codes/Errors

| Exit Code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | Error (file not found, invalid parameters) |
| 2 | Validation failure |
| 130 | Interrupted (Ctrl+C) |

## 11. Cache Behavior

- **Storage:** SQLite database at `cache/veyra_cache.db`
- **TTL:** 30 days for index builds, 1 day default
- **Key:** `{tool_name}:{sha256[:24]}`
- **Invalidation:** Auto-deletes expired entries and associated index files

## 12. Reference/Index Requirements

| Operation | Requirement |
|-----------|-------------|
| PAM scan | None (works on raw sequence) |
| PAM scan region | `.fai` index for genome |
| Build index | FASTA file for genome |
| Off-target search | BWA index (`.bwt`, `.pac`, etc.) |
| CFD scoring | CRISPOR pickle files |

## 13. Performance Notes

| Operation | Tier | Typical Time |
|-----------|------|--------------|
| PAM scan | 1 (cheap) | <1s for <100kb |
| PAM scan (FM-index) | 1 (cheap) | <1s for any size |
| Build index | 2 (expensive) | Minutes to hours |
| Off-target search | 2 (expensive) | Seconds to minutes |
| CFD scoring | 2 (moderate) | <1s per candidate |

## 14. Known Limitations

1. **Bulge detection:** `allow_bulge` parameter accepted but NOT IMPLEMENTED
2. **CFD scoring:** Requires CRISPOR pickle files (not found on this system)
3. **Reference genomes:** No genomes registered (GRCh38.p14 FASTA missing)
4. **Sequence properties:** NOT IMPLEMENTED (no GC, Tm, MFE, homopolymer analysis)
5. **RNAfold:** NOT AVAILABLE for MFE calculation
6. **BWA aln:** Uses quality-weighted mismatches, not pure CRISPR mismatch counting

## 15. Examples

### Complete Workflow

```bash
# 1. Ingest a FASTA file
python -m cli.main ingest --input genome.fasta --output-format json

# 2. Scan for PAM sites
python -m cli.main pam scan --input genome.fasta --pam-pattern NGG --output-format json

# 3. Build index (if genome is registered)
python -m cli.main index build --genome-id GRCh38.p14

# 4. Search for off-targets
python -m cli.main offtarget search \
  --spacer "ATCGATCGATCGATCGATCG" \
  --genome-id GRCh38.p14 \
  --max-mismatches 4

# 5. Score off-targets (requires CFD resources)
python -m cli.main offtarget score \
  --spacer "ATCGATCGATCGATCGATCG" \
  --candidates-json candidates.json

# 6. Rank candidates
python -m cli.main rank --guides-json guides.json --sort-by composite
```

### Python API Workflow

```python
from api import pam_scan_raw, rank_guides

# Scan
result = pam_scan_raw("ATCGATCGAGG", pam_pattern="NGG")

# Rank
ranked = rank_guides([r.to_dict() for r in result.rows])
print(ranked.to_json())
```
