# Caching

VEYRA uses a two-layer cache: SQLite for metadata and filesystem for index artifacts.

## Architecture

```
SQLite (cache/veyra_cache.db)        Filesystem (alongside FASTA)
┌──────────────────────────┐         ┌─────────────────────────┐
│ cache_entries             │         │ genome.fa.bwt            │
│   cache_key (PK)         │         │ genome.fa.pac            │
│   tool_name               │         │ genome.fa.ann            │
│   params_hash             │         │ genome.fa.fai            │
│   index_path              │         │ ...                      │
│   metadata (JSON)         │         └─────────────────────────┘
│   created_at              │
│   source_checksum         │
│   ttl_seconds             │
└──────────────────────────┘
```

## Cache Key Generation

```python
from cache import make_cache_key

key = make_cache_key(
    "build_offtarget_index",
    genome_id="GRCh38.p14",
    cas_variant="SpCas9",
    checksum="a1b2c3d4e5f6",
)
# → "build_offtarget_index:sha256hex[:24]"
```

Keys are deterministic: same tool + same parameters = same key.

## API

### make_cache_key(tool_name, **params) → str

Generate a deterministic cache key from tool name and parameters.

### cache_get(cache_key) → dict | None

Retrieve a cache entry. Returns `None` if:
- Entry does not exist
- Entry has expired (past `ttl_seconds`)

On expiry, the entry and its filesystem artifacts are automatically cleaned up.

### cache_set(cache_key, tool_name, params_hash, index_path, metadata, source_checksum, ttl_seconds)

Store a cache entry. `INSERT OR REPLACE` semantics.

### cache_invalidate(cache_key) → bool

Delete a specific entry and its filesystem artifacts. Returns `True` if the entry existed.

### cache_clear(tool_name=None) → int

Clear all entries (or entries for a specific tool). Returns count of entries removed.

### get_cache_stats() → dict

Return `{"total_entries": int, "by_tool": {tool_name: count}}`.

## TTL Defaults

| Tool | TTL | Rationale |
|------|-----|-----------|
| `build_offtarget_index` | 30 days | Indexes are stable; FASTA checksum handles invalidation |
| Other tools | 1 day (86400s) | Default TTL |

## Cache Invalidation

Cache entries are invalidated when:

1. **Manual:** `cache_invalidate(key)` or `cache_clear()`
2. **Expiry:** TTL elapsed (checked on `cache_get`)
3. **Checksum change:** If the source FASTA changes, the checksum changes, producing a different cache key. Old entries remain until expired or cleaned up.

## Artifact Cleanup

When a cache entry is invalidated or expires, `_remove_artifacts()` deletes associated filesystem files:

- For BWA indexes: deletes all files matching the prefix (`.bwt`, `.pac`, `.ann`, etc.)
- For directories: recursively removes the directory

## Database Location

```
cache/veyra_cache.db
```

SQLite with WAL mode. Single-writer concurrency is sufficient for VEYRA's use case.

## Usage in Tools

```python
from cache import make_cache_key, cache_get, cache_set

# Check cache
key = make_cache_key("build_offtarget_index", genome_id=gid, checksum=cs)
cached = cache_get(key)
if cached and cached.get("index_path"):
    return cached  # reuse

# Build and store
result = do_expensive_work()
cache_set(key, tool_name="build_offtarget_index", index_path=result.path, ...)
```

## Notes

- Cache is persistent across sessions (stored on disk)
- The cache database is small (kilobytes) — only metadata, not sequences
- Index artifacts (BWA files) can be large (gigabytes for GRCh38)
- `cache_clear()` removes both metadata and artifacts
- No remote/shared cache — each environment has its own `cache/veyra_cache.db`
