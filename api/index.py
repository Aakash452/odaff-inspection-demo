"""
Vercel entrypoint. The Python runtime looks for a module-level WSGI
callable named `app`; this just re-exports the Flask app defined at the
project root so `app.py` stays the single source of truth locally too.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import app  # noqa: E402,F401
