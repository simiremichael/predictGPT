"""Entry point for FastAPI Cloud and local development.

FastAPI Cloud auto-detects this file and runs `uvicorn main:app`.
The sys.path manipulation makes the ``app/`` package importable
without requiring a `pip install -e .` step.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

_APP = Path(__file__).resolve().parent / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from api.main import app  # noqa: E402

__all__ = ["app"]
