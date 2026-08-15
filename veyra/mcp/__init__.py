"""Repository-root compatibility package for ``python -m mcp.server``.

The implementation lives under ``backend/mcp``. This path shim keeps the
documented module command working from either the repository root or the
backend directory without duplicating the package.
"""

from pathlib import Path

__path__ = [str(Path(__file__).resolve().parent.parent / "backend" / "mcp")]
