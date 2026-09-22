"""ASGI entry point for running the backend with uvicorn.

Usage:
    uvicorn asgi:app --reload --host 0.0.0.0 --port 8000
"""

import sys
from pathlib import Path

# Make backend/app importable as top-level packages
_APP = Path(__file__).resolve().parent / "app"
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from api.main import app  # noqa: E402
