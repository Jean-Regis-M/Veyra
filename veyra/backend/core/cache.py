"""Core cache management service.

Provides cache inspection and clearing through a unified interface.
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from schemas.canonical import CacheStatus, VeyraResult, ResultRow
from cache import get_cache_stats, cache_clear as _cache_clear


def cache_status(tool_name: str | None = None) -> VeyraResult:
    """Get cache status.

    Args:
        tool_name: Optional tool name to filter by.

    Returns:
        VeyraResult with cache statistics.
    """
    stats = get_cache_stats()

    if tool_name:
        filtered_by_tool = {tool_name: stats.get("by_tool", {}).get(tool_name, 0)}
        total = filtered_by_tool[tool_name]
    else:
        filtered_by_tool = stats.get("by_tool", {})
        total = stats.get("total_entries", 0)

    status = CacheStatus(
        total_entries=total,
        by_tool=filtered_by_tool,
    )

    return VeyraResult(
        tool="cache_status",
        rows=[],
        summary=status.to_dict(),
        errors=[],
        warnings=[],
        metadata={},
    )


def cache_clear(tool_name: str | None = None) -> VeyraResult:
    """Clear cache entries.

    Args:
        tool_name: Optional tool name to clear only that tool's cache.

    Returns:
        VeyraResult with clear results.
    """
    try:
        count = _cache_clear(tool_name=tool_name)
        return VeyraResult(
            tool="cache_clear",
            rows=[],
            summary={
                "cleared": count,
                "tool_name": tool_name,
            },
            errors=[],
            warnings=[],
            metadata={},
        )
    except Exception as e:
        return VeyraResult(
            tool="cache_clear",
            errors=[str(e)],
        )
