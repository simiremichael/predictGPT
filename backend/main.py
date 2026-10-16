"""Entry point for FastAPI Cloud and local development.

FastAPI Cloud auto-detects this file and runs `uvicorn main:app`.
The sys.path manipulation makes the ``app/`` package importable
without requiring a `pip install -e .` step.
"""

import sys
from pathlib import Path

_APP = Path(__file__).resolve().parent / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from api.main import app  # noqa: E402

__all__ = ["app"]
