#!/usr/bin/env python
"""Backward-compatible entry point for the Sprint 6 dashboard command.

Sprint 6 references were kept for existing runbooks and documentation;
the implementation now lives in ``scripts/sprint7_web.py`` with richer
runtime visualization.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sprint7_web import main


if __name__ == "__main__":
    main()
