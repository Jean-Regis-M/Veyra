"""Core services layer for VEYRA.

All scientific/business logic lives here. CLI, HTTP API, MCP, and Python API
are adapters around these core services.
"""

from core.pam import pam_scan, pam_scan_region
from core.ingestion import ingest
from core.offtarget import build_index, offtarget_search, score_offtargets
from core.ranking import rank_candidates
from core.genome import list_genomes, genome_info
from core.cache import cache_status, cache_clear

__all__ = [
    "pam_scan",
    "pam_scan_region",
    "ingest",
    "build_index",
    "offtarget_search",
    "score_offtargets",
    "rank_candidates",
    "list_genomes",
    "genome_info",
    "cache_status",
    "cache_clear",
]
