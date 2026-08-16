# VEYRA Backend — Genomic Intelligence Backend

VEYRA is a modular genomic intelligence backend providing ingestion, PAM scanning, and CRISPR off-target analysis through four equivalent interfaces: CLI, Python API, HTTP API, and MCP.

**Status:** Working baseline — unified interface layer (v0.3).

## Architecture

```
                    ┌──────────────┐
                    │     CLI      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │              │
                    │ VEYRA CORE   │
                    │   SERVICES   │
                    │              │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           HTTP API       MCP      Python API
```

All interfaces call the same core services. No logic is duplicated.

## Quick Start

```bash
# Setup
cd veyra/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# CLI
python -m cli.main pam scan --sequence "ATCGATCGAGGATCGATCGATCG"

# Python API
from api import pam_scan_raw
result = pam_scan_raw("ATCGATCGAGG", pam_pattern="NGG")

# HTTP API
uvicorn http_api.app:app --port 8000
# Open http://localhost:8000/docs

# MCP
python -m mcp.server pam-scan --sequence "ATCGATCGAGG"
```

## Interfaces

### CLI

```bash
python -m cli.main --help
python -m cli.main pam scan --sequence "ATCG..." --pam-pattern NGG
python -m cli.main genome list
python -m cli.main tools list
```

See `doc/interfaces.md` for full command tree.

### Python API

```python
from api import pam_scan_raw, get_genomes, search_offtargets

result = pam_scan_raw("ATCG...", pam_pattern="NGG")
print(result.rows[0].start)
```

### HTTP API

```bash
uvicorn http_api.app:app --host 0.0.0.0 --port 8000
```

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `POST /pam/scan` | Scan sequence |
| `POST /offtarget/search` | Search off-targets |
| `GET /genomes` | List genomes |
| `GET /tools` | List tools |

Interactive docs: `http://localhost:8000/docs`

### MCP

```bash
python -m mcp.server list
python -m mcp.server pam-scan --sequence "ATCG..."
```

## Project Structure

```
veyra/backend/
├── __main__.py              # python -m veyra entry
├── veyra.py                 # Legacy CLI (ingestion)
├── requirements.txt
├── core/                    # Core services (unified logic)
│   ├── pam.py               # PAM scanning service
│   ├── ingestion.py         # Ingestion service
│   ├── offtarget.py         # Off-target service
│   ├── ranking.py           # Ranking service
│   ├── genome.py            # Genome management
│   └── cache.py             # Cache management
├── schemas/                 # Canonical schemas
│   ├── genomic_record.py    # GenomicRecord dataclass
│   └── canonical.py         # Request/response models
├── cli/                     # CLI adapter
│   └── main.py              # Unified CLI
├── api/                     # Python API adapter
│   └── __init__.py
├── http_api/                # FastAPI HTTP adapter
│   └── app.py
├── parsers/                 # File parsers
├── mcp/                     # MCP tools
├── references/              # Genome registry
├── cache/                   # SQLite cache
├── doc/                     # Documentation
└── tests/                   # Test suite
```

## MCP Tools

| Tool | Tier | Cost | Description |
|------|------|------|-------------|
| `pam_scan` | 1 | cheap | PAM scanning on input sequence |
| `pam_scan_region` | 1 | cheap | PAM scanning on genomic region |
| `build_offtarget_index` | 2 | expensive | BWA index creation (cached) |
| `offtarget_search` | 2 | expensive | Mismatch-tolerant off-target search |
| `score_offtargets` | 2 | moderate | CFD specificity scoring |
| `rank_candidates` | 2 | moderate | Candidate guide ranking |

## Testing

```bash
source venv/bin/activate
python -m pytest tests/ -v                    # full suite
python -m pytest tests/test_interfaces.py -v  # interface parity tests
```

## Documentation

- `doc/interfaces.md` — CLI, API, HTTP, MCP reference
- `doc/architecture.md` — pipeline diagram
- `doc/mcp_tools.md` — MCP tool reference
- `doc/reference_genomes.md` — genome registry
- `doc/off_target_search.md` — BWA search methodology
- `doc/caching.md` — cache architecture

## To run backend 
```bash
cd backend
uvicorn http_api.app:app --host 127.0.0.1 --port 8000 --reload

Backend URL: http://127.0.0.1:8000
API docs: http://127.0.0.1:8000/docs
```