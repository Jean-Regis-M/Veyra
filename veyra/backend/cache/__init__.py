"""Persistent caching layer for VEYRA MCP tools.

Uses SQLite for metadata and filesystem for index artifacts.
Cache keys are deterministic based on input parameters.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any

_CACHE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "cache"
_DB_PATH = _CACHE_DIR / "veyra_cache.db"


def _get_conn() -> sqlite3.Connection:
    """Get a connection to the cache database, creating it if needed."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache_entries (
            cache_key TEXT PRIMARY KEY,
            tool_name TEXT NOT NULL,
            params_hash TEXT NOT NULL,
            index_path TEXT,
            metadata TEXT,
            created_at REAL NOT NULL,
            source_checksum TEXT,
            ttl_seconds REAL DEFAULT 86400
        )
    """)
    conn.commit()
    return conn


def make_cache_key(tool_name: str, **params: Any) -> str:
    """Generate a deterministic cache key from tool name and parameters."""
    param_str = json.dumps(params, sort_keys=True, default=str)
    h = hashlib.sha256(f"{tool_name}:{param_str}".encode()).hexdigest()[:24]
    return f"{tool_name}:{h}"


def cache_get(cache_key: str) -> dict | None:
    """Retrieve a cache entry. Returns None if missing or expired."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM cache_entries WHERE cache_key = ?", (cache_key,)
    ).fetchone()
    if row is None:
        return None

    created = row["created_at"]
    ttl = row["ttl_seconds"] or 86400
    if time.time() - created > ttl:
        # Expired — clean up
        conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
        conn.commit()
        _remove_artifacts(row)
        return None

    return {
        "cache_key": row["cache_key"],
        "tool_name": row["tool_name"],
        "index_path": row["index_path"],
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        "created_at": row["created_at"],
        "source_checksum": row["source_checksum"],
    }


def cache_set(
    cache_key: str,
    tool_name: str,
    params_hash: str = "",
    index_path: str | None = None,
    metadata: dict | None = None,
    source_checksum: str = "",
    ttl_seconds: float = 86400,
) -> None:
    """Store a cache entry."""
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO cache_entries
           (cache_key, tool_name, params_hash, index_path, metadata, created_at, source_checksum, ttl_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cache_key,
            tool_name,
            params_hash,
            index_path,
            json.dumps(metadata or {}),
            time.time(),
            source_checksum,
            ttl_seconds,
        ),
    )
    conn.commit()


def cache_invalidate(cache_key: str) -> bool:
    """Invalidate a specific cache entry. Returns True if it existed."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM cache_entries WHERE cache_key = ?", (cache_key,)
    ).fetchone()
    if row is None:
        return False
    _remove_artifacts(row)
    conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (cache_key,))
    conn.commit()
    return True


def cache_clear(tool_name: str | None = None) -> int:
    """Clear cache entries. Returns number of entries removed."""
    conn = _get_conn()
    if tool_name:
        rows = conn.execute(
            "SELECT * FROM cache_entries WHERE tool_name = ?", (tool_name,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM cache_entries").fetchall()

    for row in rows:
        _remove_artifacts(row)

    if tool_name:
        conn.execute("DELETE FROM cache_entries WHERE tool_name = ?", (tool_name,))
    else:
        conn.execute("DELETE FROM cache_entries")
    conn.commit()
    return len(rows)


def _remove_artifacts(row: sqlite3.Row) -> None:
    """Remove cached index files from disk.

    Only removes BWA/samtools index artifacts, NOT the source FASTA file.
    """
    index_path = row["index_path"]
    if not index_path:
        return
    base = Path(index_path)
    if base.is_dir():
        import shutil
        shutil.rmtree(base, ignore_errors=True)
    else:
        # BWA index artifact extensions to remove
        _INDEX_EXTS = {
            ".bwt", ".pac", ".ann", ".amb", ".fai",
            ".sa", ".rbwt", ".rpac", ".rical",
        }
        parent = base.parent
        prefix = base.name
        if parent.is_dir():
            for f in parent.iterdir():
                if f.name.startswith(prefix) and f.suffix in _INDEX_EXTS:
                    f.unlink(missing_ok=True)


def get_cache_stats() -> dict[str, Any]:
    """Return cache statistics."""
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM cache_entries").fetchone()[0]
    by_tool = {}
    for row in conn.execute(
        "SELECT tool_name, COUNT(*) as cnt FROM cache_entries GROUP BY tool_name"
    ).fetchall():
        by_tool[row["tool_name"]] = row["cnt"]
    return {"total_entries": total, "by_tool": by_tool}
