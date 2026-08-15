"""VEYRA package entry point.

Allows running: python -m veyra
"""

from __future__ import annotations

import sys
import os

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from cli.main import main

if __name__ == "__main__":
    sys.exit(main())
